from __future__ import annotations

"""网球赛事调度的共享数据处理与求解流水线。"""

from dataclasses import dataclass
from pathlib import Path

from constraints import NoPlayerOverlapConstraint
from cost_evaluator import (
    BackToBackRule,
    EarlyStartRule,
    EmptyCourtRule,
    TennisTournamentEvaluator,
)
from dag_builder import build_dag
from data_parser import parse_draw_to_teams
from gurobi_scheduler import GurobiSearchStrategy
from hooks import SchedulerHook
from models import Player, SchedulerConfig
from scheduler_engine import ScheduleState
from search_strategies import BeamSearchStrategy

ID_OFFSETS = {
    "ms": 1000,
    "ws": 2000,
    "md": 3000,
    "wd": 4000,
    "xd": 5000,
}

EVENT_DISPLAY_NAMES = {
    "ms": "男单",
    "ws": "女单",
    "md": "男双",
    "wd": "女双",
    "xd": "混双",
}

EVENT_KEY_ALIASES = {
    "ms": "ms",
    "men_singles": "ms",
    "sample_men_singles": "ms",
    "ws": "ws",
    "women_singles": "ws",
    "sample_women_singles": "ws",
    "md": "md",
    "men_doubles": "md",
    "sample_men_doubles": "md",
    "wd": "wd",
    "women_doubles": "wd",
    "sample_women_doubles": "wd",
    "xd": "xd",
    "mixed_doubles": "xd",
    "sample_mixed_doubles": "xd",
}


@dataclass(frozen=True)
class SchedulerRunResult:
    best_state: ScheduleState
    all_labels: dict[int, str]
    enabled_events: list[str]
    evaluator: TennisTournamentEvaluator
    solve_info: dict[str, object]


def normalize_event_key(raw_name: str) -> str:
    stem = Path(raw_name).stem.lower()
    if stem not in EVENT_KEY_ALIASES:
        raise ValueError(f"无法识别赛事文件类型: {raw_name}")
    return EVENT_KEY_ALIASES[stem]


def build_players_dict(players_raw: dict | object) -> dict[str, Player]:
    if not isinstance(players_raw, dict):
        raise ValueError("选手数据格式应为 JSON 对象")

    players_dict: dict[str, Player] = {}
    for key_name, info in players_raw.items():
        if not isinstance(info, dict):
            continue
        players_dict[key_name] = Player.from_dict(key_name, info)
    return players_dict


def build_draw_nodes(
    draw_payloads: dict[str, list[dict]],
    players_dict: dict[str, Player],
) -> tuple[dict[int, object], dict[int, str], list[str]]:
    all_nodes: dict[int, object] = {}
    all_labels: dict[int, str] = {}
    enabled_events: list[str] = []

    for raw_key, draw_list in draw_payloads.items():
        event_key = normalize_event_key(raw_key)
        if not isinstance(draw_list, list):
            raise ValueError(f"{raw_key} 格式应为 JSON 数组")

        draw_teams = parse_draw_to_teams(draw_list)
        nodes, labels = build_dag(
            draw_teams,
            players_dict,
            start_id=ID_OFFSETS[event_key],
        )
        all_nodes.update(nodes)
        all_labels.update(labels)
        enabled_events.append(EVENT_DISPLAY_NAMES[event_key])

    return all_nodes, all_labels, enabled_events


def create_evaluator(config: SchedulerConfig) -> TennisTournamentEvaluator:
    return TennisTournamentEvaluator(
        match_rules=[
            EarlyStartRule(weight=config.w1),
            BackToBackRule(weight=config.w2),
        ],
        global_rules=[EmptyCourtRule(weight=config.w3)],
    )


def create_strategy(
    solver: str,
    solver_time_limit: float | None,
    solver_mip_gap: float | None,
    solver_log_to_console: bool,
):
    normalized_solver = solver.strip().lower()
    if normalized_solver == "beam":
        return BeamSearchStrategy()
    if normalized_solver == "gurobi":
        return GurobiSearchStrategy(
            time_limit=solver_time_limit,
            mip_gap=solver_mip_gap,
            log_to_console=solver_log_to_console,
        )
    raise ValueError(f"不支持的求解器: {solver}")


def build_default_solve_info(
    solver: str,
    best_state: ScheduleState,
) -> dict[str, object]:
    return {
        "solver": solver,
        "status_name": "HEURISTIC（启发式求解）",
        "objective_value": best_state.cost,
        "best_bound": None,
        "mip_gap": None,
        "runtime_seconds": None,
        "total_slots": best_state.t - 1,
    }


def run_scheduler_from_draws(
    players_raw: dict | object,
    draw_payloads: dict[str, list[dict]],
    config: SchedulerConfig,
    solver: str = "beam",
    solver_time_limit: float | None = None,
    solver_mip_gap: float | None = 0.0,
    solver_log_to_console: bool = False,
    hooks: list[SchedulerHook] | None = None,
) -> SchedulerRunResult:
    if hooks is None:
        hooks = []

    players_dict = build_players_dict(players_raw)
    all_nodes, all_labels, enabled_events = build_draw_nodes(draw_payloads, players_dict)
    evaluator = create_evaluator(config)
    strategy = create_strategy(
        solver=solver,
        solver_time_limit=solver_time_limit,
        solver_mip_gap=solver_mip_gap,
        solver_log_to_console=solver_log_to_console,
    )

    best_state = strategy.schedule(
        initial_nodes=all_nodes,
        config=config,
        evaluator=evaluator,
        constraints=[NoPlayerOverlapConstraint()],
        hooks=hooks,
    )
    solve_info = getattr(
        strategy,
        "last_solve_info",
        build_default_solve_info(solver=solver, best_state=best_state),
    )

    return SchedulerRunResult(
        best_state=best_state,
        all_labels=all_labels,
        enabled_events=enabled_events,
        evaluator=evaluator,
        solve_info=solve_info,
    )


def build_schedule_index(best_state: ScheduleState) -> dict[int, list[int]]:
    schedule_by_t: dict[int, list[int]] = {}
    for node in best_state.all_nodes.values():
        schedule_by_t.setdefault(node.scheduled_time, []).append(node.match_id)
    return schedule_by_t


def build_schedule_payload(
    best_state: ScheduleState,
    all_labels: dict[int, str],
) -> dict[str, list[dict[str, object]]]:
    schedule_by_t: dict[str, list[dict[str, object]]] = {}
    for node in best_state.all_nodes.values():
        slot_key = str(node.scheduled_time)
        schedule_by_t.setdefault(slot_key, []).append(
            {
                "match_id": node.match_id,
                "label": all_labels.get(node.match_id, f"[Unknown] Match {node.match_id}"),
                "players": sorted(node.potential_players),
            }
        )

    for matches in schedule_by_t.values():
        matches.sort(key=lambda item: int(item["match_id"]))
    return schedule_by_t
