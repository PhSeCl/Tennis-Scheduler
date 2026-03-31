from __future__ import annotations

from io import StringIO
from typing import Callable, Iterable

import pytest

from cost_evaluator import (
    BackToBackRule,
    EarlyStartRule,
    EmptyCourtRule,
    TennisTournamentEvaluator,
)
from scheduler_engine import MatchNode


@pytest.fixture()
def match_node() -> Callable[..., MatchNode]:
    def _make(
        match_id: int,
        *,
        scheduled_time: int = -1,
        non_staying_count: int | None = None,
        players: Iterable[str] = (),
    ) -> MatchNode:
        node = MatchNode(
            match_id=match_id,
            scheduled_time=scheduled_time,
            non_staying_count=non_staying_count,
        )
        node.potential_players = set(players)
        return node

    return _make


def test_early_start_rule_penalizes_non_staying_in_first_slot(
    match_node: Callable[..., MatchNode],
) -> None:
    rule = EarlyStartRule(weight=3.5)
    match = match_node(1, non_staying_count=2)

    assert rule.evaluate(match=match, t=1, scheduled_matches=[]) == 7.0
    assert rule.evaluate(match=match, t=2, scheduled_matches=[]) == 0.0


def test_back_to_back_rule_penalizes_overlap_with_recent_match(
    match_node: Callable[..., MatchNode],
) -> None:
    rule = BackToBackRule(weight=4.0)
    prev_match = match_node(1, scheduled_time=1, players=("PlayerA", "PlayerB"))
    current_match = match_node(2, players=("PlayerB", "PlayerC"))

    penalty = rule.evaluate(
        match=current_match,
        t=2,
        scheduled_matches=[prev_match],
    )

    assert penalty == 4.0


def test_back_to_back_rule_no_penalty_without_overlap(
    match_node: Callable[..., MatchNode],
) -> None:
    rule = BackToBackRule(weight=4.0)
    prev_match = match_node(1, scheduled_time=1, players=("PlayerA", "PlayerB"))
    current_match = match_node(2, players=("PlayerC", "PlayerD"))

    penalty = rule.evaluate(
        match=current_match,
        t=2,
        scheduled_matches=[prev_match],
    )

    assert penalty == 0.0


def test_back_to_back_rule_accumulates_multiple_previous_matches(
    match_node: Callable[..., MatchNode],
) -> None:
    rule = BackToBackRule(weight=2.5)
    prev_match_1 = match_node(1, scheduled_time=1, players=("PlayerA", "PlayerB"))
    prev_match_2 = match_node(2, scheduled_time=1, players=("PlayerC", "PlayerD"))
    current_match = match_node(3, players=("PlayerA", "PlayerC"))

    penalty = rule.evaluate(
        match=current_match,
        t=2,
        scheduled_matches=[prev_match_1, prev_match_2],
    )

    assert penalty == 5.0


def test_empty_court_rule_penalty() -> None:
    rule = EmptyCourtRule(weight=2.0)

    assert rule.evaluate(total_scheduled_matches=0, current_t=2, n_courts=2) == 4.0
    assert rule.evaluate(total_scheduled_matches=4, current_t=2, n_courts=2) == 0.0


def test_evaluator_aggregates_match_and_global_rules(
    match_node: Callable[..., MatchNode],
) -> None:
    match = match_node(1, non_staying_count=1, players=("PlayerA",))
    prev_match = match_node(2, scheduled_time=1, players=("PlayerA",))

    evaluator = TennisTournamentEvaluator(
        match_rules=[EarlyStartRule(weight=1.0), BackToBackRule(weight=2.0)],
        global_rules=[EmptyCourtRule(weight=3.0)],
    )

    match_penalty = evaluator.match_penalty(
        match=match,
        t=1,
        scheduled_matches=[prev_match],
    )
    global_penalty = evaluator.empty_court_penalty(
        total_scheduled_matches=0,
        current_t=2,
        n_courts=1,
    )

    assert match_penalty == 3.0
    assert global_penalty == 3.0


def test_print_active_rules_outputs_rule_descriptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = TennisTournamentEvaluator(
        match_rules=[EarlyStartRule(weight=1.0)],
        global_rules=[EmptyCourtRule(weight=2.0)],
    )

    buffer = StringIO()
    monkeypatch.setattr("sys.stdout", buffer)

    evaluator.print_active_rules()

    output = buffer.getvalue()
    assert "早场驻地限制" in output
    assert "赛程紧凑度限制" in output


def test_zero_and_negative_weights_edge_cases(
    match_node: Callable[..., MatchNode],
) -> None:
    early_zero = EarlyStartRule(weight=0.0)
    early_negative = EarlyStartRule(weight=-2.0)
    match = match_node(1, non_staying_count=2)

    assert early_zero.evaluate(match=match, t=1, scheduled_matches=[]) == 0.0
    assert early_negative.evaluate(match=match, t=1, scheduled_matches=[]) == -4.0

    empty_zero = EmptyCourtRule(weight=0.0)
    empty_negative = EmptyCourtRule(weight=-1.0)

    assert empty_zero.evaluate(total_scheduled_matches=0, current_t=2, n_courts=1) == 0.0
    assert empty_negative.evaluate(total_scheduled_matches=0, current_t=2, n_courts=1) == -1.0
