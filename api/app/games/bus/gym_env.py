"""Gymnasium bridge for training one Bus seat against fixed/opponent-pool seats.

The learner controls exactly one seat per episode; all other seats are played
inside ``step`` by fixed policies (and, optionally, frozen model snapshots),
so every reward and value target is from the learner's perspective. Bus
supports 3-5 players, so both the player count and the learner's seat index
are randomized every episode (see ``documentation/rl-game-ai-playbook.md``
section 8.5 and ``documentation/Bus/bus-rl-analysis.md``).

Bus scores are banked immediately (``vrrooomm`` resolution adds +1 to
``score`` right away; there is no provisional/future-value component to
estimate), so the per-step reward is simply the change in the learner's
``adjusted_score = score - time_stones`` minus the mean change across the
other seats (a multiplayer margin-style reward per playbook section 9.4).
"""
from __future__ import annotations

import random
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.games.bus.rl_adapter import ACTION_COUNT, OBSERVATION_SCHEMA_VERSION, BusReferenceEnv, action_id_for_move
from app.games.bus.rl_policies import FIXED_POLICIES

DEFAULT_OPPONENTS = {"rule": 0.6, "random": 0.2, "null": 0.2}
PLAYER_COUNT_CHOICES = (3, 4, 5)


def parse_opponent_mix(spec: str) -> dict[str, float]:
    """Parse ``"rule=0.6,random=0.2,null=0.2"`` into validated weights."""
    weights: dict[str, float] = {}
    for part in spec.split(","):
        name, _, weight = part.strip().partition("=")
        weights[name] = float(weight) if weight else 1.0
    _validate_opponents(weights)
    return weights


def _validate_opponents(weights: dict[str, float]) -> None:
    allowed = {*FIXED_POLICIES, "snapshot"}
    unknown = set(weights) - allowed
    if unknown:
        raise ValueError(f"unknown opponents {sorted(unknown)}; expected {sorted(allowed)}")
    if any(weight < 0 for weight in weights.values()):
        raise ValueError("opponent weights cannot be negative")
    if not any(weight > 0 for name, weight in weights.items() if name != "snapshot"):
        raise ValueError("at least one fixed opponent needs a positive weight")


def _adjusted_scores(game_data: dict[str, Any]) -> dict[str, float]:
    return {
        pid: float(player["score"] - player["time_stones"])
        for pid, player in game_data["players"].items()
    }


class BusGymEnv(gym.Env):
    """One learner seat versus 2-4 in-environment opponent seats."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        seed: int = 42,
        max_episode_steps: int = 3000,
        opponents: dict[str, float] | None = None,
        reward_scale: float = 0.5,
        win_reward: float = 0.0,
        timeout_penalty: float = -0.25,
        player_counts: tuple[int, ...] = PLAYER_COUNT_CHOICES,
        observation_version: int = OBSERVATION_SCHEMA_VERSION,
        random_setup_probability: float = 0.25,
        rule_pass_probability: float = 0.25,
    ):
        super().__init__()
        self.opponents = dict(opponents or DEFAULT_OPPONENTS)
        _validate_opponents(self.opponents)
        if not player_counts or any(count not in PLAYER_COUNT_CHOICES for count in player_counts):
            raise ValueError(f"player_counts must be a subset of {PLAYER_COUNT_CHOICES}")
        self.player_counts = tuple(player_counts)
        self.seed_value = seed
        self.max_episode_steps = max_episode_steps
        self.reward_scale = reward_scale
        self.win_reward = win_reward
        self.timeout_penalty = timeout_penalty
        self.observation_version = observation_version
        if not 0.0 <= random_setup_probability <= 1.0:
            raise ValueError("random_setup_probability must be between 0 and 1")
        if not 0.0 <= rule_pass_probability <= 1.0:
            raise ValueError("rule_pass_probability must be between 0 and 1")
        self.random_setup_probability = random_setup_probability
        self.rule_pass_probability = rule_pass_probability
        self.steps = 0
        self.reward_totals: dict[str, float] = {}
        self.snapshot_paths: list[str] = []
        self._snapshot_selectors: dict[str, Any] = {}
        self._seeded = False
        self._policy_rng = random.Random(seed)
        self.learner = "player_1"
        self.opponent_kinds: dict[str, str] = {}
        self._opponent_selectors: dict[str, Any] = {}
        self._last_adjusted: dict[str, float] = {}
        self.adapter = BusReferenceEnv(seed=seed, observation_version=observation_version)
        self.action_space = spaces.Discrete(ACTION_COUNT)
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(self.adapter.observation_size,), dtype=np.float32,
        )
        self._observation: dict[str, Any] | None = None

    @property
    def adapter_observation(self) -> dict[str, Any]:
        """The learner's current adapter observation (vector plus mask)."""
        if self._observation is None:
            raise RuntimeError("environment must be reset before use")
        return self._observation

    def add_opponent_snapshot(self, path: str, max_snapshots: int = 5) -> int:
        """Register a frozen model snapshot as a possible opponent."""
        if path not in self.snapshot_paths:
            self.snapshot_paths.append(path)
        while len(self.snapshot_paths) > max_snapshots:
            self._snapshot_selectors.pop(self.snapshot_paths.pop(0), None)
        return len(self.snapshot_paths)

    def _snapshot_selector(self, path: str):
        selector = self._snapshot_selectors.get(path)
        if selector is None:
            from sb3_contrib import MaskablePPO

            model = MaskablePPO.load(path, device="cpu")

            def _select(adapter, observation, rng):
                del rng
                action, _ = model.predict(
                    np.asarray(observation["observation"], dtype=np.float32),
                    action_masks=np.asarray(observation["action_mask"], dtype=bool),
                    deterministic=False,
                )
                return int(action)

            selector = _select
            self._snapshot_selectors[path] = selector
        return selector

    def _choose_opponent_kind(self) -> str:
        available = {
            name: weight
            for name, weight in self.opponents.items()
            if weight > 0 and (name != "snapshot" or self.snapshot_paths)
        }
        names = list(available)
        probs = np.array(list(available.values())) / sum(available.values())
        return names[int(self.np_random.choice(len(names), p=probs))]

    def _selector_for_kind(self, kind: str):
        if kind == "snapshot":
            path = self.snapshot_paths[int(self.np_random.integers(len(self.snapshot_paths)))]
            return self._snapshot_selector(path)
        return FIXED_POLICIES[kind]

    def _vector(self, observation: dict[str, Any]) -> np.ndarray:
        return np.asarray(observation["observation"], dtype=np.float32)

    def _play_opponents(self, observation: dict[str, Any]) -> tuple[dict[str, Any], bool, dict[str, Any]]:
        done = False
        info: dict[str, Any] = {}
        while not done and self.adapter.current_player != self.learner and self.steps < self.max_episode_steps:
            actor = self.adapter.current_player
            selector = self._opponent_selectors[self.opponent_kinds[actor]]
            legal = self.adapter.legal_moves(actor)
            phase = self.adapter.state["game_data"].get("current_phase")
            setup_phases = {"SETUP_BUILDINGS", "SETUP_FIRST_ROUTE_SEGMENTS", "SETUP_SECOND_ROUTE_SEGMENTS"}
            if phase in setup_phases and self._policy_rng.random() < self.random_setup_probability:
                action = action_id_for_move(self._policy_rng.choice(legal))
            elif (
                self.opponent_kinds[actor] == "rule"
                and self._policy_rng.random() < self.rule_pass_probability
                and (pass_moves := [move for move in legal if move["type"] == "pass_action_selection"])
            ):
                action = action_id_for_move(pass_moves[0])
            else:
                action = selector(self.adapter, observation, self._policy_rng)
            observation, _, done, info = self.adapter.step(int(action))
            self.steps += 1
        return observation, done, info

    def reset(self, *, seed: int | None = None, options=None):
        if seed is None and not self._seeded:
            seed = self.seed_value
        super().reset(seed=seed)
        self._seeded = True
        episode_seed = int(self.np_random.integers(0, 2**31 - 1))
        self._policy_rng.seed(episode_seed)

        player_count = int(self.player_counts[int(self.np_random.integers(len(self.player_counts)))])
        player_ids = tuple(f"player_{i + 1}" for i in range(player_count))
        self.learner = player_ids[int(self.np_random.integers(player_count))]
        self.opponent_kinds = {}
        self._opponent_selectors = {}
        for pid in player_ids:
            if pid == self.learner:
                continue
            kind = self._choose_opponent_kind()
            self.opponent_kinds[pid] = kind
            if kind not in self._opponent_selectors:
                self._opponent_selectors[kind] = self._selector_for_kind(kind)

        self.adapter.player_ids = player_ids
        starting_player = player_ids[int(self.np_random.integers(player_count))]
        self.adapter.starting_player = starting_player
        observation = self.adapter.reset(episode_seed)
        self.steps = 0
        self.reward_totals = {}
        self._last_adjusted = {pid: 0.0 for pid in player_ids}
        observation, _, _ = self._play_opponents(observation)
        self._observation = observation
        return self._vector(observation), {
            "player_id": self.learner,
            "opponents": dict(self.opponent_kinds),
            "episode_seed": episode_seed,
            "random_setup_probability": self.random_setup_probability,
            "rule_pass_probability": self.rule_pass_probability,
        }

    def action_masks(self) -> np.ndarray:
        if self._observation is None:
            raise RuntimeError("environment must be reset before requesting an action mask")
        return np.asarray(self._observation["action_mask"], dtype=bool)

    def step(self, action: int):
        if self._observation is None:
            raise RuntimeError("environment must be reset before stepping")
        observation, _, terminated, info = self.adapter.step(int(action))
        self.steps += 1
        if not terminated:
            observation, terminated, opponent_info = self._play_opponents(observation)
            if opponent_info:
                info = opponent_info
        if self.adapter.current_player != self.learner or terminated:
            observation = self.adapter.observe(self.learner, [])
        self._observation = observation

        game_data = self.adapter.state["game_data"]
        adjusted = _adjusted_scores(game_data)
        deltas = {pid: adjusted[pid] - self._last_adjusted.get(pid, 0.0) for pid in adjusted}
        self._last_adjusted = adjusted
        own_delta = deltas.get(self.learner, 0.0)
        opponent_ids = [pid for pid in adjusted if pid != self.learner]
        opponent_delta = (
            sum(deltas[pid] for pid in opponent_ids) / len(opponent_ids) if opponent_ids else 0.0
        )
        reward_breakdown = {
            "own_score": self.reward_scale * own_delta,
            "opponent_score": -self.reward_scale * opponent_delta,
            "win": 0.0,
            "timeout": 0.0,
        }
        winner = info.get("ranking")
        if terminated and winner is not None:
            reward_breakdown["win"] = self.win_reward if winner == self.learner else -self.win_reward
        truncated = not terminated and self.steps >= self.max_episode_steps
        if truncated:
            reward_breakdown["timeout"] = self.timeout_penalty
        for name, value in reward_breakdown.items():
            self.reward_totals[name] = self.reward_totals.get(name, 0.0) + value
        info = {
            "learner": self.learner,
            "opponents": dict(self.opponent_kinds),
            "move": info.get("move"),
            "winner": winner,
            "final_scores": dict(info.get("final_scores", {})),
            "reward_breakdown": reward_breakdown,
            "reward_totals": dict(self.reward_totals),
        }
        if truncated:
            info["truncated_reason"] = "max_episode_steps"
        reward = sum(reward_breakdown.values())
        return self._vector(observation), float(reward), bool(terminated), truncated, info
