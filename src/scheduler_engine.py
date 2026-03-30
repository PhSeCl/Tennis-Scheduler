from __future__ import annotations
import itertools
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
        if self.left_prev_match is not None and self.left_prev_match.scheduled_time == -1:
            pending += 1
        if self.right_prev_match is not None and self.right_prev_match.scheduled_time == -1:
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
        # Step 1: 克隆宇宙（核心：深拷贝保证并行状态互不污染）
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


def beam_search_schedule(
    initial_nodes: dict[int, MatchNode],
    n_courts: int,
    evaluator: CostEvaluator,
    beam_width: int = 5,
) -> ScheduleState:
    """
    使用束搜索（Beam Search）生成赛程。
    仅实现主循环，不包含其他外层业务逻辑。
    """
    MAX_BRANCHES_PER_STATE = 30

    # Root State: 初始化 ready 集合（入度为 0）
    initial_ready = {
        match_id
        for match_id, node in initial_nodes.items()
        if node.get_pending_dependencies() == 0
    }

    initial_state = ScheduleState(
        t=1,
        all_nodes=initial_nodes,
        ready_match_ids=initial_ready,
        scheduled_count=0,
        cost=0.0,
    )

    beam = [initial_state]
    total_matches = len(initial_nodes)

    while True:
        # 终止条件：beam 中所有状态都已排完全部比赛
        if all(state.scheduled_count == total_matches for state in beam):
            break

        next_candidates: list[ScheduleState] = []

        for state in beam:
            # 已完成状态直接保留
            if state.scheduled_count == total_matches:
                next_candidates.append(state)
                continue

            # 每个时间片尽量排满，若冲突过多则降级尝试
            k = min(len(state.ready_match_ids), n_courts)

            # 为绝对确定性，组合输入使用排序后的 ID 列表
            ordered_ready_ids = sorted(state.ready_match_ids)
            valid_combos: list[list[int]] = []
            for i in range(k, 0, -1):
                for combo in itertools.combinations(ordered_ready_ids, i):
                    # Hard constraint: 同一时间片内潜在选手不能交叉
                    has_overlap = False
                    for j, match_id_a in enumerate(combo):
                        players_a = state.all_nodes[match_id_a].potential_players
                        for match_id_b in combo[j + 1 :]:
                            players_b = state.all_nodes[match_id_b].potential_players
                            if players_a & players_b:
                                has_overlap = True
                                break
                        if has_overlap:
                            break
                    if has_overlap:
                        continue
                    valid_combos.append(list(combo))

                if valid_combos:
                    break

            if len(valid_combos) > MAX_BRANCHES_PER_STATE:
                step = len(valid_combos) / MAX_BRANCHES_PER_STATE
                valid_combos = [
                    valid_combos[int(j * step)]
                    for j in range(MAX_BRANCHES_PER_STATE)
                ]

            for combo in valid_combos:
                new_state = state.generate_next_state(
                    selected_match_ids=combo,
                    n_courts=n_courts,
                    evaluator=evaluator,
                )
                next_candidates.append(new_state)

        # 确定性排序与剪枝
        next_candidates.sort(
            key=lambda s: (
                s.cost,
                s.t,
                sum(n.scheduled_time * n.match_id for n in s.all_nodes.values()),
            )
        )
        beam = next_candidates[:beam_width]

    # 全局最优解（beam 始终按 key 升序维护）
    return beam[0]
