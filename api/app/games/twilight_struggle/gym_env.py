"""Gymnasium bridge: one learner faction versus a fixed in-environment opponent.

The learner's faction is randomized per episode. Opponent decisions (including multi-step sub-decisions) are
played inside ``step``; every reward is from the learner's perspective. The per-step reward is the learner's
VP-margin change scaled by ``reward_scale``, so ``sum(rewards) == reward_scale * final learner VP margin``
(plus ``timeout_penalty`` on truncation). Terminal wins by DEFCON/auto-victory are reported in ``info``.
"""
from __future__ import annotations

import random
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.games.twilight_struggle.rl_adapter import (
    ACTION_COUNT, OBSERVATION_SIZE, VP_REWARD_SCALE, TwilightStruggleReferenceEnv,
)
from app.games.twilight_struggle.rl_policies import FIXED_POLICIES

DEFAULT_OPPONENTS = {"rule": 0.6, "random": 0.3, "null": 0.1}


def validate_opponents(weights: dict[str, float]) -> None:
    allowed = {*FIXED_POLICIES, "snapshot"}
    unknown = set(weights) - allowed
    if unknown:
        raise ValueError(f"unknown opponents {sorted(unknown)}; expected {sorted(allowed)}")
    if any(weight < 0 for weight in weights.values()):
        raise ValueError("opponent weights cannot be negative")
    if not any(weight > 0 for name, weight in weights.items() if name != "snapshot"):
        raise ValueError("at least one fixed opponent needs a positive weight")


def parse_opponent_mix(spec: str) -> dict[str, float]:
    """Parse ``"rule=0.6,random=0.1,snapshot=0.3"`` into validated weights."""
    weights: dict[str, float] = {}
    for part in spec.split(","):
        name, _, weight = part.strip().partition("=")
        weights[name] = float(weight) if weight else 1.0
    validate_opponents(weights)
    return weights


class TwilightStruggleGymEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self, seed: int = 42, max_episode_steps: int = 6000, opponents: dict[str, float] | None = None,
        reward_scale: float = 0.1, timeout_penalty: float = -0.5,
        win_reward: float = 1.0, learner_faction: str | None = None,
        curriculum_stage: int = 2,  # 0=auto-DONE, 1=guided DONE reward, 2=full staged decisions
    ):
        super().__init__()
        self.opponents = dict(opponents or DEFAULT_OPPONENTS)
        validate_opponents(self.opponents)
        if learner_faction not in (None, "us", "ussr"):
            raise ValueError("learner_faction must be 'us', 'ussr' or None")
        self.seed_value = seed
        self.max_episode_steps = max_episode_steps
        self.reward_scale = reward_scale
        self.timeout_penalty = timeout_penalty
        self.win_reward = win_reward
        self.fixed_faction = learner_faction
        self.curriculum_stage = max(0, min(2, curriculum_stage))  # Clamp to 0-2
        self.adapter = TwilightStruggleReferenceEnv(seed=seed)
        self.action_space = spaces.Discrete(ACTION_COUNT)
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(OBSERVATION_SIZE,), dtype=np.float32)
        self._policy_rng = random.Random(seed)
        self._seeded = False
        self._observation: dict[str, Any] | None = None
        self.snapshot_paths: list[str] = []
        self._snapshot_selectors: dict[str, Any] = {}
        self._opponent_selector = FIXED_POLICIES["rule"]
        self.learner = "player_1"
        self.learner_faction = "us"
        self.opponent_kind = "rule"
        self.steps = 0
        self._last_vp = 0.0

    def _vp(self) -> float:
        vp = float(self.adapter.game_data["tracks"]["victory_points"])
        return vp if self.learner_faction == "us" else -vp

    def set_opponent_weights(self, weights: dict[str, float]) -> None:
        """Dynamically update opponent mix weights for subsequent episodes."""
        validate_opponents(weights)
        self.opponents = dict(weights)
        self.opponent_kind, self._opponent_selector = self._choose_opponent()

    def _vector(self, observation: dict[str, Any]) -> np.ndarray:
        return np.asarray(observation["observation"], dtype=np.float32)

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
                del adapter, rng
                action, _ = model.predict(
                    np.asarray(observation["observation"], dtype=np.float32),
                    action_masks=np.asarray(observation["action_mask"], dtype=bool),
                    deterministic=False,
                )
                return int(action)

            selector = _select
            self._snapshot_selectors[path] = selector
        return selector

    def _choose_opponent(self) -> tuple[str, Any]:
        available = {
            name: weight for name, weight in self.opponents.items()
            if weight > 0 and (name != "snapshot" or self.snapshot_paths)
        }
        names = list(available)
        probs = np.array(list(available.values()), dtype=float)
        kind = names[int(self.np_random.choice(len(names), p=probs / probs.sum()))]
        if kind == "snapshot":
            path = self.snapshot_paths[int(self.np_random.integers(len(self.snapshot_paths)))]
            return kind, self._snapshot_selector(path)
        return kind, FIXED_POLICIES[kind]

    def _play_opponent(self, observation: dict[str, Any]) -> dict[str, Any]:
        selector = self._opponent_selector
        opp_steps = 0
        while not self.adapter.is_terminal() and self.adapter.current_player != self.learner \
                and self.steps < self.max_episode_steps:
            observation = self.adapter.observe(self.adapter.current_player)
            if not any(observation["action_mask"]):
                break
            observation, _, _, _ = self.adapter.step(int(selector(self.adapter, observation, self._policy_rng)))
            self.steps += 1
            opp_steps += 1
        if opp_steps > 50:
            print(f"[OPPONENT_LONG] opp_steps={opp_steps} total_steps={self.steps} terminal={self.adapter.is_terminal()}", flush=True)
        return observation

    def reset(self, *, seed: int | None = None, options=None):
        if seed is None and not self._seeded:
            seed = self.seed_value
        super().reset(seed=seed)
        self._seeded = True
        episode_seed = int(self.np_random.integers(0, 2**31 - 1))
        self._policy_rng.seed(episode_seed)
        faction = self.fixed_faction or ("us" if self.np_random.integers(2) == 0 else "ussr")
        names = list(self.opponents)
        self.opponent_kind, self._opponent_selector = self._choose_opponent()
        self.adapter.reset(episode_seed)
        self.learner_faction = faction
        self.learner = self.adapter.game_data["player_by_faction"][faction]
        self.steps = 0
        self._last_vp = self._vp()
        self._observation = self._play_opponent(self.adapter.observe(self.adapter.current_player))
        if self.adapter.current_player == self.learner:
            self._observation = self.adapter.observe(self.learner)
        self._last_vp = self._vp()
        self._start_vp = self._last_vp
        return self._vector(self._observation), {
            "player_id": self.learner, "faction": faction, "opponent": self.opponent_kind,
            "episode_seed": episode_seed,
        }

    def action_masks(self) -> np.ndarray:
        if self._observation is None:
            raise RuntimeError("environment must be reset before requesting an action mask")
        return np.asarray(self._observation["action_mask"], dtype=bool)

    def step(self, action: int):
        if self._observation is None:
            raise RuntimeError("environment must be reset before stepping")
        
        # Staged decision stages that require DONE to complete
        STAGED_DECISION_STAGES = {3, 4, 5, 6, 7}  # INFLUENCE, COUP, REALIGN, KAL_INFLUENCE, KAL_REALIGN
        from app.games.twilight_struggle import rl_adapter as ra
        
        # Check if we were in a staged decision state BEFORE the action
        was_in_staged = self.adapter.stage in STAGED_DECISION_STAGES
        done_selected = False
        
        observation, _, terminated, info = self.adapter.step(int(action))
        self.steps += 1
        
        # Track if DONE was selected in a staged decision
        if was_in_staged and action == ra.DONE:
            done_selected = True
        
        # Curriculum Stage 0: Auto-complete staged decisions (auto-DONE)
        if not terminated and self.curriculum_stage == 0:
            auto_steps = 0
            max_auto_steps = 100
            while not terminated and auto_steps < max_auto_steps:
                stage = self.adapter.stage
                if stage not in STAGED_DECISION_STAGES:
                    break
                mask = self.adapter.action_mask(self.learner)
                legal = [i for i, m in enumerate(mask) if m]
                if not legal:
                    break
                auto_action = ra.DONE if ra.DONE in legal else legal[0]
                observation, _, terminated, info = self.adapter.step(auto_action)
                self.steps += 1
                auto_steps += 1
            if auto_steps >= max_auto_steps:
                print(f"[AUTO_DONE_STUCK] steps={self.steps} stage={self.adapter.stage} terminated={terminated}", flush=True)
        
        if not terminated:
            observation = self._play_opponent(observation)
            terminated = self.adapter.is_terminal()
        observation = self.adapter.observe(self.learner)
        self._observation = observation
        vp = self._vp()
        reward = self.reward_scale * (vp - self._last_vp)
        self._last_vp = vp
        
        # Curriculum Stage 1: Guided DONE reward - small bonus for selecting DONE in staged decisions
        if self.curriculum_stage >= 1 and done_selected:
            reward += 0.05  # Small positive reward for correctly completing a sub-decision
        
        truncated = not terminated and self.steps >= self.max_episode_steps
        stalled = not terminated and not any(observation["action_mask"])
        if truncated:
            reward += self.timeout_penalty
        winner = self.adapter.validator.check_win(self.adapter.state) if terminated else None
        if winner is not None:
            reward += self.win_reward if winner == self.learner else -self.win_reward
        terminal = self.adapter.game_data.get("terminal_result") if terminated else None
        if terminal and terminal.get("reason") == "defcon_1" and winner != self.learner:
            reward -= 2.0
        out = {
            "learner": self.learner, "faction": self.learner_faction, "opponent": self.opponent_kind,
            "vp_margin": vp, "terminal_result": self.adapter.game_data.get("terminal_result"),
            "winner": winner,
        }
        if truncated:
            out["truncated_reason"] = "max_episode_steps"
        if stalled:
            out["stalled"] = True
            truncated = True
        return self._vector(observation), float(reward), bool(terminated), truncated, out
