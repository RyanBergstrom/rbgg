"""Golden replay: the engine must reproduce recorded games exactly.

Each recorded move must still be accepted by ``validate_move`` and, once applied,
must produce the recorded ``game_data`` fingerprint. A mismatch means a refactor
changed rules behavior or dice; regenerate traces only for intended rule changes
(``python -m tests.helpers_twilight_replay``).
"""
import pytest

from app.games.twilight_struggle.validator import TwilightStruggleValidator
from tests.helpers_twilight_replay import fingerprint, initial_state, load_traces

TRACES = load_traces()


@pytest.mark.parametrize("trace", TRACES, ids=[f"seed{trace['seed']}" for trace in TRACES])
def test_engine_replays_recorded_game_exactly(trace):
    validator = TwilightStruggleValidator()
    state = initial_state(validator, trace["seed"])
    assert fingerprint(state["game_data"]) == trace["fingerprints"][0], "initial state changed"
    for step, move in enumerate(trace["moves"]):
        assert validator.validate_move(state, move), f"seed {trace['seed']} step {step}: move rejected {move}"
        state = validator.apply_move(state, move)
        assert fingerprint(state["game_data"]) == trace["fingerprints"][step + 1], (
            f"seed {trace['seed']} step {step}: state diverged after {move}"
        )


def test_recorded_traces_cover_finished_games():
    assert len(TRACES) >= 8
    assert any(trace["outcome"] == "finished" for trace in TRACES)


def test_shared_reference_data_is_not_mutated_by_play():
    """load_country_data and load_scoring_config return shared objects; play must never write into them."""
    import json

    from app.games.twilight_struggle.country_data import load_country_data
    from app.games.twilight_struggle.scoring import load_scoring_config

    before = json.dumps([load_country_data(), load_scoring_config()], sort_keys=True, default=str)
    validator = TwilightStruggleValidator()
    for trace in TRACES[:4]:
        state = initial_state(validator, trace["seed"])
        for move in trace["moves"]:
            state = validator.apply_move(state, move)
    after = json.dumps([load_country_data(), load_scoring_config()], sort_keys=True, default=str)
    assert before == after


def test_validation_never_mutates_the_input_state():
    """Headline resolution and validation pass game_data without copying; they must not write into it."""
    import json

    validator = TwilightStruggleValidator()
    for trace in TRACES[:3]:
        state = initial_state(validator, trace["seed"])
        for move in trace["moves"]:
            snapshot = json.dumps(state, sort_keys=True, default=str)
            for player_id in ("alice", "bob"):
                validator.get_legal_moves(state, player_id)
            validator.validate_move(state, move)
            assert json.dumps(state, sort_keys=True, default=str) == snapshot, f"input mutated by {move}"
            state = validator.apply_move(state, move)
