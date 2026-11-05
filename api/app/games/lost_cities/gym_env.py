"""Gymnasium bridge for training one Lost Cities seat against fixed opponents.

The learner controls exactly one seat per episode. Opponent turns are played
inside ``step`` by a fixed policy or a frozen model snapshot, so every reward,
value target, and advantage is from the learner's perspective.

Reward is the change in the learner's score margin, where each player's
running score is ``banked score + current-round expedition score``. Each card
played is therefore rewarded or charged immediately, and the per-step rewards
sum exactly to ``reward_scale * final margin`` (plus optional win and timeout
terms).
"""
from __future__ import annotations

import random
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv, OBSERVATION_SCHEMA_VERSION
from app.games.lost_cities.rl_policies import FIXED_POLICIES, make_model_selector
from app.games.lost_cities.validator import _calculate_player_score

DEFAULT_OPPONENTS = {"rule": 0.6, "random": 0.1, "snapshot": 0.3}
SEATS = ("player_1", "player_2")


def parse_opponent_mix(spec: str) -> dict[str, float]:
    """Parse ``"rule=0.6,random=0.1,snapshot=0.3"`` into validated weights."""
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


def running_score(game_data: dict[str, Any], player_id: str) -> float:
    """Banked score plus the unbanked current-round expedition score."""
    banked = float(game_data.get("scores", {}).get(player_id, 0))
    if game_data.get("game_over"):
        return banked
    return banked + _calculate_player_score(game_data["expeditions"][player_id])


class LostCitiesGymEnv(gym.Env):
    """One learner seat versus an in-environment opponent."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        seed: int = 42,
        max_episode_steps: int = 1500,
        opponents: dict[str, float] | None = None,
        reward_scale: float = 0.01,
        opponent_score_weight: float = 1.0,
        win_reward: float = 0.0,
        timeout_penalty: float = -0.25,
        learner_seat: str | None = None,
        observation_version: int = OBSERVATION_SCHEMA_VERSION,
    ):
        super().__init__()
        if learner_seat not in (None, *SEATS):
            raise ValueError(f"learner_seat must be None or one of {SEATS}")
        self.opponents = dict(opponents or DEFAULT_OPPONENTS)
        _validate_opponents(self.opponents)
        self.seed_value = seed
        self.max_episode_steps = max_episode_steps
        self.reward_scale = reward_scale
        self.opponent_score_weight = opponent_score_weight
        self.win_reward = win_reward
        self.timeout_penalty = timeout_penalty
        self.fixed_learner_seat = learner_seat
        self.steps = 0
        self.reward_totals: dict[str, float] = {}
        self.snapshot_paths: list[str] = []
        self._snapshot_selectors: dict[str, Any] = {}
        self._seeded = False
        self._policy_rng = random.Random(seed)
        self.learner = "player_1"
        self.opponent = "player_2"
        self.opponent_kind = "rule"
        self._opponent_selector = FIXED_POLICIES["rule"]
        self._last_running = {seat: 0.0 for seat in SEATS}
        self.adapter = LostCitiesReferenceEnv(seed=seed, observation_version=observation_version)
        self.action_space = spaces.Discrete(self.adapter.action_count)
        self.observation_space = spaces.Box(
            # Score features can legitimately be negative in Lost Cities.
            low=-np.inf,
            high=np.inf,
            shape=(self.adapter.observation_size,),
            dtype=np.float32,
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

            selector = make_model_selector(MaskablePPO.load(path, device="cpu"), deterministic=False)
            self._snapshot_selectors[path] = selector
        return selector

    def _choose_opponent(self) -> None:
        available = {
            name: weight
            for name, weight in self.opponents.items()
            if weight > 0 and (name != "snapshot" or self.snapshot_paths)
        }
        names = list(available)
        kind = names[int(self.np_random.choice(len(names), p=np.array(list(available.values())) / sum(available.values())))]
        self.opponent_kind = kind
        if kind == "snapshot":
            path = self.snapshot_paths[int(self.np_random.integers(len(self.snapshot_paths)))]
            self._opponent_selector = self._snapshot_selector(path)
        else:
            self._opponent_selector = FIXED_POLICIES[kind]

    def _vector(self, observation: dict[str, Any]) -> np.ndarray:
        return np.asarray(observation["observation"], dtype=np.float32)

    def _play_opponent(self, observation: dict[str, Any]) -> tuple[dict[str, Any], bool, dict[str, Any]]:
        done = False
        info: dict[str, Any] = {}
        while not done and self.adapter.current_player != self.learner and self.steps < self.max_episode_steps:
            action = self._opponent_selector(self.adapter, observation, self._policy_rng)
            observation, _, done, info = self.adapter.step(int(action))
            self.steps += 1
        return observation, done, info

    def reset(self, *, seed: int | None = None, options=None):
        # Seed once, then keep drawing new deals from the persistent generator.
        # Re-using a fixed seed on every auto-reset would train on one deal.
        if seed is None and not self._seeded:
            seed = self.seed_value
        super().reset(seed=seed)
        self._seeded = True
        episode_seed = int(self.np_random.integers(0, 2**31 - 1))
        self._policy_rng.seed(episode_seed)
        self.learner = self.fixed_learner_seat or SEATS[int(self.np_random.integers(2))]
        self.opponent = SEATS[1 - SEATS.index(self.learner)]
        self.adapter.starting_player = SEATS[int(self.np_random.integers(2))]
        self._choose_opponent()
        observation = self.adapter.reset(episode_seed)
        self.steps = 0
        self.reward_totals = {}
        self._last_running = {seat: 0.0 for seat in SEATS}
        observation, _, _ = self._play_opponent(observation)
        self._observation = observation
        return self._vector(observation), {
            "player_id": self.learner,
            "opponent": self.opponent_kind,
            "episode_seed": episode_seed,
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
        learner_info = info
        if not terminated:
            observation, terminated, opponent_info = self._play_opponent(observation)
            if opponent_info:
                info = opponent_info
        if self.adapter.current_player != self.learner or terminated:
            # Terminal/truncated observations are only used for value
            # bootstrapping and must still be from the learner's perspective.
            observation = self.adapter.observe(self.learner, [])
        self._observation = observation

        game_data = self.adapter.state["game_data"]
        running = {seat: running_score(game_data, seat) for seat in SEATS}
        own_delta = running[self.learner] - self._last_running[self.learner]
        opponent_delta = running[self.opponent] - self._last_running[self.opponent]
        self._last_running = running
        reward_breakdown = {
            "own_score": self.reward_scale * own_delta,
            "opponent_score": -self.reward_scale * self.opponent_score_weight * opponent_delta,
            "win": 0.0,
            "timeout": 0.0,
        }
        winner = info.get("winner")
        if terminated and winner not in (None, "draw"):
            reward_breakdown["win"] = self.win_reward if winner == self.learner else -self.win_reward
        truncated = not terminated and self.steps >= self.max_episode_steps
        if truncated:
            reward_breakdown["timeout"] = self.timeout_penalty
        for name, value in reward_breakdown.items():
            self.reward_totals[name] = self.reward_totals.get(name, 0.0) + value
        info = {
            "learner": self.learner,
            "opponent": self.opponent_kind,
            "move": learner_info["move"],
            "winner": winner,
            "final_scores": dict(game_data.get("scores", {})),
            "reward_breakdown": reward_breakdown,
            "reward_totals": dict(self.reward_totals),
        }
        if truncated:
            info["truncated_reason"] = "max_episode_steps"
        reward = sum(reward_breakdown.values())
        return self._vector(observation), float(reward), bool(terminated), truncated, info
