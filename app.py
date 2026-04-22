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

from models import SchedulerConfig
from scheduler_pipeline import build_schedule_payload, run_scheduler_from_draws


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


def _format_optional_float(value: object, digits: int = 6) -> str:
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


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

        draw_payloads: dict[str, list[dict]] = {}
        for draw_file in draw_files:
            draw_list = _load_json_file(draw_file)
            if not isinstance(draw_list, list):
                raise ValueError(f"{draw_file} must be a JSON array")
            draw_payloads[draw_file] = draw_list

        scheduler_config = SchedulerConfig(
            courts=int(config.get("courts", 5)),
            beam_width=int(config.get("beam_width", 10)),
            w1=float(config.get("w1", 10.0)),
            w2=float(config.get("w2", 7.0)),
            w3=float(config.get("w3", 2.5)),
        )

        solver = str(config.get("solver", "beam"))
        solver_time_limit = float(config.get("solver_time_limit", 60.0))
        solver_mip_gap = float(config.get("solver_mip_gap", 0.0))
        solver_log_to_console = bool(config.get("solver_log_to_console", False))

        run_result = run_scheduler_from_draws(
            players_raw=players_raw,
            draw_payloads=draw_payloads,
            config=scheduler_config,
            solver=solver,
            solver_time_limit=solver_time_limit,
            solver_mip_gap=solver_mip_gap,
            solver_log_to_console=solver_log_to_console,
            hooks=[],
        )
        schedule_by_t = build_schedule_payload(
            best_state=run_result.best_state,
            all_labels=run_result.all_labels,
        )
        solve_info = run_result.solve_info

        return {
            "status": "success",
            "total_cost": run_result.best_state.cost,
            "total_slots": run_result.best_state.t - 1,
            "schedule_by_t": schedule_by_t,
            "enabled_events": run_result.enabled_events,
            "solve_info": solve_info,
            "solver": solve_info.get("solver", solver),
            "solver_status": solve_info.get("status_name"),
            "solver_best_bound": solve_info.get("best_bound"),
            "solver_mip_gap": solve_info.get("mip_gap"),
            "solver_runtime_seconds": solve_info.get("runtime_seconds"),
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
            f.write("=" * 50 + "\n")
            f.write("Tennis Smart Schedule Result\n")
            f.write(f"Total Penalty Cost: {schedule_data.get('total_cost')}\n")
            f.write(f"Total Time Slots: {schedule_data.get('total_slots')}\n")
            f.write(f"Included Events: {', '.join(selected_draws)}\n")
            f.write(f"Solver: {schedule_data.get('solver', 'beam')}\n")
            f.write(f"Solver Status: {schedule_data.get('solver_status', '-')}\n")
            f.write(
                "Runtime Seconds: "
                f"{_format_optional_float(schedule_data.get('solver_runtime_seconds'), digits=4)}\n"
            )
            f.write(
                "Best Bound: "
                f"{_format_optional_float(schedule_data.get('solver_best_bound'))}\n"
            )
            f.write(
                "MIP Gap: "
                f"{_format_optional_float(schedule_data.get('solver_mip_gap'))}\n"
            )
            f.write("=" * 50 + "\n\n")

            schedule_by_t = schedule_data.get("schedule_by_t", {})
            for t in sorted(schedule_by_t.keys(), key=lambda x: int(x)):
                f.write(f"[Time Slot {t}]\n")
                matches = schedule_by_t[t]
                for idx, match in enumerate(matches, start=1):
                    players_str = " / ".join(match.get("players", []))
                    label = match.get("label", "")
                    match_id = match.get("match_id", "")
                    f.write(
                        f"  - Court {idx}: {label} ({players_str}) [ID: {match_id}]\n"
                    )
                f.write("\n")

        return {
            "status": "success",
            "filepath": filepath,
            "solver": schedule_data.get("solver", "beam"),
            "solver_status": schedule_data.get("solver_status", "-"),
        }
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
