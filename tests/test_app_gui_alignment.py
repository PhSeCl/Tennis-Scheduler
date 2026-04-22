from __future__ import annotations

from schedule_output import (
    event_display_name,
    event_key_from_draw_file,
    normalize_event_labels,
    serialize_schedule_txt,
    start_id_for_draw_file,
)


def test_gui_recognizes_standard_draw_filenames() -> None:
    assert event_key_from_draw_file("matches/men_singles.json") == "ms"
    assert event_key_from_draw_file("matches/women_singles.json") == "ws"
    assert event_key_from_draw_file("matches/men_doubles.json") == "md"
    assert event_key_from_draw_file("matches/women_doubles.json") == "wd"
    assert event_key_from_draw_file("matches/mixed_doubles.json") == "xd"


def test_gui_recognizes_prefixed_draw_filenames() -> None:
    assert event_key_from_draw_file("matches/jy_men_singles.json") == "ms"
    assert event_key_from_draw_file("matches/jy_women_singles.json") == "ws"
    assert event_key_from_draw_file("matches/jy_men_doubles.json") == "md"
    assert event_key_from_draw_file("matches/jy_mixed_doubles.json") == "xd"


def test_gui_uses_cli_aligned_start_ids_for_known_events() -> None:
    assert start_id_for_draw_file("matches/men_singles.json", 0) == 1000
    assert start_id_for_draw_file("matches/women_singles.json", 1) == 2000
    assert start_id_for_draw_file("matches/men_doubles.json", 2) == 3000
    assert start_id_for_draw_file("matches/women_doubles.json", 3) == 4000
    assert start_id_for_draw_file("matches/mixed_doubles.json", 4) == 5000


def test_gui_assigns_distinct_start_ids_to_multiple_files_of_same_event() -> None:
    assert start_id_for_draw_file("matches/men_singles.json", 0, duplicate_index=0) == 1000
    assert start_id_for_draw_file("matches/jy_men_singles.json", 1, duplicate_index=1) == 11000


def test_gui_uses_human_readable_event_names() -> None:
    assert event_display_name("matches/men_singles.json") == "男单"
    assert event_display_name("matches/women_singles.json") == "女单"
    assert event_display_name("matches/men_doubles.json") == "男双"
    assert event_display_name("matches/women_doubles.json") == "女双"
    assert event_display_name("matches/mixed_doubles.json") == "混双"


def test_schedule_txt_uses_shared_cli_gui_format() -> None:
    output = serialize_schedule_txt(
        total_cost=12.5,
        total_slots=3,
        included_events=["男单", "女单"],
        schedule_by_t={
            "1": [{"match_id": 1001, "label": "[男单] A vs B"}],
            "2": [{"match_id": 2001, "label": "[女单] C vs D"}],
        },
        active_rules=[
            {"name": "规则A", "weight": 1.0, "description": "desc"},
        ],
    )

    assert "排表项目: 男单、女单" in output
    assert "启用规则:" in output
    assert "[时间片 1]" in output
    assert "场地 1: [男单] A vs B (场次ID: 1001)" in output


def test_label_normalization_preserves_round_name() -> None:
    normalized = normalize_event_labels(
        {1001: "[赛事 1/16决赛] A vs B"},
        "matches/men_singles.json",
    )

    assert normalized[1001] == "[男单 1/16决赛] A vs B"
