"""Dependency-free reference adapter for Lost Cities reinforcement learning.

This module is intentionally separate from the HTTP and persistence layers. It
provides a correctness-first environment contract that can later be wrapped by
PettingZoo without making PettingZoo, Gymnasium, or PyTorch API dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.rl_adapter import RLAdapter
from app.games.lost_cities.validator import (
    COLORS,
    LostCitiesValidator,
    _calculate_expedition_score,
    card_color,
    card_number,
    is_investment,
)

HAND_SIZE = 8
DRAW_PILE_ACTION = HAND_SIZE * 2
ACTION_COUNT = DRAW_PILE_ACTION + 1 + len(COLORS)
LEGACY_OBSERVATION_SIZE = (
    HAND_SIZE * 7
    + 7
    + (2 * len(COLORS) * 3)
    + (len(COLORS) * 8)
)
HAND_SLOT_FEATURES = 16
GLOBAL_FEATURES = 9
COLOR_FEATURES = 23
OBSERVATION_SIZE = (
    HAND_SIZE * HAND_SLOT_FEATURES
    + GLOBAL_FEATURES
    + len(COLORS) * COLOR_FEATURES
)
OBSERVATION_SCHEMA_VERSION = 2
OBSERVATION_SIZES = {1: LEGACY_OBSERVATION_SIZE, 2: OBSERVATION_SIZE}
NUMBERED_VALUES = tuple(range(2, 11))


def action_id_for_move(move: dict[str, Any]) -> int:
    """Map one validator move to a stable fixed action ID.

    Play and discard actions are positional: card identity is deliberately not
    part of the action ID. ``ValueError`` is raised for malformed or
    unsupported moves rather than silently creating an invalid mask.
    """
    move_type = move.get("type")
    if move_type in ("play_expedition", "discard"):
        hand_index = move.get("hand_index")
        if not isinstance(hand_index, int) or not 0 <= hand_index < HAND_SIZE:
            raise ValueError("hand move must contain a valid hand_index")
        return hand_index if move_type == "play_expedition" else HAND_SIZE + hand_index

    if move_type == "draw":
        source = move.get("source")
        if source == "draw_pile":
            return DRAW_PILE_ACTION
        suffix = "_discard"
        if isinstance(source, str) and source.endswith(suffix):
            color = source[: -len(suffix)]
            if color in COLORS:
                return DRAW_PILE_ACTION + 1 + COLORS.index(color)

    raise ValueError(f"unsupported Lost Cities move: {move!r}")


def moves_by_action_id(
    legal_moves: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Build a fail-closed action map and reject duplicate action IDs."""
    mapped: dict[int, dict[str, Any]] = {}
    for move in legal_moves:
        action_id = action_id_for_move(move)
        if action_id in mapped:
            raise ValueError(f"multiple legal moves map to action {action_id}")
        mapped[action_id] = move
    return mapped


def _card_features(card: str | None) -> list[float]:
    """Encode a card as five color bits, investment bit, and value."""
    return list(CARD_FEATURES.get(card, (0.0,) * 7))


CARD_FEATURES = {
    None: (0.0,) * 7,
    **{
        card: tuple(
            1.0 if index == COLORS.index(card_color(card)) else 0.0
            for index in range(5)
        ) + (
            (1.0, 0.0)
            if is_investment(card)
            else (0.0, (card_number(card) or 0) / 10.0)
        )
        for card in (
            f"{short}_{value}"
            for color in COLORS
            for short in [color[0] if color != "white" else "w"]
            for value in ("i", *range(2, 11))
        )
    },
}


def hand_sort_key(card: str) -> tuple[int, int]:
    """Canonical hand order: color, investments first, then ascending value."""
    return COLORS.index(card_color(card)), card_number(card) or 0


def _last_number(cards: list[str]) -> int | None:
    numbers = [card_number(card) for card in cards if card_number(card) is not None]
    return max(numbers, default=None)


def _can_extend(cards: list[str], card: str) -> bool:
    if not cards:
        return True
    if is_investment(card):
        return all(is_investment(existing) for existing in cards)
    last = _last_number(cards)
    return last is None or card_number(card) > last


def _projected_score(cards: list[str], hand_cards: list[str]) -> int:
    """Score if every still-playable hand card of this color were added."""
    projected = list(cards)
    for card in sorted(hand_cards, key=hand_sort_key):
        if _can_extend(projected, card):
            projected.append(card)
    return _calculate_expedition_score(projected)


def _encode_v2(
    game_data: dict[str, Any], player_id: str, opponent_id: str,
) -> list[float]:
    """Per-card and per-color decision features from public information only.

    "Unseen" cards are derived from what the observer can see (own hand, both
    expedition rows, and discard piles), so the opponent's hidden hand and the
    draw-pile order never influence the encoding.
    """
    hand = game_data.get("player_hands", {}).get(player_id, [])
    expeditions = game_data.get("expeditions", {})
    mine = expeditions.get(player_id, {})
    theirs = expeditions.get(opponent_id, {})
    discards = game_data.get("discard_piles", {})
    scores = game_data.get("scores", {})

    visible_numbers = {color: set() for color in COLORS}
    visible_investments = dict.fromkeys(COLORS, 0)
    visible_sources = [hand]
    visible_sources.extend(mine.get(color, []) for color in COLORS)
    visible_sources.extend(theirs.get(color, []) for color in COLORS)
    visible_sources.extend(discards.get(color, []) for color in COLORS)
    for cards in visible_sources:
        for card in cards:
            color = card_color(card)
            if is_investment(card):
                visible_investments[color] += 1
            else:
                visible_numbers[color].add(card_number(card))

    color_info: dict[str, dict[str, Any]] = {}
    for color in COLORS:
        my_cards = mine.get(color, [])
        their_cards = theirs.get(color, [])
        hand_cards = [card for card in hand if card_color(card) == color]
        unseen = [value for value in NUMBERED_VALUES if value not in visible_numbers[color]]
        color_info[color] = {
            "my_cards": my_cards,
            "their_cards": their_cards,
            "my_last": _last_number(my_cards),
            "their_last": _last_number(their_cards),
            "my_score": _calculate_expedition_score(my_cards),
            "their_score": _calculate_expedition_score(their_cards),
            "hand_cards": hand_cards,
            "unseen": unseen,
        }

    values: list[float] = []
    for index in range(HAND_SIZE):
        if index >= len(hand):
            values.extend([0.0] * HAND_SLOT_FEATURES)
            continue
        card = hand[index]
        color = card_color(card)
        info = color_info[color]
        number = card_number(card)
        investment = is_investment(card)
        playable = _can_extend(info["my_cards"], card)
        if investment:
            gap = 0.0
        elif info["my_last"] is not None:
            gap = (number - info["my_last"]) / 10.0
        else:
            gap = (number - 2) / 10.0
        play_delta = (
            _calculate_expedition_score([*info["my_cards"], card]) - info["my_score"]
            if playable
            else 0
        )
        reference = 1 if investment else number
        values.extend((
            1.0,
            *(1.0 if color == other else 0.0 for other in COLORS),
            1.0 if investment else 0.0,
            0.0 if investment else number / 10.0,
            1.0 if playable else 0.0,
            1.0 if info["my_cards"] else 0.0,
            gap,
            play_delta / 50.0,
            1.0 if info["their_cards"] else 0.0,
            1.0 if info["their_cards"] and _can_extend(info["their_cards"], card) else 0.0,
            sum(value > reference for value in info["unseen"]) / 9.0,
            len(info["hand_cards"]) / 8.0,
        ))

    round_number = game_data.get("round", 1)
    my_board = sum(color_info[color]["my_score"] for color in COLORS)
    their_board = sum(color_info[color]["their_score"] for color in COLORS)
    values.extend((
        1.0 if game_data.get("current_phase") == "play_a_card" else 0.0,
        len(game_data.get("draw_pile", [])) / 44.0,
        *(1.0 if round_number == value else 0.0 for value in (1, 2, 3)),
        float(scores.get(player_id, 0)) / 200.0,
        float(scores.get(opponent_id, 0)) / 200.0,
        my_board / 100.0,
        their_board / 100.0,
    ))

    for color in COLORS:
        info = color_info[color]
        unseen = info["unseen"]
        my_last = info["my_last"] or 0
        playable_hand = [card for card in info["hand_cards"] if _can_extend(info["my_cards"], card)]
        pile = discards.get(color, [])
        top = pile[-1] if pile else None
        for cards, last, score in (
            (info["my_cards"], info["my_last"], info["my_score"]),
            (info["their_cards"], info["their_last"], info["their_score"]),
        ):
            values.extend((
                1.0 if cards else 0.0,
                len(cards) / 12.0,
                sum(is_investment(card) for card in cards) / 3.0,
                (last or 0) / 10.0,
                score / 50.0,
            ))
        values.extend((
            len(unseen) / 9.0,
            sum(unseen) / 54.0,
            (3 - visible_investments[color]) / 3.0,
            sum(value > my_last for value in unseen) / 9.0,
            len(info["hand_cards"]) / 8.0,
            sum(card_number(card) or 0 for card in playable_hand) / 54.0,
            _projected_score(info["my_cards"], info["hand_cards"]) / 50.0,
            1.0 if top else 0.0,
            (card_number(top) or 0) / 10.0 if top else 0.0,
            1.0 if top and is_investment(top) else 0.0,
            len(pile) / 12.0,
            1.0 if top and info["my_cards"] and _can_extend(info["my_cards"], top) else 0.0,
            1.0 if top and info["their_cards"] and _can_extend(info["their_cards"], top) else 0.0,
        ))
    return values


def encode_observation(
    state: dict[str, Any], player_id: str,
    legal_moves: list[dict[str, Any]] | None = None,
    version: int = OBSERVATION_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return a fixed-shape, player-relative observation.

    Only the observing player's hand is encoded. Opponent cards and draw-pile
    identities are intentionally excluded. The returned list is suitable for a
    later Gymnasium ``Box`` space, while the mask is suitable for masked policy
    selection. ``version=1`` reproduces the legacy schema for older models.
    """
    if version not in OBSERVATION_SIZES:
        raise ValueError(f"unsupported observation version: {version}")
    game_data = state.get("game_data", {})
    hands = game_data.get("player_hands", {})
    hand = hands.get(player_id, [])
    players = ["player_1", "player_2"]
    opponent_id = next((pid for pid in players if pid != player_id), "player_2")
    expeditions = game_data.get("expeditions", {})
    discards = game_data.get("discard_piles", {})
    scores = game_data.get("scores", {})

    if version == 2:
        values = _encode_v2(game_data, player_id, opponent_id)
        legal = legal_moves if legal_moves is not None else []
        action_mask = [0] * ACTION_COUNT
        for action_id in moves_by_action_id(legal):
            action_mask[action_id] = 1
        return {"schema_version": 2, "observation": values, "action_mask": action_mask}

    values: list[float] = []
    for index in range(HAND_SIZE):
        values.extend(_card_features(hand[index] if index < len(hand) else None))
    values.extend([
        1.0 if game_data.get("current_phase") == "play_a_card" else 0.0,
        1.0 if game_data.get("pending_draw") else 0.0,
        1.0 if game_data.get("current_player") == player_id else 0.0,
        min(1.0, len(game_data.get("draw_pile", [])) / 44.0),
        min(1.0, game_data.get("round", 1) / 3.0),
        float(scores.get(player_id, 0)) / 200.0,
        float(scores.get(opponent_id, 0)) / 200.0,
    ])

    # Public expedition summary: card count, investment count, highest number.
    for pid in (player_id, opponent_id):
        for color in COLORS:
            cards = expeditions.get(pid, {}).get(color, [])
            numbers = [card_number(card) for card in cards if card_number(card) is not None]
            values.extend([
                min(1.0, len(cards) / 8.0),
                min(1.0, sum(is_investment(card) for card in cards) / 3.0),
                float(max(numbers, default=0)) / 10.0,
            ])

    # Public discard summary: top card encoding plus normalized pile count.
    for color in COLORS:
        pile = discards.get(color, [])
        values.extend(_card_features(pile[-1] if pile else None))
        values.append(min(1.0, len(pile) / 12.0))

    legal = legal_moves if legal_moves is not None else []
    action_mask = [0] * ACTION_COUNT
    for action_id in moves_by_action_id(legal):
        action_mask[action_id] = 1
    return {
        "schema_version": 1,
        "observation": values,
        "action_mask": action_mask,
    }


def encode_live_state(
    state: dict[str, Any], player_id: str, legal_moves: list[dict[str, Any]],
    version: int = OBSERVATION_SCHEMA_VERSION, validator: LostCitiesValidator | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Encode a live game without mutating it, preserving training slot order.

    Schema v2 is trained with canonically sorted hands. The returned legal move
    list is generated against the copied, sorted state so action IDs and
    observation slots agree. Callers must map the chosen card move back to the
    original live legal move before applying it.
    """
    if version < 2:
        return encode_observation(state, player_id, legal_moves, version), legal_moves

    import copy

    canonical_state = copy.deepcopy(state)
    canonical_game_data = canonical_state.get("game_data", {})
    hands = canonical_game_data.get("player_hands", {})
    for pid, cards in hands.items():
        hands[pid] = sorted(cards, key=hand_sort_key)
    active_validator = validator or LostCitiesValidator()
    canonical_moves = active_validator.get_legal_moves(canonical_state, player_id)
    return encode_observation(canonical_state, player_id, canonical_moves, version), canonical_moves


@dataclass
class LostCitiesReferenceEnv(RLAdapter):
    """Small in-memory reference environment for adapter contract testing."""

    seed: int = 42
    validator: LostCitiesValidator | None = None
    state: dict[str, Any] | None = None
    agents: tuple[str, str] = ("player_1", "player_2")
    starting_player: str = "player_1"
    observation_version: int = OBSERVATION_SCHEMA_VERSION

    @property
    def action_count(self) -> int:
        return ACTION_COUNT

    @property
    def observation_size(self) -> int:
        return OBSERVATION_SIZES[self.observation_version]

    def __post_init__(self) -> None:
        if self.observation_version not in OBSERVATION_SIZES:
            raise ValueError(f"unsupported observation version: {self.observation_version}")
        self.validator = self.validator or LostCitiesValidator()

    def _sort_hands(self) -> None:
        """Give v2 policies a canonical hand order so slot IDs carry meaning."""
        if self.observation_version < 2:
            return
        hands = self.state["game_data"]["player_hands"]
        for player_id, cards in list(hands.items()):
            hands[player_id] = sorted(cards, key=hand_sort_key)

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        """Reset a new episode without persistence, files, or API models."""
        if seed is not None:
            self.seed = seed
        game_data = self.validator.initial_game_data(rng_seed=self.seed)
        if self.starting_player not in self.agents:
            raise ValueError(f"unknown starting player: {self.starting_player}")
        if self.starting_player == "player_2":
            game_data["player_hands"]["player_1"], game_data["player_hands"]["player_2"] = (
                game_data["player_hands"]["player_2"],
                game_data["player_hands"]["player_1"],
            )
            game_data["current_player"] = "player_2"
        self.state = {
            "game_data": game_data,
            "players": [{"player_id": pid} for pid in self.agents],
            "current_player_index": self.agents.index(self.starting_player),
            "rng_seed": self.seed,
            "rng_state_json": game_data.pop("_rng_state_json", "{}"),
        }
        self._sort_hands()
        return self.observe(self.current_player)

    @property
    def current_player(self) -> str:
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        return self.state["game_data"]["current_player"]

    def legal_moves(self, player_id: str | None = None) -> list[dict[str, Any]]:
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        actor = player_id or self.current_player
        return self.validator.get_legal_moves(self.state, actor)

    def observe(
        self,
        player_id: str,
        legal_moves: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        legal = self.legal_moves(player_id) if legal_moves is None else legal_moves
        return encode_observation(self.state, player_id, legal, self.observation_version)

    def step(self, action_id: int) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """Apply one legal action and return next observation, reward, done, info."""
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        if not isinstance(action_id, int) or not 0 <= action_id < ACTION_COUNT:
            raise ValueError(f"action must be an integer in [0, {ACTION_COUNT})")
        actor = self.current_player
        legal = self.legal_moves(actor)
        move = moves_by_action_id(legal).get(action_id)
        if move is None:
            raise ValueError(f"action {action_id} is illegal for {actor}")

        before_score = self.state["game_data"].get("scores", {}).get(actor, 0)
        # The validator already deep-copies game_data before applying a move.
        # Avoid deep-copying the outer training envelope a second time. The
        # reference environment still receives a fresh game_data object and
        # does not mutate self.state in place.
        result = self.validator.apply_move(self.state, move)
        next_state = {
            **self.state,
            **result,
            "game_data": result["game_data"],
        }
        next_state["current_player_index"] = self.agents.index(
            next_state["game_data"].get("current_player", actor)
        )
        self.state = next_state
        self._sort_hands()

        winner = self.validator.check_win(self.state)
        done = winner is not None
        after_score = self.state["game_data"].get("scores", {}).get(actor, 0)
        reward = max(-1.0, min(1.0, (after_score - before_score) / 100.0))
        if done:
            if winner == actor:
                reward = 1.0
            elif winner not in (None, "draw"):
                reward = -1.0
            else:
                reward = 0.0
        next_player = self.current_player
        next_legal = [] if done else self.legal_moves(next_player)
        return self.observe(next_player, next_legal), reward, done, {
            "actor": actor,
            "move": move,
            "winner": winner,
            "final_scores": dict(self.state["game_data"].get("scores", {})),
        }
