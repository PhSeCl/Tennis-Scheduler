from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scheduler_engine import ScheduleState


class ScheduleConstraint(ABC):
    """
    硬约束规则接口：用于筛选“必须满足”的排表组合。

    约束层只关心“组合是否可行”，不参与惩罚计算。
    """

    @abstractmethod
    def is_valid(self, combo: list[int], state: "ScheduleState") -> bool:
        raise NotImplementedError


class NoPlayerOverlapConstraint(ScheduleConstraint):
    """
    同一时间片内选手不能同时出现在多场比赛中。
    """

    def is_valid(self, combo: list[int], state: "ScheduleState") -> bool:
        for i, match_id_a in enumerate(combo):
            players_a = state.all_nodes[match_id_a].potential_players
            for match_id_b in combo[i + 1 :]:
                players_b = state.all_nodes[match_id_b].potential_players
                if players_a & players_b:
                    return False
        return True
