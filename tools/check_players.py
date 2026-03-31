"""
网球赛事报名数据合法性校验工具 (Data Gatekeeper)
用于在排表前，提前拦截搭档不匹配、性别错误、单双打逻辑冲突等脏数据。
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Set


def safe_get_str(obj: Dict[str, Any], key: str, default: str = "") -> str:
    value = obj.get(key, default)
    return value if isinstance(value, str) else default


def safe_get_list(obj: Dict[str, Any], key: str) -> List[Any]:
    value = obj.get(key, [])
    return value if isinstance(value, list) else []


def build_event_index(
    registered_events: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {}
    for event in registered_events:
        if not isinstance(event, dict):
            continue
        event_type = safe_get_str(event, "event_type")
        if not event_type:
            continue
        index.setdefault(event_type, []).append(event)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="选手报名数据合法性校验工具")
    parser.add_argument("--players", required=True, help="Path to players.json")
    parser.add_argument(
        "--report", default="data_validation_report.txt", help="输出报告的文件名"
    )
    args = parser.parse_args()

    print(f"正在加载选手数据库: {args.players} ...")
    try:
        with open(args.players, "r", encoding="utf-8") as f:
            players = json.load(f)
            if not isinstance(players, dict):
                players = {}
    except Exception as e:
        print(f"[Error] 无法读取选手文件: {e}")
        sys.exit(1)

    errors: List[str] = []

    # 1) 学号冲突校验
    student_id_map: Dict[str, Set[str]] = {}
    for key_name, info in players.items():
        if not isinstance(info, dict):
            continue
        student_id = safe_get_str(info, "student_id")
        if not student_id:
            continue
        student_id_map.setdefault(student_id, set()).add(key_name)

    for student_id, names in student_id_map.items():
        if len(names) > 1:
            name_list = ", ".join(sorted(names))
            errors.append(
                f'[学号冲突] 发现多个姓名使用同一学号 "{student_id}": {name_list}'
            )

    # 2) 键名一致性校验
    for key_name, info in players.items():
        if not isinstance(info, dict):
            continue
        inner_name = safe_get_str(info, "name")
        if inner_name != key_name:
            errors.append(
                f"[键名不一致] {key_name}: 顶层键名与内部name字段不一致 (name={inner_name})"
            )

    # 构建索引
    player_info: Dict[str, Dict[str, Any]] = {
        name: info for name, info in players.items() if isinstance(info, dict)
    }
    player_events: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for name, info in player_info.items():
        registered_events = safe_get_list(info, "registered_events")
        player_events[name] = build_event_index(
            [e for e in registered_events if isinstance(e, dict)]
        )

    # 3~6) 业务逻辑深度校验
    for name, info in player_info.items():
        sex = safe_get_str(info, "sex")
        registered_events = safe_get_list(info, "registered_events")

        for event in registered_events:
            if not isinstance(event, dict):
                errors.append(
                    f"[字段类型错误] {name}: registered_events 中存在非字典元素"
                )
                continue

            event_type = safe_get_str(event, "event_type")
            partner = safe_get_str(event, "partner")

            # 单双打逻辑
            if "单打" in event_type and partner:
                errors.append(
                    f'[逻辑错误] {name}: 报名了"{event_type}"，却填写了搭档"{partner}"'
                )
            if "双打" in event_type:
                if not partner:
                    errors.append(
                        f'[逻辑错误] {name}: 报名了"{event_type}"，未填写搭档'
                    )
                elif partner == name:
                    errors.append(
                        f'[逻辑错误] {name}: 报名了"{event_type}"，搭档不能是自己'
                    )

            # 搭档存在性与双向奔赴校验
            if partner:
                if partner not in player_info:
                    errors.append(
                        f'[搭档不存在] {name}: 在"{event_type}"的搭档"{partner}"不在总名单中'
                    )
                    continue

                if "双打" in event_type:
                    partner_events = player_events.get(partner, {})
                    reciprocal_events = partner_events.get(event_type, [])
                    if not reciprocal_events:
                        errors.append(
                            f'[搭档单相思] {name}: 搭档填了"{partner}"，但TA根本没报"{event_type}"'
                        )
                    else:
                        matched = any(
                            safe_get_str(e, "partner") == name
                            for e in reciprocal_events
                        )
                        if not matched:
                            errors.append(
                                f'[搭档劈腿] {name}: 搭档填了"{partner}"，但TA的搭档却不是你'
                            )

            # 性别合规性校验
            if "男子" in event_type and sex != "男":
                errors.append(
                    f'[性别不符] {name}: 报名"{event_type}"，但登记性别为"{sex}"'
                )
            if "女子" in event_type and sex != "女":
                errors.append(
                    f'[性别不符] {name}: 报名"{event_type}"，但登记性别为"{sex}"'
                )

            if partner and partner in player_info:
                partner_sex = safe_get_str(player_info[partner], "sex")
                if "男子" in event_type and partner_sex != "男":
                    errors.append(
                        f'[搭档性别不符] {name}: 你的搭档"{partner}"登记性别为"{partner_sex}"'
                    )
                if "女子" in event_type and partner_sex != "女":
                    errors.append(
                        f'[搭档性别不符] {name}: 你的搭档"{partner}"登记性别为"{partner_sex}"'
                    )
                if "混合" in event_type and sex and partner_sex and sex == partner_sex:
                    errors.append(
                        f'[混双性别冲突] {name}: 你与搭档"{partner}"的登记性别同为"{sex}"'
                    )

    # 结果输出
    if errors:
        print(f"\n❌ 校验失败！发现 {len(errors)} 个数据异常！")
        for err in errors[:5]:  # 控制台最多预览5条
            print(f"  {err}")
        if len(errors) > 5:
            print("  ... (更多错误见报告)")

        with open(args.report, "w", encoding="utf-8") as f:
            f.write("\n".join(errors))
        print(f"\n📄 完整错误报告已导出至: {args.report}")
        sys.exit(1)  # 抛出错误状态码，阻断后续排表脚本的执行
    else:
        print("✅ 校验通过！报名数据完美无瑕，可以开始智能排表。")
        with open(args.report, "w", encoding="utf-8") as f:
            f.write("未发现错误。\n")


if __name__ == "__main__":
    main()
