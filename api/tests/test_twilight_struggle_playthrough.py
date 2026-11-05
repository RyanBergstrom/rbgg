"""Random-bot playthroughs through the validator.

Invariants checked for each seed:
- Every move the validator accepts applies without raising.
- A stall (no legal moves while the game is running) is only allowed when the
  mover still has cards and actions left but every card needs choice input,
  which this random bot does not supply. Any other stall fails the test.

Finishing whole games automatically needs a choice generator; that is not in scope here.
"""
import random

import pytest

from app.games.twilight_struggle.turns import faction_action_limit
from app.games.twilight_struggle.validator import TwilightStruggleValidator
from tests.helpers_twilight_choices import candidate_choices

PLAYERS = ["alice", "bob"]
MAX_STEPS = 4000
VALID_SAMPLE = 3


def _finished(gd):
    return bool(gd.get("game_over")) or gd.get("current_phase") == "game_over" or gd.get("terminal_result") is not None


def _candidates(validator, state, rng):
    """Build concrete moves from legal templates; validate lazily and keep a few valid ones."""
    specs = []
    gd = state["game_data"]
    for player_id in PLAYERS:
        for move in validator.get_legal_moves(state, player_id):
            if move["type"] == "play_card":
                faction = validator._faction(gd, player_id)
                card = next((c for c in gd.get("hands", {}).get(faction, []) if c["id"] == move["card_id"]), None)
                for mode in move["modes"]:
                    if mode == "event":
                        specs.append({"type": "play_card", "player_id": player_id, "card_id": move["card_id"], "mode": "event"})
                        if move["card_id"] == 46:
                            # How I Learned to Stop Worrying needs an explicit DEFCON level (1-5).
                            for level in range(1, 6):
                                specs.append({
                                    "type": "play_card", "player_id": player_id, "card_id": move["card_id"],
                                    "mode": "event", "chosen_defcon": level,
                                })
                        if card is not None:
                            for choices in candidate_choices(gd, card, faction, rng)[:4]:
                                specs.append({
                                    "type": "play_card", "player_id": player_id, "card_id": move["card_id"],
                                    "mode": "event", "event_choices": choices,
                                })
                    else:
                        specs.append({
                            "type": "play_card", "player_id": player_id, "card_id": move["card_id"],
                            "mode": "operations", "operations_action": {"type": "space_race"},
                        })
                        specs.append({
                            "type": "play_card", "player_id": player_id, "card_id": move["card_id"],
                            "mode": "operations", "trigger_own_event": False,
                            "operations_action": {"type": "influence", "placements": []},
                        })
                        # Restricted factions must name a discard; offer each eligible hand card.
                        for discard in gd.get("hands", {}).get(faction, []):
                            if discard["id"] != move["card_id"] and not discard.get("scoring") and discard.get("operations", 0) >= 2:
                                specs.append({
                                    "type": "play_card", "player_id": player_id, "card_id": move["card_id"],
                                    "mode": "operations", "trigger_own_event": False,
                                    "operations_action": {"type": "influence", "placements": []},
                                    "restriction_discard_id": discard["id"],
                                })
            elif move["type"] == "kal_007_bonus":
                specs.append({
                    "type": "kal_007_bonus", "player_id": player_id,
                    "operations_action": {"type": "influence", "placements": []},
                })
            else:
                specs.append(move)
    rng.shuffle(specs)
    valid = []
    for spec in specs:
        if validator.validate_move(state, spec):
            valid.append(spec)
    if not valid:
        # The original bot never supplied choices for mandatory opponent events played for Ops,
        # nor combined those choices with a restriction discard. Try those before declaring a stall.
        for player_id in PLAYERS:
            faction = validator._faction(gd, player_id)
            hand = gd.get("hands", {}).get(faction, [])
            for move in validator.get_legal_moves(state, player_id):
                if move["type"] != "play_card":
                    continue
                card = next(c for c in hand if c["id"] == move["card_id"])
                discards = [None] + [
                    c["id"] for c in hand if c["id"] != card["id"]
                    and not c.get("scoring") and c.get("operations", 0) >= 2
                ]
                for choices in candidate_choices(gd, card, faction):
                    for mode in move["modes"]:
                        for discard in discards:
                            spec = {
                                "type": "play_card", "player_id": player_id, "card_id": card["id"],
                                "mode": mode, "event_choices": choices,
                            }
                            if mode == "operations":
                                spec["operations_action"] = {"type": "influence", "placements": []}
                            if discard is not None:
                                spec["restriction_discard_id"] = discard
                            if validator.validate_move(state, spec):
                                valid.append(spec)
    return valid


def _run(seed):
    """Return ("finished", steps) or ("choice_stall", steps, message). Engine failures raise."""
    validator = TwilightStruggleValidator()
    state = {
        "players": [{"player_id": p} for p in PLAYERS],
        "game_data": validator.initial_game_data(seed, PLAYERS),
    }
    rng = random.Random(seed)
    for step in range(MAX_STEPS):
        gd = state["game_data"]
        if _finished(gd):
            return ("finished", step)
        candidates = _candidates(validator, state, rng)
        if not candidates:
            faction = validator._faction(gd, gd.get("current_player"))
            hand = [c["id"] for c in gd.get("hands", {}).get(faction, [])]
            limit = faction_action_limit(gd, faction)
            spent = gd.get("actions_taken", {}).get(faction, 0)
            message = (
                f"seed {seed} step {step}: phase={gd.get('current_phase')} current={gd.get('current_player')} "
                f"turn={gd.get('turn')} actions={gd.get('actions_taken')} hand={hand}"
            )
            if gd.get("current_phase") == "action_round" and hand and spent < limit:
                return ("choice_stall", step, message)
            pytest.fail("engine stall: " + message)
        # Engine invariant: a move the validator accepts must apply cleanly.
        state = validator.apply_move(state, rng.choice(candidates))
    pytest.fail(f"seed {seed} did not finish or stall within {MAX_STEPS} steps")


@pytest.mark.parametrize("seed", list(range(8)))
def test_random_bot_moves_apply_and_stalls_are_only_choice_input(seed):
    outcome = _run(seed)
    assert outcome[0] in {"finished", "choice_stall"}
    assert outcome[1] > 0


# Floor, not target: raise it as choice generation improves. Measured on 60 seeds on 2026-10-20:
# 45 of 60 finished once the bot also offers Space Race attempts (18 before: with Space Race unsupported the
# bot burned cards into Ops and stalled on choice-heavy hands). 60 seeds, not 20, because 20-seed counts
# swing by a game or two.
MIN_FINISHED_OF_SIXTY = 45


def test_random_bot_finish_rate_meets_floor():
    finished = 0
    for seed in range(60):
        outcome = _run(seed)
        assert outcome[0] in {"finished", "choice_stall"}
        if outcome[0] == "finished":
            finished += 1
    assert finished >= MIN_FINISHED_OF_SIXTY, (
        f"only {finished} of 60 random-bot games finished; floor is {MIN_FINISHED_OF_SIXTY}"
    )
