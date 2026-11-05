"""Golden replay traces for the Twilight Struggle engine.

A trace is a seed, the exact sequence of moves the random bot applied, and a
fingerprint of ``game_data`` after every move. Replaying the moves through
``apply_move`` must reproduce every fingerprint, so performance refactors of the
engine are checked for unchanged rules behavior and dice.

Fingerprints project card records to their ids, so storing cards as ids instead
of full records does not change the fingerprint.

Regenerate (only when rules behavior is meant to change):
    python -m tests.helpers_twilight_replay
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "twilight_replays.json"
PLAYERS = ["alice", "bob"]
RECORD_SEEDS = list(range(12))
MAX_STEPS = 4000


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        if "id" in value and "card_face_asset" in value:
            return value["id"]
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def fingerprint(game_data: dict[str, Any]) -> str:
    canonical = json.dumps(_normalize(game_data), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def initial_state(validator, seed: int) -> dict[str, Any]:
    return {
        "players": [{"player_id": player} for player in PLAYERS],
        "game_data": validator.initial_game_data(seed, PLAYERS),
    }


def record_trace(seed: int) -> dict[str, Any]:
    from app.games.twilight_struggle.validator import TwilightStruggleValidator
    from tests.test_twilight_struggle_playthrough import _candidates, _finished

    validator = TwilightStruggleValidator()
    state = initial_state(validator, seed)
    rng = random.Random(seed)
    moves: list[dict[str, Any]] = []
    fingerprints = [fingerprint(state["game_data"])]
    outcome = "step_limit"
    for _ in range(MAX_STEPS):
        if _finished(state["game_data"]):
            outcome = "finished"
            break
        candidates = _candidates(validator, state, rng)
        if not candidates:
            outcome = "stall"
            break
        move = rng.choice(candidates)
        state = validator.apply_move(state, move)
        moves.append(move)
        fingerprints.append(fingerprint(state["game_data"]))
    return {"seed": seed, "outcome": outcome, "moves": moves, "fingerprints": fingerprints}


def load_traces() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def main() -> None:
    traces = []
    for seed in RECORD_SEEDS:
        trace = record_trace(seed)
        traces.append(trace)
        print(f"seed {seed}: {trace['outcome']} after {len(trace['moves'])} moves", flush=True)
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(traces, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
