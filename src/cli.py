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
from search_strategies import BeamSearchStrategy


ID_OFFSETS = {
    "ms": 1000,
    "ws": 2000,
    "md": 3000,
    "wd": 4000,
    "xd": 5000,
}


def _safe_load_json(path: str, file_desc: str) -> dict | list:
    # 统一错误处理与提示
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[Error] 未找到{file_desc}文件: {path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"[Error] {file_desc}格式解析失败: {path} ({exc})")
        sys.exit(1)


if __name__ == "__main__":
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

    # 将命令行参数统一收敛到配置模型，便于后续扩展与传递
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

        event_name = {
            "ms": "男单抽签",
            "ws": "女单抽签",
            "md": "男双抽签",
            "wd": "女双抽签",
            "xd": "混双抽签",
        }[key]
        print(f"正在解析{event_name}...")
        enabled_events.append(event_name.replace("抽签", ""))
        draw_list = _safe_load_json(draw_path, event_name)
        if not isinstance(draw_list, list):
            print(f"[Error] {event_name} 格式应为 JSON 数组")
            sys.exit(1)
        draw_teams = parse_draw_to_teams(draw_list)

        # 解析抽签并构建 DAG
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

    # 规则权重由命令行参数控制
    r1 = EarlyStartRule(weight=config.w1)
    r2 = BackToBackRule(weight=config.w2)
    r3 = EmptyCourtRule(weight=config.w3)
    evaluator = TennisTournamentEvaluator(
        match_rules=[r1, r2],
        global_rules=[r3],
    )
    evaluator.print_active_rules()

    overlap_constraint = NoPlayerOverlapConstraint()
    logger_hook = ConsoleLoggingHook()
    strategy = BeamSearchStrategy()

    # 调度搜索主入口
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

    # 按时间片归类并输出到文件
    schedule_by_t: dict[int, list[int]] = {}
    for node in best_state.all_nodes.values():
        schedule_by_t.setdefault(node.scheduled_time, []).append(node.match_id)

    # 输出到项目根目录的 results/
    base_dir = os.path.dirname(os.path.dirname(__file__))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = os.path.join(results_dir, f"schedule_result_{timestamp}.txt")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write("=" * 50 + "\n")
        f.write("网球赛事极速智能编排结果\n")
        f.write(f"总惩罚分: {best_state.cost} | 预计完赛总时间片: {best_state.t - 1}\n")
        f.write("排表项目: " + ("、".join(enabled_events) or "无") + "\n")
        f.write("启用规则:\n")
        for rule in evaluator.match_rules:
            f.write(f"  - {rule.name} (权重: {rule.weight}): {rule.description}\n")
        for rule in evaluator.global_rules:
            f.write(f"  - {rule.name} (权重: {rule.weight}): {rule.description}\n")
        f.write("=" * 50 + "\n\n")

        for t in sorted(schedule_by_t.keys()):
            f.write(f"[时间片 {t}]\n")
            ids = sorted(schedule_by_t[t])
            for idx, match_id in enumerate(ids, start=1):
                label = all_labels.get(match_id, f"[未知] 场次{match_id}")
                f.write(f"  - 场地 {idx}: {label} (场次ID: {match_id})\n")
            f.write("\n")

    total_slots = best_state.t - 1
    print(
        "[Success] 赛程计算完毕！"
        f"总耗时片: {total_slots}, 结果已保存至 results/schedule_result.txt"
    )
