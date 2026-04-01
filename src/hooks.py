from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import SchedulerConfig
    from scheduler_engine import MatchNode, ScheduleState


class SchedulerHook(ABC):
    """
    生命周期钩子接口：为排程流程提供可插拔的扩展点。
    """

    def on_scheduling_start(
        self,
        initial_nodes: dict[int, "MatchNode"],
        config: "SchedulerConfig",
    ) -> None:
        pass

    def on_scheduling_end(self, best_state: "ScheduleState") -> None:
        pass


class ConsoleLoggingHook(SchedulerHook):
    """
    控制台日志钩子：在排程开始/结束时输出提示信息。
    """

    def on_scheduling_start(
        self,
        initial_nodes: dict[int, "MatchNode"],
        config: "SchedulerConfig",
    ) -> None:
        total_matches = len(initial_nodes)
        print(
            ">>> [Hook] Scheduling started for "
            f"{total_matches} matches with {config.courts} courts."
        )

    def on_scheduling_end(self, best_state: "ScheduleState") -> None:
        print(
            ">>> [Hook] Scheduling finished with cost="
            f"{best_state.cost}, total slots={best_state.t - 1}."
        )
