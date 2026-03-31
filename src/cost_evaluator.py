from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from scheduler_engine import MatchNode


class CostEvaluator(Protocol):
    # 统一接口：单场惩罚 + 全局惩罚
    def match_penalty(
        self,
        match: "MatchNode",
        t: int,
        scheduled_matches: list["MatchNode"],
    ) -> float:
        ...

    def empty_court_penalty(
        self,
        total_scheduled_matches: int,
        current_t: int,
        n_courts: int,
    ) -> float:
        ...


class MatchRule(ABC):
    # 针对单场比赛的惩罚规则
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def weight(self) -> float:
        ...

    @abstractmethod
    def evaluate(
        self,
        match: "MatchNode",
        t: int,
        scheduled_matches: list["MatchNode"],
    ) -> float:
        ...


class GlobalRule(ABC):
    # 针对全局赛程的惩罚规则
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def weight(self) -> float:
        ...

    @abstractmethod
    def evaluate(
        self,
        total_scheduled_matches: int,
        current_t: int,
        n_courts: int,
    ) -> float:
        ...


class EarlyStartRule(MatchRule):
    # 早场不驻地选手惩罚
    def __init__(self, weight: float) -> None:
        self._weight = weight

    @property
    def name(self) -> str:
        return "早场驻地限制"

    @property
    def description(self) -> str:
        return "避免前一晚不在比赛场地的选手打第一场"

    @property
    def weight(self) -> float:
        return self._weight

    def evaluate(
        self,
        match: "MatchNode",
        t: int,
        scheduled_matches: list["MatchNode"],
    ) -> float:
        if t != 1:
            return 0.0
        non_staying_count = int(match.meta.get("non_staying_count", 0))
        return non_staying_count * self.weight


class BackToBackRule(MatchRule):
    # 连场休息惩罚
    def __init__(self, weight: float) -> None:
        self._weight = weight

    @property
    def name(self) -> str:
        return "连场休息限制"

    @property
    def description(self) -> str:
        return "避免同一个选手连场，保证合理的休息间隔"

    @property
    def weight(self) -> float:
        return self._weight

    def evaluate(
        self,
        match: "MatchNode",
        t: int,
        scheduled_matches: list["MatchNode"],
    ) -> float:
        penalty = 0.0
        for prev_match in scheduled_matches:
            if prev_match.potential_players & match.potential_players:
                rest_time = t - prev_match.scheduled_time
                if rest_time <= 1:
                    penalty += self.weight
        return penalty


class EmptyCourtRule(GlobalRule):
    # 空场惩罚
    def __init__(self, weight: float) -> None:
        self._weight = weight

    @property
    def name(self) -> str:
        return "赛程紧凑度限制"

    @property
    def description(self) -> str:
        return "避免留出空场，确保场地利用率最大化"

    @property
    def weight(self) -> float:
        return self._weight

    def evaluate(
        self,
        total_scheduled_matches: int,
        current_t: int,
        n_courts: int,
    ) -> float:
        capacity = (current_t - 1) * n_courts
        empty_slots = capacity - total_scheduled_matches
        if empty_slots > 0:
            return empty_slots * self.weight
        return 0.0


class TennisTournamentEvaluator:
    """
    网球赛事惩罚评估器（规则引擎化）。
    - Match rules: 早场驻地限制、连场休息限制
    - Global rules: 赛程紧凑度限制
    """

    def __init__(
        self,
        match_rules: list[MatchRule],
        global_rules: list[GlobalRule],
    ) -> None:
        self.match_rules = match_rules
        self.global_rules = global_rules

    def match_penalty(
        self,
        match: "MatchNode",
        t: int,
        scheduled_matches: list["MatchNode"],
    ) -> float:
        # 聚合单场规则
        return sum(
            rule.evaluate(match=match, t=t, scheduled_matches=scheduled_matches)
            for rule in self.match_rules
        )

    def empty_court_penalty(
        self,
        total_scheduled_matches: int,
        current_t: int,
        n_courts: int,
    ) -> float:
        # 聚合全局规则
        return sum(
            rule.evaluate(
                total_scheduled_matches=total_scheduled_matches,
                current_t=current_t,
                n_courts=n_courts,
            )
            for rule in self.global_rules
        )

    def print_active_rules(self) -> None:
        print("已启用规则:")
        for rule in self.match_rules:
            print(f"- {rule.name} (权重: {rule.weight}): {rule.description}")
        for rule in self.global_rules:
            print(f"- {rule.name} (权重: {rule.weight}): {rule.description}")
