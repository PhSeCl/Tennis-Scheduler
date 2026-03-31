from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from scheduler_engine import MatchNode


@dataclass
class _AdvanceBranch:
    """
    内部中间结构：描述“该签位在当前轮次的晋级来源”。

    - prev_match: 若来源于真实比赛，则指向该比赛节点；若来源于轮空直晋，则为 None。
        - direct_entry_non_staying: 仅当 prev_match is None 时有意义，
            表示该轮空队伍的非驻地惩罚人数。
        - display_name: 当前分支晋级者的人类可读名称。
    """

    prev_match: Optional[MatchNode]
    direct_entry_non_staying: int
    display_name: str
    direct_entry_players: set[str]


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


def _is_bye(players: list[str]) -> bool:
    # 任何一侧出现“轮空”即视为轮空分支
    return any(player == "轮空" for player in players)


def _get_non_staying_count(players: list[str], players_dict: dict) -> int:
    # 统计不驻地选手人数，用于首秀惩罚
    count = 0
    for player_name in players:
        player = players_dict.get(player_name)
        if not player:
            continue
        if not bool(player.get("is_staying_at_venue", True)):
            count += 1
    return count


def _format_team_name(players: list[str]) -> str:
    # 双打使用斜杠连接
    return "/".join(players)


def get_round_name(matches_in_round: int) -> str:
    """根据本轮比赛场次数量生成中文轮次名称。"""
    if matches_in_round == 16:
        return "1/16决赛"
    if matches_in_round == 8:
        return "1/8决赛"
    if matches_in_round == 4:
        return "1/4决赛"
    if matches_in_round == 2:
        return "半决赛"
    if matches_in_round == 1:
        return "决赛"
    return f"第{matches_in_round}轮"


def _get_prefix(start_id: int) -> str:
    prefix_map = {
        1000: "男单",
        2000: "女单",
        3000: "男双",
        4000: "女双",
        5000: "混双",
    }
    return prefix_map.get(start_id, "赛事")


def build_dag_from_json(
    draw_list: list[dict],
    players_dict: dict,
    start_id: int,
) -> tuple[dict[int, MatchNode], dict[int, str]]:
    """
    将抽签 JSON 列表解析为 MatchNode DAG（单打/双打通用）。

    Step 1: 计算规模（基于 draw_list 构建完美二叉树拓扑）
    Step 2: 叶子节点构建（步长为 2 的首轮对阵）
    Step 3: 内部节点构建（两两合并分支，处理轮空首秀惩罚）
    """
    if len(draw_list) % 2 != 0:
        raise ValueError("draw_list 长度必须为偶数（两两成对）")

    first_round_matches = len(draw_list) // 2
    if (
        first_round_matches <= 0
        or (first_round_matches & (first_round_matches - 1)) != 0
    ):
        raise ValueError("首轮场次数必须为 2 的幂")

    # 仅用于阅读与调试
    _ = int(math.log2(first_round_matches)) + 1

    all_nodes: dict[int, MatchNode] = {}
    match_labels: dict[int, str] = {}
    next_match_id = start_id

    # ---------- Step 2: 构建首轮叶子 ----------
    current_round_branches: list[_AdvanceBranch] = []
    round_name = get_round_name(first_round_matches)
    prefix = _get_prefix(start_id)

    for i in range(0, len(draw_list), 2):
        left_players = _extract_players(draw_list[i])
        right_players = _extract_players(draw_list[i + 1])

        left_is_bye = _is_bye(left_players)
        right_is_bye = _is_bye(right_players)

        if left_is_bye and right_is_bye:
            raise ValueError("同一签位两侧不能同时为轮空")

        # 轮空分支：不创建 MatchNode，仅记录直晋选手惩罚
        if left_is_bye or right_is_bye:
            advancing_players = right_players if left_is_bye else left_players
            non_staying = _get_non_staying_count(advancing_players, players_dict)
            current_round_branches.append(
                _AdvanceBranch(
                    prev_match=None,
                    direct_entry_non_staying=non_staying,
                    display_name=_format_team_name(advancing_players),
                    direct_entry_players=set(advancing_players),
                )
            )
            continue

        # 真实首轮比赛
        non_staying_count = _get_non_staying_count(
            left_players, players_dict
        ) + _get_non_staying_count(right_players, players_dict)
        node = MatchNode(
            match_id=next_match_id,
            left_prev_match=None,
            right_prev_match=None,
            non_staying_count=non_staying_count,
        )
        node.potential_players.update(left_players)
        node.potential_players.update(right_players)
        all_nodes[node.match_id] = node
        match_labels[node.match_id] = (
            f"[{prefix} {round_name}] "
            f"{_format_team_name(left_players)} vs {_format_team_name(right_players)}"
        )
        current_round_branches.append(
            _AdvanceBranch(
                prev_match=node,
                direct_entry_non_staying=0,
                display_name=f"场{node.match_id}胜者",
                direct_entry_players=set(),
            )
        )
        next_match_id += 1

    # ---------- Step 3: 构建后续轮次 ----------
    while len(current_round_branches) > 1:
        next_round_branches: list[_AdvanceBranch] = []
        matches_in_round = len(current_round_branches) // 2
        round_name = get_round_name(matches_in_round)
        for i in range(0, len(current_round_branches), 2):
            left_branch = current_round_branches[i]
            right_branch = current_round_branches[i + 1]

            # 轮空直晋来源的选手首秀惩罚在此节点生效
            node_non_staying = (
                left_branch.direct_entry_non_staying
                + right_branch.direct_entry_non_staying
            )

            node = MatchNode(
                match_id=next_match_id,
                left_prev_match=left_branch.prev_match,
                right_prev_match=right_branch.prev_match,
                non_staying_count=node_non_staying,
            )

            potential_players = set()
            if left_branch.prev_match is not None:
                potential_players |= left_branch.prev_match.potential_players
            potential_players |= left_branch.direct_entry_players
            if right_branch.prev_match is not None:
                potential_players |= right_branch.prev_match.potential_players
            potential_players |= right_branch.direct_entry_players
            node.potential_players = potential_players

            if left_branch.prev_match is not None:
                left_branch.prev_match.next_match = node
            if right_branch.prev_match is not None:
                right_branch.prev_match.next_match = node

            all_nodes[node.match_id] = node
            match_labels[node.match_id] = (
                f"[{prefix} {round_name}] "
                f"{left_branch.display_name} vs {right_branch.display_name}"
            )
            next_round_branches.append(
                _AdvanceBranch(
                    prev_match=node,
                    direct_entry_non_staying=0,
                    display_name=f"场{node.match_id}胜者",
                    direct_entry_players=set(),
                )
            )
            next_match_id += 1

        current_round_branches = next_round_branches

    return all_nodes, match_labels
