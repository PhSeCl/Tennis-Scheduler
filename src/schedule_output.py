from __future__ import annotations

import os
import re
from collections.abc import Iterable


EVENT_START_IDS = {
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


def event_key_from_draw_file(draw_file: str) -> str | None:
    basename = os.path.splitext(os.path.basename(draw_file))[0].lower()
    normalized = re.sub(r"^[a-z0-9]+_", "", basename)

    alias_map = {
        "ms": "ms",
        "men_singles": "ms",
        "male_singles": "ms",
        "ws": "ws",
        "women_singles": "ws",
        "womens_singles": "ws",
        "female_singles": "ws",
        "md": "md",
        "men_doubles": "md",
        "male_doubles": "md",
        "wd": "wd",
        "women_doubles": "wd",
        "womens_doubles": "wd",
        "female_doubles": "wd",
        "xd": "xd",
        "mixed_doubles": "xd",
        "mix_doubles": "xd",
    }
    return alias_map.get(normalized) or alias_map.get(basename)


def start_id_for_draw_file(
    draw_file: str,
    index: int,
    *,
    duplicate_index: int = 0,
) -> int:
    event_key = event_key_from_draw_file(draw_file)
    if event_key is not None:
        return EVENT_START_IDS[event_key] + (duplicate_index * 10000)
    return 6000 + (index * 1000)


def event_display_name(draw_file: str) -> str:
    event_key = event_key_from_draw_file(draw_file)
    if event_key is not None:
        return EVENT_DISPLAY_NAMES[event_key]
    return os.path.splitext(os.path.basename(draw_file))[0]


def normalize_event_labels(
    labels: dict[int, str],
    draw_file: str,
) -> dict[int, str]:
    event_name = event_display_name(draw_file)
    normalized: dict[int, str] = {}

    for match_id, label in labels.items():
        if label.startswith("[") and "]" in label:
            bracket_content, remainder = label[1:].split("]", 1)
            suffix = ""
            if " " in bracket_content:
                _, suffix = bracket_content.split(" ", 1)
                suffix = f" {suffix}"
            normalized[match_id] = f"[{event_name}{suffix}]{remainder}"
        else:
            normalized[match_id] = label

    return normalized


def build_schedule_by_slot(
    all_nodes: dict[int, object],
    all_labels: dict[int, str],
) -> dict[str, list[dict[str, object]]]:
    schedule_by_t: dict[str, list[dict[str, object]]] = {}

    for node in all_nodes.values():
        slot_key = str(node.scheduled_time)
        schedule_by_t.setdefault(slot_key, []).append(
            {
                "match_id": node.match_id,
                "label": all_labels.get(node.match_id, f"[未知] 场次{node.match_id}"),
                "players": sorted(node.potential_players),
            }
        )

    for matches in schedule_by_t.values():
        matches.sort(key=lambda item: item["match_id"])

    return schedule_by_t


def serialize_schedule_txt(
    *,
    total_cost: float | int | None,
    total_slots: int | None,
    included_events: Iterable[str],
    schedule_by_t: dict[str | int, list[dict[str, object]]],
    active_rules: Iterable[dict[str, object]] | None = None,
) -> str:
    lines = [
        "=" * 50,
        "网球赛事极速智能编排结果",
        f"总惩罚分: {total_cost} | 预计完赛总时间片: {total_slots}",
        "排表项目: " + ("、".join(included_events) or "无"),
    ]

    if active_rules:
        lines.append("启用规则:")
        for rule in active_rules:
            lines.append(
                f"  - {rule['name']} (权重: {rule['weight']}): {rule['description']}"
            )

    lines.extend(["=" * 50, ""])

    for t in sorted(schedule_by_t.keys(), key=lambda value: int(value)):
        lines.append(f"[时间片 {t}]")
        matches = schedule_by_t[t]
        for idx, match in enumerate(matches, start=1):
            lines.append(
                f"  - 场地 {idx}: {match.get('label', '')} "
                f"(场次ID: {match.get('match_id', '')})"
            )
        lines.append("")

    return "\n".join(lines)
