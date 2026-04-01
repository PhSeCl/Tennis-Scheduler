from constraints import NoPlayerOverlapConstraint
from cost_evaluator import TennisTournamentEvaluator
from dag_builder import build_dag
from data_parser import parse_draw_to_teams
from models import SchedulerConfig
from search_strategies import BeamSearchStrategy


def _schedule_simple_overlap_case():
    players = {
        "PlayerA": {"is_staying_at_venue": True},
        "PlayerB": {"is_staying_at_venue": True},
        "PlayerC": {"is_staying_at_venue": True},
    }
    draw_event_1 = [
        {"player": "PlayerA", "round": 0},
        {"player": "PlayerB", "round": 0},
    ]
    draw_event_2 = [
        {"player": "PlayerA", "round": 0},
        {"player": "PlayerC", "round": 0},
    ]

    teams_a = parse_draw_to_teams(draw_event_1)
    teams_b = parse_draw_to_teams(draw_event_2)
    nodes_a, _ = build_dag(teams_a, players, start_id=1000)
    nodes_b, _ = build_dag(teams_b, players, start_id=2000)
    all_nodes = {**nodes_a, **nodes_b}

    evaluator = TennisTournamentEvaluator(match_rules=[], global_rules=[])
    strategy = BeamSearchStrategy()
    overlap_constraint = NoPlayerOverlapConstraint()
    config = SchedulerConfig(courts=2, beam_width=5)
    return strategy.schedule(
        initial_nodes=all_nodes,
        config=config,
        evaluator=evaluator,
        constraints=[overlap_constraint],
    )


def test_no_overlapping_players_same_timeslice() -> None:
    best_state = _schedule_simple_overlap_case()

    schedule_by_t: dict[int, list[set[str]]] = {}
    for node in best_state.all_nodes.values():
        schedule_by_t.setdefault(node.scheduled_time, []).append(node.potential_players)

    for t, player_sets in schedule_by_t.items():
        for i, players_i in enumerate(player_sets):
            for players_j in player_sets[i + 1 :]:
                overlap = players_i & players_j
                assert not overlap, f"Overlap at time {t}: {overlap}"


def test_deterministic_scheduling_order() -> None:
    first_run = _schedule_simple_overlap_case()
    second_run = _schedule_simple_overlap_case()

    first_times = {
        node.match_id: node.scheduled_time for node in first_run.all_nodes.values()
    }
    second_times = {
        node.match_id: node.scheduled_time for node in second_run.all_nodes.values()
    }

    assert first_times == second_times
