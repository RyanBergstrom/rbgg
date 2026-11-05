"""Dependency-free reinforcement-learning adapter for Twilight Struggle (experimental groundwork).

Status: groundwork only. The game has not passed the human-playable sign-off (see
``documentation/twilight-struggle/twilight-struggle-ai-analysis.md``), so nothing here is a training
claim. The adapter exists so the action/observation contracts can be tested and measured early.

Decision model
--------------
A turn is split into sequential sub-decisions (playbook section 5) so the fixed action space stays small
while every mask is built from the engine's own legality checks:

* root: pick a card and how to use it (event / influence / coup / realignment), a headline card,
  ``reveal_headlines``, ``finish_turn`` or a KAL-007 bonus action;
* restriction: when Quagmire / Bear Trap binds, pick the Operations card to discard;
* event choice: pick one of the generator's candidate choice payloads (slot index);
* targets: influence places one point per decision (``DONE`` ends early), coup picks one country,
  realignment picks up to ``ops`` targets (``DONE`` ends early).

Known restrictions of the action space (each is a subset of what the engine would accept):

* event choices come from ``default_choices.candidate_choices`` (representative, not exhaustive),
  truncated to ``CHOICE_SLOTS``; a play whose bare event is valid is applied with no choices;
* a mandatory opponent event played for Ops resolves with the first valid default choice;
* realignment targets must contain opponent influence at the start of the action;
* The China Card is not offered because the validator does not offer it (``_move_matches_card``
  requires the card to be in a hand);
* dice are always server-side; masks never depend on a future roll (the Quagmire/Bear Trap roll is
  applied by the engine after the discard is chosen).

Known information leak (documented, small): the second headline commit is masked using the opponent's
committed headline (``validator._headline_pair_playable``). Everything else uses only public state and the
actor's own hand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.rl_adapter import RLAdapter
from app.core.rng import create_rng
from app.games.twilight_struggle.actions import effective_operations_value
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.default_choices import candidate_choices
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.operations import _nato_protected
from app.games.twilight_struggle.rules import (
    _validate_defcon_region_action,
    controlled_by,
    influence_operation_cost,
)
from app.games.twilight_struggle.state import create_initial_game_data
from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
from app.games.twilight_struggle.turns import action_round_limit
from app.games.twilight_struggle.validator import TwilightStruggleValidator

OBSERVATION_SCHEMA_VERSION = 1

CARD_COUNT = 110
CHOICE_SLOTS = 32
# Board spaces that hold influence (the reference data also lists non-board entries such as "China").
COUNTRY_NAMES: tuple[str, ...] = tuple(sorted(create_initial_game_data(0)["countries"]))
COUNTRY_INDEX = {name: index for index, name in enumerate(COUNTRY_NAMES)}
COUNTRY_COUNT = len(COUNTRY_NAMES)

# Action ID layout (fixed; never reorder, append new families at the end).
EVENT_BASE = 0
INFLUENCE_BASE = EVENT_BASE + CARD_COUNT
COUP_BASE = INFLUENCE_BASE + CARD_COUNT
REALIGN_BASE = COUP_BASE + CARD_COUNT
HEADLINE_BASE = REALIGN_BASE + CARD_COUNT
DISCARD_BASE = HEADLINE_BASE + CARD_COUNT
COUNTRY_BASE = DISCARD_BASE + CARD_COUNT
DONE = COUNTRY_BASE + COUNTRY_COUNT
CHOICE_BASE = DONE + 1
REVEAL = CHOICE_BASE + CHOICE_SLOTS
FINISH_TURN = REVEAL + 1
KAL_INFLUENCE = FINISH_TURN + 1
KAL_REALIGN = KAL_INFLUENCE + 1
ACTION_COUNT = KAL_REALIGN + 1

STAGE_ROOT = 0
STAGE_EVENT_CHOICE = 1
STAGE_RESTRICT_DISCARD = 2
STAGE_INFLUENCE = 3
STAGE_COUP = 4
STAGE_REALIGN = 5
STAGE_KAL_INFLUENCE = 6
STAGE_KAL_REALIGN = 7
STAGE_NAMES = (
    "root", "event_choice", "restrict_discard", "influence", "coup", "realignment",
    "kal_influence", "kal_realignment",
)

_HOW_BASES = {"event": EVENT_BASE, "influence": INFLUENCE_BASE, "coup": COUP_BASE, "realignment": REALIGN_BASE}
_PHASES = ("headline", "headline_reveal_ready", "action_round", "turn_end", "game_over")

PERSISTENT_FLAGS = (
    "action_restriction", "arab_israeli_war", "arab_israeli_war_cancelled", "awacs_sale_played",
    "brezhnev_doctrine", "containment", "flower_power", "flower_power_cancelled", "formosan_resolution",
    "iranian_hostage_crisis", "kal_007_bonus", "marshall_plan", "missile_envy", "nato", "norad",
    "north_sea_oil", "red_scare_purge", "reformer", "salt_negotiations", "samantha_yuri",
    "shuttle_diplomacy", "socialist_governments_cancelled", "solidarity_enabled",
    "tear_down_this_wall", "vietnam_revolts", "we_will_bury_you",
)

_HEADER = 24
_PER_COUNTRY = 7
OBSERVATION_SIZE = (
    _HEADER
    + len(_PHASES) + len(STAGE_NAMES) + CARD_COUNT          # phase, stage, pending card
    + COUNTRY_COUNT * _PER_COUNTRY
    + 3 * CARD_COUNT                                          # own hand, public discard, removed
    + len(PERSISTENT_FLAGS) + 1                               # flags + count of unknown flags
)

VP_REWARD_SCALE = 1.0 / 20.0
DEFAULT_PLAYERS = ("player_1", "player_2")  # US, USSR (validator convention)


def card_index(card_id: int) -> int:
    return card_id - 1


def describe_action(action_id: int) -> str:
    """Human-readable label for logs and failure messages."""
    for name, base, size in (
        ("event", EVENT_BASE, CARD_COUNT), ("influence", INFLUENCE_BASE, CARD_COUNT),
        ("coup", COUP_BASE, CARD_COUNT), ("realignment", REALIGN_BASE, CARD_COUNT),
        ("headline", HEADLINE_BASE, CARD_COUNT), ("discard", DISCARD_BASE, CARD_COUNT),
    ):
        if base <= action_id < base + size:
            return f"{name}:card{action_id - base + 1}"
    if COUNTRY_BASE <= action_id < COUNTRY_BASE + COUNTRY_COUNT:
        return f"country:{COUNTRY_NAMES[action_id - COUNTRY_BASE]}"
    if CHOICE_BASE <= action_id < CHOICE_BASE + CHOICE_SLOTS:
        return f"choice:{action_id - CHOICE_BASE}"
    return {DONE: "done", REVEAL: "reveal", FINISH_TURN: "finish_turn",
            KAL_INFLUENCE: "kal_influence", KAL_REALIGN: "kal_realignment"}.get(action_id, f"unknown:{action_id}")


@dataclass
class _Pending:
    stage: int
    card_id: int | None = None
    how: str = ""
    fragment: dict[str, Any] = field(default_factory=dict)
    discard_id: int | None = None
    ops: int = 0
    board: dict[str, dict[str, int]] | None = None
    spent: int = 0
    placements: list[dict[str, Any]] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    valid_slots: list[int] = field(default_factory=list)
    reachable: list[str] = field(default_factory=list)
    base: dict[str, Any] | None = None  # game data after a mandatory event; Ops targets are chosen against it


def _superpower_adjacent(data: dict[str, Any], faction: str) -> set[str]:
    name = "United States" if faction == "us" else "USSR"
    return {edge[0] if edge[1] == name else edge[1] for edge in data["superpower_adjacency"] if name in edge}


def _restriction(gd: dict[str, Any], faction: str) -> dict[str, Any] | None:
    restriction = (gd.get("persistent_events") or {}).get("action_restriction")
    if isinstance(restriction, dict) and restriction.get("faction") == faction:
        return restriction
    return None


@dataclass
class TwilightStruggleReferenceEnv(RLAdapter):
    """In-memory reference environment; one policy decision per ``step``."""

    seed: int = 42
    player_ids: tuple[str, str] = DEFAULT_PLAYERS
    validator: TwilightStruggleValidator | None = None
    state: dict[str, Any] | None = None
    pending: _Pending | None = None

    def __post_init__(self) -> None:
        self.validator = self.validator or TwilightStruggleValidator()
        self._data = load_country_data()
        self._version = 0
        self._options_cache: tuple[int, dict[int, tuple[Any, ...]]] | None = None

    # ----- protocol surface -------------------------------------------------------------------
    @property
    def action_count(self) -> int:
        return ACTION_COUNT

    @property
    def observation_size(self) -> int:
        return OBSERVATION_SIZE

    @property
    def game_data(self) -> dict[str, Any]:
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        return self.state["game_data"]

    @property
    def current_player(self) -> str:
        return self.game_data["current_player"]

    @property
    def stage(self) -> int:
        return self.pending.stage if self.pending else STAGE_ROOT

    def faction_of(self, player_id: str) -> str:
        return self.game_data["faction_by_player"][player_id]

    def is_terminal(self) -> bool:
        gd = self.game_data
        return bool(gd.get("game_over")) or gd.get("current_phase") == "game_over" or gd.get("terminal_result") is not None

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        if seed is not None:
            self.seed = seed
        self.state = {
            "players": [{"player_id": pid} for pid in self.player_ids],
            "game_data": self.validator.initial_game_data(self.seed, list(self.player_ids)),
        }
        self.pending = None
        self._touch()
        return self.observe(self.current_player)

    def _touch(self) -> None:
        self._version += 1
        self._options_cache = None

    def action_mask(self, player_id: str | None = None) -> list[int]:
        actor = player_id or self.current_player
        mask = [0] * ACTION_COUNT
        if actor == self.current_player and not self.is_terminal():
            for action_id in self._options():
                mask[action_id] = 1
        return mask

    def legal_moves(self, player_id: str | None = None) -> list[dict[str, Any]]:
        actor = player_id or self.current_player
        if actor != self.current_player or self.is_terminal():
            return []
        return [
            {"action_id": action_id, "stage": STAGE_NAMES[self.stage], "label": describe_action(action_id)}
            for action_id in sorted(self._options())
        ]

    # ----- option construction ----------------------------------------------------------------
    def _options(self) -> dict[int, tuple[Any, ...]]:
        if self._options_cache is not None and self._options_cache[0] == self._version:
            return self._options_cache[1]
        options = self._root_options() if self.pending is None else self._stage_options(self.pending)
        self._options_cache = (self._version, options)
        return options

    def _hand(self, faction: str) -> list[dict[str, Any]]:
        return self.game_data.get("hands", {}).get(faction, [])

    def _event_candidates(self, gd: dict[str, Any], card: dict[str, Any], faction: str) -> list[dict[str, Any]]:
        fragments = [{"event_choices": choice} for choice in candidate_choices(gd, card, faction)]
        if card["id"] == 46:
            fragments += [{"chosen_defcon": level} for level in range(1, 6)]
        return fragments[:CHOICE_SLOTS]

    def _simulate_event(
        self, gd: dict[str, Any], card: dict[str, Any], faction: str, mode: str, fragment: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Resolve the card's event on a copy exactly as play would (card leaves the hand first)."""
        trial = deepcopy(gd)
        hand = trial["hands"][faction]
        index = next((i for i, c in enumerate(hand) if c.get("id") == card["id"]), None)
        if index is None:
            return None
        hand.pop(index)
        try:
            return resolve_card_event(
                trial, card, faction, mode=mode, trigger_own_event=False, country_data=self._data,
                rng=create_rng(gd.get("rng_seed", 42), gd.get("rng_state_json", "{}")),
                chosen_defcon=fragment.get("chosen_defcon"), event_choices=fragment.get("event_choices"),
            )
        except (KeyError, TypeError, ValueError, StopIteration):
            return None

    def _event_valid(self, gd: dict[str, Any], card: dict[str, Any], faction: str, fragment: dict[str, Any]) -> bool:
        if card["id"] == 46 and fragment.get("chosen_defcon") is None:
            return False
        return self._simulate_event(gd, card, faction, "event", fragment) is not None

    def _event_playable(self, gd: dict[str, Any], card: dict[str, Any], faction: str) -> bool:
        if self._event_valid(gd, card, faction, {}):
            return True
        return any(self._event_valid(gd, card, faction, fragment) for fragment in self._event_candidates(gd, card, faction))

    def _ops_context(self, gd: dict[str, Any], card: dict[str, Any], faction: str) -> dict[str, Any] | None:
        """Resolve the mandatory event (if any) of an Ops play with the first valid default choice.

        Returns the choice payload, the game data after the event (Ops targets are chosen against it, as in
        play: the event resolves publicly first), and whether the Ops are skipped (terminal event, Grain Sales).
        """
        fragments: list[dict[str, Any]] = [{}]
        fragments += [{"event_choices": choice} for choice in candidate_choices(gd, card, faction)]
        if card["id"] == 46:
            fragments += [{"chosen_defcon": level} for level in (5, 4, 3, 2, 1)]  # never default to nuclear war first
        for fragment in fragments[: CHOICE_SLOTS + 6]:
            event = self._simulate_event(gd, card, faction, "operations", fragment)
            if event is not None:
                skip = event.get("terminal_result") is not None or bool(event.get("ops_skipped"))
                return {"fragment": fragment, "post": event["game_data"], "skip": skip}
        return None

    def _coup_targets(self, gd: dict[str, Any], faction: str) -> list[str]:
        opponent = "ussr" if faction == "us" else "us"
        defcon = gd["tracks"]["defcon"]
        reformer = bool((gd.get("persistent_events") or {}).get("reformer"))
        board = gd.get("countries", {})
        out = []
        for name in COUNTRY_NAMES:
            info = self._data["countries"][name]
            if not isinstance(info["stability"], int) or board.get(name, {}).get(opponent, 0) <= 0:
                continue
            try:
                _validate_defcon_region_action(info["region"], defcon)
            except ValueError:
                continue
            if faction == "ussr" and (_nato_protected(gd, name, self._data) or (reformer and info["region"] == "Europe")):
                continue
            if faction == "ussr" and name == "Japan" and (gd.get("persistent_events") or {}).get("us_japan_pact"):
                continue
            out.append(name)
        return out

    def _realign_targets(self, gd: dict[str, Any], faction: str) -> list[str]:
        opponent = "ussr" if faction == "us" else "us"
        defcon = gd["tracks"]["defcon"]
        board = gd.get("countries", {})
        out = []
        for name in COUNTRY_NAMES:
            info = self._data["countries"][name]
            if board.get(name, {}).get(opponent, 0) <= 0:
                continue
            try:
                _validate_defcon_region_action(info["region"], defcon)
            except ValueError:
                continue
            if faction == "ussr" and _nato_protected(gd, name, self._data):
                continue
            if faction == "ussr" and name == "Japan" and (gd.get("persistent_events") or {}).get("us_japan_pact"):
                continue
            out.append(name)
        return out

    def _influence_reachable(self, gd: dict[str, Any], faction: str) -> list[str]:
        adjacency = self._data["adjacency"]
        board = self.game_data.get("countries", {})
        edge = _superpower_adjacent(self._data, faction)
        persistent = self.game_data.get("persistent_events") or {}
        chernobyl = persistent.get("chernobyl")
        blocked_region = (
            chernobyl.get("region")
            if faction == "ussr" and isinstance(chernobyl, dict)
            and chernobyl.get("expires_turn") == self.game_data.get("turn", 1)
            else None
        )
        return [
            name for name in COUNTRY_NAMES
            if self._data["countries"][name].get("region") != blocked_region
            and (name in edge or board[name].get(faction, 0) > 0
            or any(board.get(neighbor, {}).get(faction, 0) > 0 for neighbor in adjacency.get(name, ())))
        ]

    def _restricted_state(self, gd: dict[str, Any], faction: str, card: dict[str, Any]) -> tuple[str, list[int]]:
        """Return ("free"|"scoring_only"|"burn"|"discard", eligible discard ids)."""
        restriction = _restriction(gd, faction)
        if restriction is None or card.get("scoring"):
            return "free", []
        if restriction.get("scoring_only"):
            return "scoring_only", []
        eligible = [
            c["id"] for c in self._hand(faction)
            if c["id"] != card["id"] and not c.get("scoring")
            and isinstance(c.get("operations"), int) and c["operations"] >= 2
        ]
        return ("discard", eligible) if eligible else ("burn", [])

    def _root_options(self) -> dict[int, tuple[Any, ...]]:
        state, gd = self.state, self.game_data
        actor = self.current_player
        faction = self.faction_of(actor)
        phase = gd.get("current_phase")
        options: dict[int, tuple[Any, ...]] = {}
        # Existing 781-action checkpoints have no crisis-cancellation action. Ignore it rather than
        # treating this card-free move as a card/headline and changing the established action layout.
        legal = [
            move for move in self.validator.get_legal_moves(state, actor)
            if move["type"] != "cancel_cuban_missile_crisis"
        ]
        if phase == "headline":
            for move in legal:
                options[HEADLINE_BASE + card_index(move["card_id"])] = ("move", move)
            return options
        if phase == "headline_reveal_ready":
            return {REVEAL: ("move", move) for move in legal}
        if phase == "turn_end":
            # The RL action space has no held-card discard (Space Race box 6); the agent always keeps it.
            return {
                FINISH_TURN: ("move", move) for move in legal
                if move["type"] in {"finish_turn", "keep_held_card"}
            }
        if phase != "action_round":
            return options

        for move in legal:
            if move["type"] == "kal_007_bonus":
                options[KAL_INFLUENCE] = ("kal", "influence")
                if self._realign_targets(gd, faction):
                    options[KAL_REALIGN] = ("kal", "realignment")
                continue
            card = next((c for c in self._hand(faction) if c["id"] == move["card_id"]), None)
            if card is None:
                continue
            kind, _eligible = self._restricted_state(gd, faction, card)
            if kind == "scoring_only":
                continue
            if kind == "discard" and not self.validator._random_draws_resolvable(gd, card, faction):
                # The restriction roll consumes the RNG before this card's random draw, so which card
                # Five Year Plan hits is unknowable at mask time. Offer it only when every possible hit resolves.
                continue
            if kind == "burn":
                # Events that require choices (e.g. Aldrich Ames Remix needs a US card discard)
                # cannot be resolved under restriction. Skip the option; the card can't be
                # played for event while burned.
                if not self._event_valid(gd, card, faction, {}):
                    continue
                options[EVENT_BASE + card_index(card["id"])] = ("play", card["id"], "event")
                continue
            if "event" in move["modes"] and self._event_playable(gd, card, faction):
                options[EVENT_BASE + card_index(card["id"])] = ("play", card["id"], "event")
            if "operations" in move["modes"]:
                context = self._ops_context(gd, card, faction)
                if context is None:
                    continue
                options[INFLUENCE_BASE + card_index(card["id"])] = ("play", card["id"], "influence")
                if context["skip"]:
                    continue
                post = context["post"]
                if self._coup_targets(post, faction):
                    options[COUP_BASE + card_index(card["id"])] = ("play", card["id"], "coup")
                if self._realign_targets(post, faction):
                    options[REALIGN_BASE + card_index(card["id"])] = ("play", card["id"], "realignment")
        return options

    def _remaining(self, pending: _Pending) -> int:
        return pending.ops - pending.spent

    def _placeable(self, pending: _Pending, faction: str) -> list[str]:
        remaining = self._remaining(pending)
        out = []
        for name in pending.reachable:
            cost = influence_operation_cost(faction, pending.board[name], self._data["countries"][name])
            if cost <= remaining:
                out.append(name)
        return out

    def _stage_options(self, pending: _Pending) -> dict[int, tuple[Any, ...]]:
        faction = self.faction_of(self.current_player)
        stage = pending.stage
        if stage == STAGE_EVENT_CHOICE:
            return {CHOICE_BASE + slot: ("choice", slot) for slot in pending.valid_slots}
        if stage == STAGE_RESTRICT_DISCARD:
            eligible = self._restricted_state(self.game_data, faction, self._card(faction, pending.card_id))[1]
            return {DISCARD_BASE + card_index(cid): ("discard", cid) for cid in eligible}
        if stage in (STAGE_INFLUENCE, STAGE_KAL_INFLUENCE):
            options = {COUNTRY_BASE + COUNTRY_INDEX[name]: ("place", name) for name in self._placeable(pending, faction)}
            if pending.placements:
                options[DONE] = ("done",)
            return options
        if stage == STAGE_COUP:
            return {COUNTRY_BASE + COUNTRY_INDEX[name]: ("coup", name) for name in pending.reachable}
        if stage in (STAGE_REALIGN, STAGE_KAL_REALIGN):
            options = {}
            if len(pending.targets) < pending.ops:
                options = {COUNTRY_BASE + COUNTRY_INDEX[name]: ("target", name) for name in pending.reachable}
            if pending.targets:
                options[DONE] = ("done",)
            return options
        return {}

    def _card(self, faction: str, card_id: int | None) -> dict[str, Any]:
        return next(c for c in self._hand(faction) if c["id"] == card_id)

    # ----- stepping ---------------------------------------------------------------------------
    def step(self, action_id: int) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        if not isinstance(action_id, int) or not 0 <= action_id < ACTION_COUNT:
            raise ValueError(f"action must be an integer in [0, {ACTION_COUNT})")
        actor = self.current_player
        option = self._options().get(action_id)
        if option is None:
            raise ValueError(f"action {action_id} ({describe_action(action_id)}) is illegal for {actor}")
        faction = self.faction_of(actor)
        vp_before = self._vp_for(faction)
        completed: dict[str, Any] | None = None

        kind = option[0]
        if kind == "move":
            completed = option[1]
        elif kind == "play":
            completed = self._begin_play(actor, faction, option[1], option[2])
        elif kind == "kal":
            completed = self._begin_kal(faction, option[1])
        else:
            completed = self._advance(actor, faction, option)

        if completed is not None:
            self.pending = None
            try:
                self.state = self.validator.apply_move(self.state, completed)
            except ValueError:
                # Move rejected by validator (e.g. mandatory event resolution changed state,
                # making a previously-valid target invalid). The card is not consumed.
                # Clear pending state so the learner can choose again.
                self._touch()
                done = self.is_terminal()
                reward = 0.0
                info = {"actor": actor, "stage": STAGE_NAMES[self.stage],
                        "move": completed, "rejected": True}
                return self.observe(self.current_player), reward, done, info

        self._touch()
        done = self.is_terminal()
        reward = (self._vp_for(faction) - vp_before) * VP_REWARD_SCALE
        info: dict[str, Any] = {"actor": actor, "stage": STAGE_NAMES[self.stage], "move": completed}
        if done:
            winner = self.validator.check_win(self.state)
            info["winner"] = winner
            info["terminal_result"] = self.game_data.get("terminal_result")
        next_player = self.current_player
        return self.observe(next_player), reward, done, info

    def _vp_for(self, faction: str) -> float:
        vp = self.game_data["tracks"]["victory_points"]
        return float(vp if faction == "us" else -vp)

    def _move_base(self, actor: str, card_id: int, mode: str, pending: _Pending) -> dict[str, Any]:
        move: dict[str, Any] = {"type": "play_card", "player_id": actor, "card_id": card_id, "mode": mode}
        move.update(pending.fragment)
        if mode == "operations":
            move["trigger_own_event"] = False
        if pending.discard_id is not None:
            move["restriction_discard_id"] = pending.discard_id
        return move

    def _begin_play(self, actor: str, faction: str, card_id: int, how: str) -> dict[str, Any] | None:
        gd = self.game_data
        card = self._card(faction, card_id)
        kind, eligible = self._restricted_state(gd, faction, card)
        pending = _Pending(stage=STAGE_ROOT, card_id=card_id, how=how)
        if kind == "burn":
            # No eligible discard: the engine spends the round without playing the card.
            return {"type": "play_card", "player_id": actor, "card_id": card_id, "mode": "event"}
        if kind == "discard":
            pending.stage = STAGE_RESTRICT_DISCARD
            self.pending = pending
            return None
        return self._enter_main_stage(actor, faction, pending)

    def _enter_main_stage(self, actor: str, faction: str, pending: _Pending) -> dict[str, Any] | None:
        gd = self.game_data
        card = self._card(faction, pending.card_id)
        how = pending.how
        if how == "event":
            if self._event_valid(gd, card, faction, {}):
                return self._move_base(actor, card["id"], "event", pending)
            pending.candidates = self._event_candidates(gd, card, faction)
            pending.valid_slots = [
                slot for slot, fragment in enumerate(pending.candidates)
                if self._event_valid(gd, card, faction, fragment)
            ]
            if len(pending.valid_slots) == 1:  # forced: no decision to make
                pending.fragment = dict(pending.candidates[pending.valid_slots[0]])
                return self._move_base(actor, card["id"], "event", pending)
            pending.stage = STAGE_EVENT_CHOICE
            self.pending = pending
            return None
        context = self._ops_context(gd, card, faction)
        pending.fragment = context["fragment"]
        pending.base = context["post"]
        if context["skip"]:
            pending.how = "influence"
            return self._finish_ops(actor, faction, pending)
        pending.ops = effective_operations_value(pending.base, faction, card)
        return self._enter_ops_stage(actor, faction, pending)

    def _enter_ops_stage(self, actor: str, faction: str, pending: _Pending) -> dict[str, Any] | None:
        gd = pending.base if pending.base is not None else self.game_data
        how = pending.how
        if how == "influence":
            pending.stage = STAGE_INFLUENCE
            pending.board = dict(gd["countries"])
            pending.reachable = self._influence_reachable(gd, faction)
            if not self._placeable(pending, faction):
                return self._finish_ops(actor, faction, pending)
        elif how == "coup":
            pending.stage = STAGE_COUP
            pending.reachable = self._coup_targets(gd, faction)
        else:
            pending.stage = STAGE_REALIGN
            pending.reachable = self._realign_targets(gd, faction)
        self.pending = pending
        return None

    def _begin_kal(self, faction: str, how: str) -> dict[str, Any] | None:
        gd = self.game_data
        pending = _Pending(stage=STAGE_ROOT, how=how, ops=4)
        if how == "influence":
            pending.stage = STAGE_KAL_INFLUENCE
            pending.board = dict(gd["countries"])
            pending.reachable = self._influence_reachable(gd, faction)
            if not self._placeable(pending, faction):
                return self._finish_ops(self.current_player, faction, pending)
        else:
            pending.stage = STAGE_KAL_REALIGN
            pending.reachable = self._realign_targets(gd, faction)
        self.pending = pending
        return None

    def _advance(self, actor: str, faction: str, option: tuple[Any, ...]) -> dict[str, Any] | None:
        pending = self.pending
        kind = option[0]
        if kind == "discard":
            pending.discard_id = option[1]
            return self._enter_main_stage(actor, faction, pending)
        if kind == "choice":
            pending.fragment = dict(pending.candidates[option[1]])
            return self._move_base(actor, pending.card_id, "event", pending)
        if kind == "place":
            name = option[1]
            info = self._data["countries"][name]
            pending.spent += influence_operation_cost(faction, pending.board[name], info)
            updated = dict(pending.board[name])
            updated[faction] = updated.get(faction, 0) + 1
            pending.board = {**pending.board, name: updated}
            pending.placements.append({"country": name, "points": 1})
            if not self._placeable(pending, faction):
                return self._finish_ops(actor, faction, pending)
            return None
        if kind == "coup":
            pending.targets = [option[1]]
            return self._finish_ops(actor, faction, pending)
        if kind == "target":
            pending.targets.append(option[1])
            if len(pending.targets) >= pending.ops:
                return self._finish_ops(actor, faction, pending)
            return None
        if kind == "done":
            return self._finish_ops(actor, faction, pending)
        raise ValueError(f"unhandled option {option!r}")

    def _is_influence_connected(self, board: dict[str, Any], country_name: str, faction: str) -> bool:
        """Mirror the validator's adjacency check for influence placement."""
        data = self._data
        edge = _superpower_adjacent(data, faction)
        if country_name in edge:
            return True
        if board.get(country_name, {}).get(faction, 0) > 0:
            return True
        return any(
            board.get(neighbor, {}).get(faction, 0) > 0
            for neighbor in data["adjacency"].get(country_name, ())
        )

    def _finish_ops(self, actor: str, faction: str, pending: _Pending) -> dict[str, Any]:
        if pending.how in ("influence",):
            # Validate each placement against live state (same board the validator uses).
            board = self.game_data.get("countries", {})
            valid_placements = [
                p for p in pending.placements
                if self._is_influence_connected(board, p.get("country"), faction)
            ]
            action = {"type": "influence", "placements": valid_placements}
        elif pending.how == "coup":
            board = self.game_data.get("countries", {})
            opponent = "ussr" if faction == "us" else "us"
            valid = [t for t in pending.targets if board.get(t, {}).get(opponent, 0) > 0]
            if not valid:
                valid = [t for t in pending.reachable if board.get(t, {}).get(opponent, 0) > 0]
            if not valid:
                return None
            action = {"type": "coup", "country": valid[0]}
        else:
            action = {"type": "realignment", "targets": [{"country": name} for name in pending.targets]}
        if pending.card_id is None:
            return {"type": "kal_007_bonus", "player_id": actor, "operations_action": action}
        move = self._move_base(actor, pending.card_id, "operations", pending)
        move["operations_action"] = action
        return move

    # ----- observation ------------------------------------------------------------------------
    def observe(self, player_id: str, legal_moves: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        del legal_moves
        gd = self.game_data
        faction = self.faction_of(player_id)
        opponent = "ussr" if faction == "us" else "us"
        sign = 1.0 if faction == "us" else -1.0
        tracks = gd["tracks"]
        if self.pending is not None and self.pending.base is not None and self.current_player == player_id:
            tracks = self.pending.base["tracks"]  # a mandatory event already resolved publicly
        turn = gd.get("turn", 1)
        limit = action_round_limit(turn, gd.get("extra_action_rounds", 0))
        actions = gd.get("actions_taken", {})
        china = gd.get("china_card") or {}
        headline = gd.get("headline_cards") or {}
        # Compute pending and can_done before header
        pending = self.pending if self.current_player == player_id else None
        can_done = 1.0 if (pending and pending.stage in (STAGE_INFLUENCE, STAGE_REALIGN, STAGE_KAL_INFLUENCE, STAGE_KAL_REALIGN) and (pending.placements or pending.targets)) else 0.0
        values: list[float] = [
            turn / 10.0,
            min(1.0, actions.get(faction, 0) / limit),
            min(1.0, actions.get(opponent, 0) / limit),
            tracks["defcon"] / 5.0,
            max(-1.0, min(1.0, sign * tracks["victory_points"] / 20.0)),
            tracks["military_operations"][faction] / 5.0,
            tracks["military_operations"][opponent] / 5.0,
            tracks["space_race"][faction] / 8.0,
            tracks["space_race"][opponent] / 8.0,
            1.0 if china.get("owner") == faction else 0.0,
            1.0 if china.get("owner") == opponent else 0.0,
            1.0 if china.get("face_up") else 0.0,
            len(gd.get("draw_pile", [])) / CARD_COUNT,
            len(gd.get("hands", {}).get(faction, [])) / 9.0,
            len(gd.get("hands", {}).get(opponent, [])) / 9.0,
            1.0 if headline.get(faction) is not None else 0.0,
            1.0 if headline.get(opponent) is not None else 0.0,
            1.0 if faction == "us" else 0.0,
            1.0 if self.current_player == player_id else 0.0,
            1.0 if gd.get("extra_action_rounds", 0) else 0.0,
            can_done,  # can_done flag
            0.0, 0.0, 0.0,
        ]
        assert len(values) == _HEADER
        phase = gd.get("current_phase")
        values += [1.0 if phase == name else 0.0 for name in _PHASES]
        stage = pending.stage if pending else STAGE_ROOT
        values += [1.0 if stage == index else 0.0 for index in range(len(STAGE_NAMES))]
        card_one_hot = [0.0] * CARD_COUNT
        if pending is not None and pending.card_id is not None:
            card_one_hot[card_index(pending.card_id)] = 1.0
        values += card_one_hot
        targeted = set(pending.targets) if pending else set()
        targeted |= {p["country"] for p in pending.placements} if pending else set()
        board = pending.board if pending is not None and pending.board is not None else gd["countries"]
        for name in COUNTRY_NAMES:
            info = self._data["countries"][name]
            influence = board[name]
            stability = info["stability"] if isinstance(info["stability"], int) else 0
            controller = controlled_by(influence, info)
            values += [
                min(1.0, influence.get(faction, 0) / 8.0),
                min(1.0, influence.get(opponent, 0) / 8.0),
                1.0 if controller == faction else 0.0,
                1.0 if controller == opponent else 0.0,
                stability / 5.0,
                1.0 if info["battleground"] else 0.0,
                1.0 if name in targeted else 0.0,
            ]
        hand = [0.0] * CARD_COUNT
        for card in gd.get("hands", {}).get(faction, []):
            hand[card_index(card["id"])] = 1.0
        discard = [0.0] * CARD_COUNT
        for card in gd.get("discard_pile", []):
            discard[card_index(card["id"])] = 1.0
        removed = [0.0] * CARD_COUNT
        for card in gd.get("removed_cards", []):
            removed[card_index(card["id"])] = 1.0
        values += hand + discard + removed
        persistent = gd.get("persistent_events") or {}
        values += [1.0 if flag in persistent else 0.0 for flag in PERSISTENT_FLAGS]
        values.append(min(1.0, len([k for k in persistent if k not in PERSISTENT_FLAGS]) / 4.0))
        assert len(values) == OBSERVATION_SIZE, (len(values), OBSERVATION_SIZE)
        return {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "observation": values,
            "action_mask": self.action_mask(player_id),
        }
