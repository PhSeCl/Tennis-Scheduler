from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import eel

# Determine if the app is running as a compiled PyInstaller executable
if getattr(sys, "frozen", False):
    # BASE_DIR is the temp folder where PyInstaller extracts everything (_MEIPASS)
    BASE_DIR = sys._MEIPASS
    # RUNTIME_DIR is the actual folder where the user double-clicked the .exe
    RUNTIME_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RUNTIME_DIR = BASE_DIR

SRC_DIR = os.path.join(BASE_DIR, "src")
# Data and Results MUST be read/written to the user's actual directory, not the temp folder
DATA_DIR = os.path.join(RUNTIME_DIR, "data")
RESULTS_DIR = os.path.join(RUNTIME_DIR, "results")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from constraints import NoPlayerOverlapConstraint
from cost_evaluator import BackToBackRule, EarlyStartRule, EmptyCourtRule, TennisTournamentEvaluator
from dag_builder import build_dag
from data_parser import parse_draw_to_teams
from models import Player, SchedulerConfig
from schedule_output import (
    build_schedule_by_slot,
    event_display_name,
    event_key_from_draw_file,
    normalize_event_labels,
    serialize_schedule_txt,
    start_id_for_draw_file,
)
from search_strategies import BeamSearchStrategy


@eel.expose
def ping() -> str:
    return "pong"


def _resolve_data_path(filename: str) -> str:
    filename = filename.lstrip("/\\")
    path = os.path.abspath(os.path.join(DATA_DIR, filename))
    data_root = os.path.abspath(DATA_DIR)
    if not path.startswith(data_root):
        raise ValueError("Path traversal attempt detected.")
    return path


def _load_json_file(filename: str) -> dict | list:
    path = _resolve_data_path(filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _default_payload(filename: str) -> dict | list:
    return {} if filename == "players.json" else []


@eel.expose
def get_available_files() -> list[str]:
    if not os.path.isdir(DATA_DIR):
        return []
    results: list[str] = []
    for root, _, files in os.walk(DATA_DIR):
        for file in files:
            if not file.endswith(".json"):
                continue
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, DATA_DIR).replace("\\", "/")
            results.append(rel_path)
    return sorted(results)


@eel.expose
def read_json_file(filename: str) -> dict | list:
    try:
        return _load_json_file(filename)
    except FileNotFoundError:
        return _default_payload(filename)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}")


@eel.expose
def write_json_file(filename: str, data: dict | list) -> dict:
    path = _resolve_data_path(filename)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"status": "success"}


@eel.expose
def run_scheduler(config: dict, file_paths: dict) -> dict:
    try:
        players_file = file_paths.get("players", "players.json")
        draw_files = file_paths.get("draws", [])

        players_raw = _load_json_file(players_file)
        if not isinstance(players_raw, dict):
            raise ValueError("players.json must be a JSON object")

        players_dict: dict[str, Player] = {}
        for key_name, info in players_raw.items():
            if isinstance(info, dict):
                players_dict[key_name] = Player.from_dict(key_name, info)

        all_nodes: dict[int, object] = {}
        all_labels: dict[int, str] = {}
        event_counts: dict[str, int] = {}

        for index, draw_file in enumerate(draw_files):
            event_key = event_key_from_draw_file(draw_file)
            duplicate_index = event_counts.get(event_key, 0) if event_key is not None else 0
            start_id = start_id_for_draw_file(
                draw_file,
                index,
                duplicate_index=duplicate_index,
            )
            draw_list = _load_json_file(draw_file)
            if not isinstance(draw_list, list):
                raise ValueError(f"{draw_file} must be a JSON array")
            draw_teams = parse_draw_to_teams(draw_list)
            nodes, labels = build_dag(draw_teams, players_dict, start_id=start_id)
            labels = normalize_event_labels(labels, draw_file)
            all_nodes.update(nodes)
            all_labels.update(labels)
            if event_key is not None:
                event_counts[event_key] = duplicate_index + 1

        scheduler_config = SchedulerConfig(
            courts=int(config.get("courts", 5)),
            beam_width=int(config.get("beam_width", 10)),
            w1=float(config.get("w1", 10.0)),
            w2=float(config.get("w2", 7.0)),
            w3=float(config.get("w3", 2.5)),
        )

        evaluator = TennisTournamentEvaluator(
            match_rules=[
                EarlyStartRule(weight=scheduler_config.w1),
                BackToBackRule(weight=scheduler_config.w2),
            ],
            global_rules=[EmptyCourtRule(weight=scheduler_config.w3)],
        )

        strategy = BeamSearchStrategy()
        best_state = strategy.schedule(
            initial_nodes=all_nodes,
            config=scheduler_config,
            evaluator=evaluator,
            constraints=[NoPlayerOverlapConstraint()],
            hooks=[],
        )

        schedule_by_t = build_schedule_by_slot(best_state.all_nodes, all_labels)
        active_rules = [
            {
                "name": rule.name,
                "weight": rule.weight,
                "description": rule.description,
            }
            for rule in [*evaluator.match_rules, *evaluator.global_rules]
        ]

        return {
            "status": "success",
            "total_cost": best_state.cost,
            "total_slots": best_state.t - 1,
            "schedule_by_t": schedule_by_t,
            "active_rules": active_rules,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc)}


@eel.expose
def export_schedule_to_txt(schedule_data: dict, selected_draws: list[str]) -> dict:
    try:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(RESULTS_DIR, f"schedule_result_{timestamp}.txt")

        with open(filepath, "w", encoding="utf-8") as f:
            included_events = [event_display_name(draw_file) for draw_file in selected_draws]
            f.write(
                serialize_schedule_txt(
                    total_cost=schedule_data.get("total_cost"),
                    total_slots=schedule_data.get("total_slots"),
                    included_events=included_events,
                    schedule_by_t=schedule_data.get("schedule_by_t", {}),
                    active_rules=schedule_data.get("active_rules"),
                )
            )

        return {"status": "success", "filepath": filepath}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc)}


def main() -> None:
    web_dir = os.path.join(BASE_DIR, "frontend", "dist")
    eel.init(web_dir)

    is_dev = "--dev" in sys.argv
    if is_dev:
        print("[Eel] Dev mode: open http://localhost:5173")
        eel.start(
            "index.html",
            host="localhost",
            port=8000,
            mode=None,
            block=True,
        )
    else:
        print("[Eel] Prod mode: frontend/dist/index.html")
        eel.start(
            "index.html",
            host="localhost",
            port=8000,
            mode="edge",
            block=True,
        )


if __name__ == "__main__":
    main()
