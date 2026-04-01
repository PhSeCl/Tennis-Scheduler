from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchedulerConfig:
    """
    调度配置模型：集中管理所有可调参数，避免配置与业务逻辑耦合。
    后续新增参数只需在此扩展，不影响调度引擎的调用链。
    """

    courts: int = 5
    beam_width: int = 10
    w1: float = 10.0
    w2: float = 7.0
    w3: float = 2.5


@dataclass
class Player:
    """
    选手模型：仅暴露核心字段，其他属性以扩展字典保留。
    这样在不修改代码结构的情况下，也能兼容新增字段。
    """

    name: str
    is_staying_at_venue: bool = True
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, key_name: str, data: dict[str, Any]) -> "Player":
        is_staying = bool(data.get("is_staying_at_venue", True))
        extras = dict(data)
        if "name" not in extras:
            extras["name"] = key_name
        return cls(name=key_name, is_staying_at_venue=is_staying, extras=extras)

    def get_str(self, key: str, default: str = "") -> str:
        value = self.extras.get(key, default)
        return value if isinstance(value, str) else default

    def get_list(self, key: str) -> list[Any]:
        value = self.extras.get(key, [])
        return value if isinstance(value, list) else []


@dataclass
class MatchData:
    """
    比赛数据载体：用于承载上游抽签或业务数据，便于后续扩展。
    """

    match_id: int
    event_type: str
    players: list[str] = field(default_factory=list)
    round_name: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
