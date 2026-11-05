"""Contract tests for the Twilight Struggle RL adapter (experimental groundwork)."""
from __future__ import annotations

import random

import pytest

from app.games.twilight_struggle.rl_adapter import (
    ACTION_COUNT,
    CARD_COUNT,
    CHOICE_BASE,
    CHOICE_SLOTS,
    COUNTRY_BASE,
    COUNTRY_COUNT,
    DISCARD_BASE,
    DONE,
    FINISH_TURN,
    HEADLINE_BASE,
    INFLUENCE_BASE,
    KAL_INFLUENCE,
    KAL_REALIGN,
    OBSERVATION_SIZE,
    REVEAL,
    STAGE_RESTRICT_DISCARD,
    STAGE_ROOT,
    TwilightStruggleReferenceEnv,
    describe_action,
)
from tests.helpers_twilight_replay import fingerprint

MAX_STEPS = 5000


def _legal(env: TwilightStruggleReferenceEnv) -> list[int]:
    return [index for index, flag in enumerate(env.action_mask()) if flag]


def _play(seed: int, rng_seed: int | None = None, stop=None):
    """Random masked playout. Returns (env, outcome, completed (state_before, move) pairs)."""
    env = TwilightStruggleReferenceEnv()
    env.reset(seed)
    rng = random.Random(seed if rng_seed is None else rng_seed)
    completed = []
    for _ in range(MAX_STEPS):
        if env.is_terminal():
            return env, "finished", completed
        if stop is not None and stop(env):
            return env, "stopped", completed
        legal = _legal(env)
        if not legal:
            return env, "stall", completed
        before = env.state
        _, _, _, info = env.step(rng.choice(legal))
        if info["move"] is not None:
            completed.append((before, info["move"]))
    return env, "step_limit", completed


def test_action_layout_is_consistent():
    assert ACTION_COUNT == 781
    assert COUNTRY_COUNT == 84 and CARD_COUNT == 110
    ids = [DONE, REVEAL, FINISH_TURN, KAL_INFLUENCE, KAL_REALIGN]
    assert len(set(ids)) == len(ids)
    assert COUNTRY_BASE + COUNTRY_COUNT == DONE
    assert CHOICE_BASE + CHOICE_SLOTS == REVEAL
    assert all(not describe_action(i).startswith("unknown") for i in range(ACTION_COUNT))


def test_reset_observation_and_mask_shape():
    env = TwilightStruggleReferenceEnv()
    obs = env.reset(1)
    assert len(obs["observation"]) == OBSERVATION_SIZE == env.observation_size
    assert len(obs["action_mask"]) == ACTION_COUNT == env.action_count
    legal = _legal(env)
    assert legal and all(HEADLINE_BASE <= i < HEADLINE_BASE + CARD_COUNT for i in legal)
    assert all(-1.0 <= value <= 1.0 for value in obs["observation"])
    # The non-acting seat sees an empty mask.
    other = "player_1" if env.current_player == "player_2" else "player_2"
    assert sum(env.observe(other)["action_mask"]) == 0


def test_illegal_action_is_rejected():
    env = TwilightStruggleReferenceEnv()
    env.reset(1)
    illegal = next(i for i in range(ACTION_COUNT) if i not in set(_legal(env)))
    with pytest.raises(ValueError):
        env.step(illegal)
    with pytest.raises(ValueError):
        env.step(ACTION_COUNT)


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 5])
def test_every_completed_move_is_accepted_by_the_validator(seed):
    """Mask invariant: each assembled move passes the validator's authoritative check before it is applied.

    Moves that carry a restriction discard are skipped: the validator's gate peeks at the next die roll, which the
    adapter deliberately never does.
    """
    env, outcome, completed = _play(seed)
    assert outcome in {"finished", "stall"}
    assert completed
    for before, move in completed:
        if "restriction_discard_id" in move:
            continue
        assert env.validator.validate_move(before, move), move


def test_random_masked_play_finishes_most_games():
    outcomes = [_play(seed)[1] for seed in range(6)]
    assert outcomes.count("step_limit") == 0
    assert outcomes.count("finished") >= 4, outcomes


def test_same_seed_and_choices_reproduce_the_same_game():
    first, _, _ = _play(3)
    second, _, _ = _play(3)
    assert fingerprint(first.game_data) == fingerprint(second.game_data)


@pytest.mark.parametrize("card_id", [14, 28, 29])
def test_unresolvable_opponent_event_keeps_operations_playable(card_id):
    from copy import deepcopy

    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    env = TwilightStruggleReferenceEnv()
    env.reset(17)
    gd = env.game_data
    data = load_country_data()
    catalog = {card["id"]: card for card in load_standard_card_catalog()}
    card = deepcopy(catalog[card_id])
    faction = "ussr" if card_id == 29 else "us"
    gd["hands"][faction] = [card]
    if card_id == 14:
        for name in ("E. Germany", "Poland", "Czechoslovakia", "Hungary", "Romania", "Bulgaria", "Yugoslavia"):
            gd["countries"][name]["us"] = data["countries"][name]["stability"]
    elif card_id == 28:
        gd["countries"]["France"]["us"] = 1
        gd["countries"]["U.K."]["us"] = 1
        gd["countries"]["Israel"]["us"] = 1
    else:
        gd["turn"] = 10
        for name in ("E. Germany", "Poland", "Czechoslovakia", "Hungary", "Romania", "Bulgaria"):
            gd["countries"][name]["ussr"] = 0

    context = env._ops_context(gd, card, faction)

    assert context is not None
    assert context["skip"] is False
    assert context["fragment"] == {}


def _to_action_round(seed: int, faction: str | None = None):
    def stop(env):
        gd = env.game_data
        return gd.get("current_phase") == "action_round" and (
            faction is None or env.faction_of(env.current_player) == faction
        ) and env.stage == STAGE_ROOT

    env, outcome, _ = _play(seed, stop=stop)
    assert outcome == "stopped"
    return env


def test_observation_and_mask_hide_opponent_hand_and_draw_order():
    env = _to_action_round(2)
    me = env.current_player
    faction = env.faction_of(me)
    opponent = "ussr" if faction == "us" else "us"
    baseline = env.observe(me)

    twin = TwilightStruggleReferenceEnv()
    twin.reset(2)
    gd = env.game_data
    from app.games.twilight_struggle.state_clone import clone_state

    altered = clone_state(gd)
    # Swap one opponent card with one draw-pile card, then reorder the draw pile.
    altered["hands"][opponent][0], altered["draw_pile"][0] = altered["draw_pile"][0], altered["hands"][opponent][0]
    random.Random(0).shuffle(altered["draw_pile"])
    twin.state = {**env.state, "game_data": altered}
    twin.pending = None
    twin._touch()
    assert twin.observe(me) == baseline


def test_observation_hides_the_opponents_committed_headline():
    env = TwilightStruggleReferenceEnv()
    env.reset(4)
    first = env.current_player
    env.step(_legal(env)[0])  # first faction commits a headline
    second = env.current_player
    assert second != first
    baseline = env.observe(second)["observation"]

    from app.games.twilight_struggle.state_clone import clone_state

    altered = clone_state(env.game_data)
    committed_faction = env.faction_of(first)
    hand = altered["hands"][committed_faction]
    current = altered["headline_cards"][committed_faction]
    replacement = next(card["id"] for card in hand if card["id"] != current)
    altered["headline_cards"][committed_faction] = replacement
    twin = TwilightStruggleReferenceEnv()
    twin.reset(4)
    twin.state = {**env.state, "game_data": altered}
    twin.pending = None
    twin._touch()
    assert twin.observe(second)["observation"] == baseline


def test_restricted_faction_must_discard_before_playing():
    env = _to_action_round(5)
    gd = env.game_data
    faction = env.faction_of(env.current_player)
    gd["persistent_events"]["action_restriction"] = {"faction": faction}
    env._touch()
    hand_ids = {card["id"] for card in gd["hands"][faction]}
    influence = [i for i in _legal(env) if INFLUENCE_BASE <= i < INFLUENCE_BASE + CARD_COUNT]
    assert influence
    played = influence[0] - INFLUENCE_BASE + 1
    env.step(influence[0])
    assert env.stage == STAGE_RESTRICT_DISCARD
    options = _legal(env)
    assert options and all(DISCARD_BASE <= i < DISCARD_BASE + CARD_COUNT for i in options)
    eligible = {i - DISCARD_BASE + 1 for i in options}
    assert played not in eligible
    assert eligible <= hand_ids
    assert all(
        next(c for c in gd["hands"][faction] if c["id"] == cid)["operations"] >= 2 for cid in eligible
    )
    discard = min(eligible)
    env.step(DISCARD_BASE + discard - 1)
    for _ in range(20):
        if env.stage == STAGE_ROOT:
            break
        env.step(_legal(env)[0])
    assert env.stage == STAGE_ROOT
    after = env.game_data
    assert discard not in {c["id"] for c in after["hands"][faction]}
    assert discard in {c["id"] for c in after["discard_pile"]}


def test_kal_007_bonus_is_offered_and_consumed():
    env = _to_action_round(6, faction="us")
    gd = env.game_data
    turn = gd["turn"]
    gd["persistent_events"]["kal_007_bonus"] = {"faction": "us", "expires_turn": turn, "operations": 4}
    env._touch()
    legal = _legal(env)
    assert KAL_INFLUENCE in legal
    actions_before = dict(env.game_data["actions_taken"])
    env.step(KAL_INFLUENCE)
    for _ in range(10):
        if env.stage == STAGE_ROOT:
            break
        env.step(_legal(env)[0])
    assert env.stage == STAGE_ROOT
    assert "kal_007_bonus" not in env.game_data["persistent_events"]
    assert env.game_data["actions_taken"] == actions_before  # the bonus does not consume an action round
    assert KAL_REALIGN not in _legal(env)


def test_influence_stage_only_offers_countries_the_engine_accepts():
    env = _to_action_round(7)
    influence = [i for i in _legal(env) if INFLUENCE_BASE <= i < INFLUENCE_BASE + CARD_COUNT]
    env.step(influence[0])
    options = _legal(env)
    assert options
    assert DONE not in options  # at least one placement first
    env.step(options[0])
    if env.stage != STAGE_ROOT:
        assert DONE in _legal(env)
