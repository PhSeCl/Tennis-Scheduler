import pytest

from dag_builder import build_dag
from data_parser import parse_draw_to_teams


def test_build_dag_minimal_single_elimination() -> None:
    players = {
        "PlayerA": {"is_staying_at_venue": True},
        "PlayerB": {"is_staying_at_venue": False},
        "PlayerC": {"is_staying_at_venue": True},
        "PlayerD": {"is_staying_at_venue": False},
    }
    draw = [
        {"player": "PlayerA", "round": 0},
        {"player": "PlayerB", "round": 0},
        {"player": "PlayerC", "round": 0},
        {"player": "PlayerD", "round": 0},
    ]

    teams = parse_draw_to_teams(draw)
    nodes, labels = build_dag(teams, players, start_id=1000)

    # 4 players -> 2 first-round matches + 1 final = 3 nodes
    assert len(nodes) == 3
    assert len(labels) == 3
    assert all(match_id in labels for match_id in nodes)


def test_build_dag_with_bye_branch() -> None:
    players = {
        "PlayerA": {"is_staying_at_venue": True},
        "PlayerB": {"is_staying_at_venue": False},
        "PlayerC": {"is_staying_at_venue": True},
    }
    draw = [
        {"player": "PlayerA", "round": 0},
        {"player": "轮空", "round": 0},
        {"player": "PlayerB", "round": 0},
        {"player": "PlayerC", "round": 0},
    ]

    teams = parse_draw_to_teams(draw)
    nodes, _ = build_dag(teams, players, start_id=1000)

    # One bye -> one first-round match + final = 2 nodes
    assert len(nodes) == 2
    # Final node should include all potential players
    all_potential = set()
    for node in nodes.values():
        all_potential |= node.potential_players
    assert {"PlayerA", "PlayerB", "PlayerC"}.issubset(all_potential)


def test_build_dag_rejects_double_bye() -> None:
    players = {"PlayerA": {"is_staying_at_venue": True}}
    draw = [
        {"player": "轮空", "round": 0},
        {"player": "轮空", "round": 0},
    ]

    with pytest.raises(ValueError):
        teams = parse_draw_to_teams(draw)
        build_dag(teams, players, start_id=1000)
