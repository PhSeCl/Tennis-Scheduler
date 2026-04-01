from __future__ import annotations

import itertools
from abc import ABC, abstractmethod

from constraints import ScheduleConstraint
from cost_evaluator import CostEvaluator
from hooks import SchedulerHook
from models import SchedulerConfig
from scheduler_engine import MatchNode, ScheduleState


class SearchStrategy(ABC):
    """
    搜索策略接口：定义统一的排程入口，便于替换不同算法实现。
    """

    @abstractmethod
    def schedule(
        self,
        initial_nodes: dict[int, MatchNode],
        config: SchedulerConfig,
        evaluator: CostEvaluator,
        constraints: list[ScheduleConstraint] | None,
        hooks: list[SchedulerHook] | None = None,
    ) -> ScheduleState:
        raise NotImplementedError


class BeamSearchStrategy(SearchStrategy):
    """
    束搜索策略：在每个时间片探索有限数量的最优分支。
    """

    def schedule(
        self,
        initial_nodes: dict[int, MatchNode],
        config: SchedulerConfig,
        evaluator: CostEvaluator,
        constraints: list[ScheduleConstraint] | None,
        hooks: list[SchedulerHook] | None = None,
    ) -> ScheduleState:
        if not constraints:
            constraints = []
        if hooks is None:
            hooks = []

        for hook in hooks:
            hook.on_scheduling_start(initial_nodes, config)

        n_courts = config.courts
        beam_width = config.beam_width
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

                # 为确定性，组合输入使用排序后的 ID 列表
                ordered_ready_ids = sorted(state.ready_match_ids)
                valid_combos: list[list[int]] = []
                for i in range(k, 0, -1):
                    for combo in itertools.combinations(ordered_ready_ids, i):
                        combo_list = list(combo)
                        if not all(
                            constraint.is_valid(combo_list, state)
                            for constraint in constraints
                        ):
                            continue
                        valid_combos.append(combo_list)

                    if valid_combos:
                        break

                # 组合过多时按均匀采样裁剪分支
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
        best_state = beam[0]
        for hook in hooks:
            hook.on_scheduling_end(best_state)

        return best_state
