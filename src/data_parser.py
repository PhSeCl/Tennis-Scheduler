from __future__ import annotations

"""
数据解析适配层（Anti-Corruption Layer）。

负责将外部 JSON 抽签数据转换为内部一致的“队伍列表”结构，
从而隔离后续 DAG 构建逻辑与输入格式的耦合。
"""


def _extract_players(draw_item: dict) -> list[str]:
    # 兼容单打/双打的输入格式
    if "players" in draw_item:
        players = draw_item["players"]
        if not isinstance(players, list):
            raise ValueError("draw_item['players'] 必须为列表")
        return players
    if "player" in draw_item:
        return [draw_item["player"]]
    raise KeyError("draw_item 需包含 'player' 或 'players' 键")


def is_bye_team(players: list[str]) -> bool:
    # 任何一侧出现“轮空”即视为轮空分支
    return any(player == "轮空" for player in players)


def parse_draw_to_teams(raw_draw_list: list[dict]) -> list[list[str]]:
    """
    将抽签原始 JSON 列表解析为标准化“队伍列表”。

    - 单打: {"player": "A"} -> ["A"]
    - 双打: {"players": ["A", "B"]} -> ["A", "B"]
    - 轮空: 任何包含 "轮空" 的分支 -> ["轮空"]
    """
    if not isinstance(raw_draw_list, list):
        raise ValueError("draw_list 必须为列表")

    teams: list[list[str]] = []
    for item in raw_draw_list:
        if not isinstance(item, dict):
            raise ValueError("draw_list 中的每个元素必须为字典")
        players = _extract_players(item)
        if is_bye_team(players):
            teams.append(["轮空"])
        else:
            teams.append(players)
    return teams
