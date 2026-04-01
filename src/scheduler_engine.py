from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from cost_evaluator import CostEvaluator


@dataclass(init=False)
class MatchNode:
    """
    单败淘汰赛中的比赛节点（DAG 节点）。
    仅定义数据结构与依赖状态查询，不包含排表调度逻辑。
    """

    match_id: int
    left_prev_match: Optional["MatchNode"]
    right_prev_match: Optional["MatchNode"]
    next_match: Optional["MatchNode"]
    scheduled_time: int
    meta: dict[str, object]
    potential_players: set[str]

    def __init__(
        self,
        match_id: int,
        left_prev_match: Optional["MatchNode"] = None,
        right_prev_match: Optional["MatchNode"] = None,
        next_match: Optional["MatchNode"] = None,
        scheduled_time: int = -1,
        meta: Optional[dict[str, object]] = None,
        non_staying_count: Optional[int] = None,
        potential_players: Optional[set[str]] = None,
    ) -> None:
        self.match_id = match_id
        self.left_prev_match = left_prev_match
        self.right_prev_match = right_prev_match
        self.next_match = next_match
        self.scheduled_time = scheduled_time
        self.meta = meta or {}
        self.potential_players = potential_players or set()
        if non_staying_count is not None:
            self.meta["non_staying_count"] = non_staying_count

    def get_pending_dependencies(self) -> int:
        """
        返回当前比赛尚未打完的前置比赛数量（0 / 1 / 2）。
        规则：前置比赛不为 None 且其 scheduled_time == -1 视为“未决依赖”。
        """
        pending = 0
        if (
            self.left_prev_match is not None
            and self.left_prev_match.scheduled_time == -1
        ):
            pending += 1
        if (
            self.right_prev_match is not None
            and self.right_prev_match.scheduled_time == -1
        ):
            pending += 1
        return pending


@dataclass
class ScheduleState:
    """
    赛程搜索中的“单个宇宙状态”。
    仅包含状态表达与单步转移，不包含任何搜索主循环。
    """

    t: int  # 当前即将安排的时间片（初始为 1）
    all_nodes: dict[int, MatchNode]  # 当前宇宙中的完整比赛 DAG
    ready_match_ids: set[int]  # 当前可被安排的比赛 ID 集合
    scheduled_count: int  # 已安排比赛数量
    cost: float  # 累计惩罚

    def generate_next_state(
        self,
        selected_match_ids: list[int],
        n_courts: int,
        evaluator: CostEvaluator,
    ) -> "ScheduleState":
        """
        基于当前状态，生成“在当前时间片安排 selected_match_ids 后”的下一状态。

        逻辑步骤：
        1) 深拷贝 all_nodes，保证状态隔离
        2) 在新状态安排本时段比赛并累加单场惩罚
        3) 计算并累加全局空场惩罚（使用本次安排后的 scheduled_count）
        4) 时间推进 t += 1
        5) 更新 ready_match_ids（移除已安排 + 拓扑解锁）
        """
        # Step 1: 克隆宇宙（深拷贝保证并行状态互不污染）
        cloned_nodes = deepcopy(self.all_nodes)
        next_state = ScheduleState(
            t=self.t,
            all_nodes=cloned_nodes,
            ready_match_ids=set(self.ready_match_ids),
            scheduled_count=self.scheduled_count,
            cost=self.cost,
        )

        # Step 2: 安排比赛（单场惩罚 + 标记 scheduled_time + 数量计数）
        scheduled_matches = [
            n for n in self.all_nodes.values() if n.scheduled_time != -1
        ]
        for match_id in selected_match_ids:
            match = next_state.all_nodes[match_id]

            next_state.cost += evaluator.match_penalty(
                match=match,
                t=next_state.t,
                scheduled_matches=scheduled_matches,
            )
            match.scheduled_time = next_state.t
            next_state.scheduled_count += 1

        # Step 3: 计算空场惩罚（基于“本次安排完成后”的 scheduled_count）
        next_state.cost += evaluate_empty_court_penalty(
            total_scheduled_matches=next_state.scheduled_count,
            current_t=next_state.t,
            n_courts=n_courts,
            evaluator=evaluator,
        )

        # Step 4: 时间推进
        next_state.t += 1

        # Step 5: 拓扑解锁
        # 5.1 从 ready 集合中移除本时段已安排节点
        next_state.ready_match_ids -= set(selected_match_ids)

        # 5.2 扫描所有未安排节点：凡是依赖已全部满足者，加入 ready
        for node in next_state.all_nodes.values():
            if node.scheduled_time == -1 and node.get_pending_dependencies() == 0:
                next_state.ready_match_ids.add(node.match_id)

        return next_state


def evaluate_empty_court_penalty(
    total_scheduled_matches: int,
    current_t: int,
    n_courts: int,
    evaluator: CostEvaluator,
) -> float:
    return evaluator.empty_court_penalty(
        total_scheduled_matches=total_scheduled_matches,
        current_t=current_t,
        n_courts=n_courts,
    )
