from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from constraints import NoPlayerOverlapConstraint
from cost_evaluator import (
    BackToBackRule,
    EarlyStartRule,
    EmptyCourtRule,
    TennisTournamentEvaluator,
)
from dag_builder import build_dag
from data_parser import parse_draw_to_teams
from hooks import ConsoleLoggingHook
from models import Player, SchedulerConfig
from schedule_output import build_schedule_by_slot, serialize_schedule_txt
from search_strategies import BeamSearchStrategy

ID_OFFSETS = {
    "ms": 1000,
    "ws": 2000,
    "md": 3000,
    "wd": 4000,
    "xd": 5000,
}

EVENT_NAMES = {
    "ms": "男单抽签",
    "ws": "女单抽签",
    "md": "男双抽签",
    "wd": "女双抽签",
    "xd": "混双抽签",
}


def _safe_load_json(path: str, file_desc: str) -> dict | list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[Error] 未找到{file_desc}文件: {path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"[Error] {file_desc}格式解析失败: {path} ({exc})")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tennis tournament scheduler")
    parser.add_argument("--players", required=True, help="Path to players.json")
    parser.add_argument("--ms", help="Path to men singles JSON")
    parser.add_argument("--ws", help="Path to women singles JSON")
    parser.add_argument("--md", help="Path to men doubles JSON")
    parser.add_argument("--wd", help="Path to women doubles JSON")
    parser.add_argument("--xd", help="Path to mixed doubles JSON")
    parser.add_argument("--courts", type=int, default=5, help="Available courts")
    parser.add_argument("--w1", type=float, default=10.0, help="SC1 weight")
    parser.add_argument("--w2", type=float, default=7.0, help="SC2 weight")
    parser.add_argument("--w3", type=float, default=2.5, help="SC3 weight")
    parser.add_argument(
        "--beam-width",
        type=int,
        default=10,
        help="Beam search width",
    )
    args = parser.parse_args()

    config = SchedulerConfig(
        courts=args.courts,
        beam_width=args.beam_width,
        w1=args.w1,
        w2=args.w2,
        w3=args.w3,
    )

    print("正在加载选手数据库...")
    players_raw = _safe_load_json(args.players, "选手数据")
    if not isinstance(players_raw, dict):
        print("[Error] 选手数据格式应为 JSON 对象")
        sys.exit(1)

    players_dict: dict[str, Player] = {}
    for key_name, info in players_raw.items():
        if not isinstance(info, dict):
            continue
        players_dict[key_name] = Player.from_dict(key_name, info)

    all_nodes: dict[int, object] = {}
    all_labels: dict[int, str] = {}
    enabled_events: list[str] = []

    for key in ("ms", "ws", "md", "wd", "xd"):
        draw_path = getattr(args, key)
        if not draw_path:
            continue

        event_name = EVENT_NAMES[key]
        print(f"正在解析{event_name}...")
        enabled_events.append(event_name.replace("抽签", ""))
        draw_list = _safe_load_json(draw_path, event_name)
        if not isinstance(draw_list, list):
            print(f"[Error] {event_name}格式应为 JSON 数组")
            sys.exit(1)
        draw_teams = parse_draw_to_teams(draw_list)

        try:
            nodes, labels = build_dag(
                draw_teams,
                players_dict,
                start_id=ID_OFFSETS[key],
            )
        except (ValueError, KeyError) as exc:
            print(f"[业务数据错误] {exc}")
            sys.exit(1)

        all_nodes.update(nodes)
        all_labels.update(labels)

    evaluator = TennisTournamentEvaluator(
        match_rules=[
            EarlyStartRule(weight=config.w1),
            BackToBackRule(weight=config.w2),
        ],
        global_rules=[EmptyCourtRule(weight=config.w3)],
    )
    evaluator.print_active_rules()

    overlap_constraint = NoPlayerOverlapConstraint()
    logger_hook = ConsoleLoggingHook()
    strategy = BeamSearchStrategy()

    try:
        best_state = strategy.schedule(
            initial_nodes=all_nodes,
            config=config,
            evaluator=evaluator,
            constraints=[overlap_constraint],
            hooks=[logger_hook],
        )
    except (ValueError, KeyError) as exc:
        print(f"[业务数据错误] {exc}")
        sys.exit(1)

    schedule_by_t = build_schedule_by_slot(best_state.all_nodes, all_labels)
    active_rules = [
        {
            "name": rule.name,
            "weight": rule.weight,
            "description": rule.description,
        }
        for rule in [*evaluator.match_rules, *evaluator.global_rules]
    ]

    base_dir = os.path.dirname(os.path.dirname(__file__))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = os.path.join(results_dir, f"schedule_result_{timestamp}.txt")

    with open(result_path, "w", encoding="utf-8") as f:
        f.write(
            serialize_schedule_txt(
                total_cost=best_state.cost,
                total_slots=best_state.t - 1,
                included_events=enabled_events,
                schedule_by_t=schedule_by_t,
                active_rules=active_rules,
            )
        )

    total_slots = best_state.t - 1
    print(
        f"[Success] 赛程计算完毕！总耗时片: {total_slots}, 结果已保存至 {result_path}"
    )


if __name__ == "__main__":
    main()
