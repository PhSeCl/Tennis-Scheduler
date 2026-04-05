from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from hooks import ConsoleLoggingHook
from models import SchedulerConfig
from scheduler_pipeline import build_schedule_index, run_scheduler_from_draws


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


def _format_optional_float(value: object, digits: int = 6) -> str:
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


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
    parser.add_argument(
        "--solver",
        choices=("beam", "gurobi"),
        default="beam",
        help="选择调度求解器",
    )
    parser.add_argument(
        "--solver-time-limit",
        type=float,
        default=60.0,
        help="Gurobi 求解时间上限（秒）",
    )
    parser.add_argument(
        "--solver-mip-gap",
        type=float,
        default=0.0,
        help="Gurobi MIPGap 容忍度，例如 0.01 表示 1%",
    )
    parser.add_argument(
        "--solver-log-to-console",
        action="store_true",
        help="是否显示 Gurobi 原生日志",
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

    draw_payloads: dict[str, list[dict]] = {}
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
        draw_list = _safe_load_json(draw_path, event_name)
        if not isinstance(draw_list, list):
            print(f"[Error] {event_name} 格式应为 JSON 数组")
            sys.exit(1)
        draw_payloads[key] = draw_list

    logger_hook = ConsoleLoggingHook()
    try:
        run_result = run_scheduler_from_draws(
            players_raw=players_raw,
            draw_payloads=draw_payloads,
            config=config,
            solver=args.solver,
            solver_time_limit=args.solver_time_limit,
            solver_mip_gap=args.solver_mip_gap,
            solver_log_to_console=args.solver_log_to_console,
            hooks=[logger_hook],
        )
    except (ValueError, KeyError, RuntimeError, NotImplementedError) as exc:
        print(f"[Error] {exc}")
        sys.exit(1)

    best_state = run_result.best_state
    schedule_by_t = build_schedule_index(best_state)
    solve_info = run_result.solve_info

    base_dir = os.path.dirname(os.path.dirname(__file__))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = os.path.join(results_dir, f"schedule_result_{timestamp}.txt")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write("=" * 50 + "\n")
        f.write("网球赛事极速智能编排结果\n")
        f.write(f"总惩罚分: {best_state.cost} | 预计完赛总时间片: {best_state.t - 1}\n")
        f.write("排表项目: " + ("、".join(run_result.enabled_events) or "无") + "\n")
        f.write(f"求解器: {solve_info.get('solver', args.solver)}\n")
        f.write(f"求解状态: {solve_info.get('status_name', 'HEURISTIC（启发式求解）')}\n")
        f.write(
            "运行时间(秒): "
            f"{_format_optional_float(solve_info.get('runtime_seconds'), digits=4)}\n"
        )
        f.write(f"最优界: {_format_optional_float(solve_info.get('best_bound'))}\n")
        f.write(f"MIPGap: {_format_optional_float(solve_info.get('mip_gap'))}\n")
        f.write("启用规则:\n")
        for rule in run_result.evaluator.match_rules:
            f.write(f"  - {rule.name} (权重: {rule.weight}): {rule.description}\n")
        for rule in run_result.evaluator.global_rules:
            f.write(f"  - {rule.name} (权重: {rule.weight}): {rule.description}\n")
        f.write("=" * 50 + "\n\n")

        for t in sorted(schedule_by_t.keys()):
            f.write(f"[时间片 {t}]\n")
            ids = sorted(schedule_by_t[t])
            for idx, match_id in enumerate(ids, start=1):
                label = run_result.all_labels.get(match_id, f"[未知] 场次{match_id}")
                f.write(f"  - 场地 {idx}: {label} (场次ID: {match_id})\n")
            f.write("\n")

    total_slots = best_state.t - 1
    print(
        "[Success] 赛程计算完毕！"
        f"求解器: {solve_info.get('solver', args.solver)}, "
        f"总耗时片: {total_slots}, 结果已保存至 {result_path}"
    )
