import json
import os
from typing import Any, Dict, List, Set, Tuple


def safe_get_str(obj: Dict[str, Any], key: str, default: str = "") -> str:
    value = obj.get(key, default)
    return value if isinstance(value, str) else default


def safe_get_list(obj: Dict[str, Any], key: str) -> List[Any]:
    value = obj.get(key, [])
    return value if isinstance(value, list) else []


def load_players(json_path: str) -> Dict[str, Any]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def build_event_index(registered_events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {}
    for event in registered_events:
        if not isinstance(event, dict):
            continue
        event_type = safe_get_str(event, "event_type")
        if not event_type:
            continue
        index.setdefault(event_type, []).append(event)
    return index


def append_error(errors: List[str], msg: str) -> None:
    errors.append(msg)


def main() -> None:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "data", "players.json")
    report_path = os.path.join(base_dir, "data", "results.txt")

    players = load_players(json_path)
    errors: List[str] = []

    # 1) Student ID uniqueness check
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
            append_error(
                errors,
                f"[学号冲突] 发现多个姓名使用同一学号 \"{student_id}\": {name_list}",
            )

    # 2) Key-name consistency check
    for key_name, info in players.items():
        if not isinstance(info, dict):
            continue
        inner_name = safe_get_str(info, "name")
        if inner_name != key_name:
            append_error(
                errors,
                f"[键名不一致] {key_name}: 顶层键名与内部name字段不一致 (name={inner_name})",
            )

    # Build quick lookup for player info and event indices
    player_info: Dict[str, Dict[str, Any]] = {
        name: info for name, info in players.items() if isinstance(info, dict)
    }
    player_events: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for name, info in player_info.items():
        registered_events = safe_get_list(info, "registered_events")
        player_events[name] = build_event_index(
            [e for e in registered_events if isinstance(e, dict)]
        )

    # 3) Partner existence and 4) partner reciprocal check, 5) event/partner logic, 6) sex/event compliance
    for name, info in player_info.items():
        sex = safe_get_str(info, "sex")
        registered_events = safe_get_list(info, "registered_events")

        for event in registered_events:
            if not isinstance(event, dict):
                append_error(
                    errors,
                    f"[字段类型错误] {name}: registered_events 中存在非字典元素",
                )
                continue

            event_type = safe_get_str(event, "event_type")
            partner = safe_get_str(event, "partner")

            # 5) Singles vs doubles partner logic
            if "单打" in event_type:
                if partner != "":
                    append_error(
                        errors,
                        f"[单双打逻辑错误] {name}: 报名了\"{event_type}\"，但填写了搭档\"{partner}\"。",
                    )
            if "双打" in event_type:
                if not partner:
                    append_error(
                        errors,
                        f"[单双打逻辑错误] {name}: 报名了\"{event_type}\"，但未填写搭档。",
                    )
                elif partner == name:
                    append_error(
                        errors,
                        f"[单双打逻辑错误] {name}: 报名了\"{event_type}\"，但搭档填写了自己。",
                    )

            # 3) Partner existence check
            if partner:
                if partner not in player_info:
                    append_error(
                        errors,
                        f"[搭档不存在] {name}: 在\"{event_type}\"中填写搭档\"{partner}\"，但该姓名不存在于报名名单。",
                    )
                    continue

            # 4) Reciprocal partner check for doubles
            if partner and "双打" in event_type and partner in player_info:
                partner_events = player_events.get(partner, {})
                reciprocal_events = partner_events.get(event_type, [])
                if not reciprocal_events:
                    append_error(
                        errors,
                        f"[搭档未双向对应] {name}: 在\"{event_type}\"中搭档填了\"{partner}\"，但\"{partner}\"未报该项目。",
                    )
                else:
                    matched = any(safe_get_str(e, "partner") == name for e in reciprocal_events)
                    if not matched:
                        append_error(
                            errors,
                            f"[搭档未双向对应] {name}: 在\"{event_type}\"中搭档填了\"{partner}\"，但\"{partner}\"的该项目搭档不是\"{name}\"。",
                        )

            # 6) Sex/event compliance check
            if "男子" in event_type:
                if sex != "男":
                    append_error(
                        errors,
                        f"[性别不符] {name}: 报名\"{event_type}\"，但性别为\"{sex}\"。",
                    )
                if partner:
                    partner_sex = safe_get_str(player_info.get(partner, {}), "sex")
                    if partner_sex and partner_sex != "男":
                        append_error(
                            errors,
                            f"[性别不符] {name}: 在\"{event_type}\"中搭档\"{partner}\"性别为\"{partner_sex}\"。",
                        )
            if "女子" in event_type:
                if sex != "女":
                    append_error(
                        errors,
                        f"[性别不符] {name}: 报名\"{event_type}\"，但性别为\"{sex}\"。",
                    )
                if partner:
                    partner_sex = safe_get_str(player_info.get(partner, {}), "sex")
                    if partner_sex and partner_sex != "女":
                        append_error(
                            errors,
                            f"[性别不符] {name}: 在\"{event_type}\"中搭档\"{partner}\"性别为\"{partner_sex}\"。",
                        )
            if "混合双打" in event_type and partner:
                partner_sex = safe_get_str(player_info.get(partner, {}), "sex")
                if sex and partner_sex and sex == partner_sex:
                    append_error(
                        errors,
                        f"[性别不符] {name}: 报名\"{event_type}\"，但与搭档\"{partner}\"性别相同。",
                    )

    # Write report
    if errors:
        content = "\n".join(errors)
    else:
        content = "未发现错误。"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()
