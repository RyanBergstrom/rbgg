"""Low-overhead episode execution and streaming statistics for RL adapters."""
from __future__ import annotations

import json
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TextIO

from app.core.rl_adapter import RLAdapter


@dataclass(frozen=True)
class EpisodeSummary:
    """Small terminal summary; no states or trajectories are retained."""

    episode: int
    seed: int
    steps: int
    winner: str | None
    total_reward: float
    elapsed_seconds: float
    action_counts: dict[str, int]
    final_scores: dict[str, float]
    terminated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "episode": self.episode,
            "seed": self.seed,
            "steps": self.steps,
            "winner": self.winner,
            "total_reward": round(self.total_reward, 8),
            "elapsed_seconds": round(self.elapsed_seconds, 8),
            "action_counts": self.action_counts,
            "final_scores": self.final_scores,
            "terminated": self.terminated,
        }


@dataclass
class RunStatistics:
    """Streaming aggregate statistics for a collection of episodes."""

    episodes: int = 0
    total_steps: int = 0
    total_reward: float = 0.0
    winners: Counter[str] = field(default_factory=Counter)
    action_counts: Counter[str] = field(default_factory=Counter)
    score_totals: Counter[str] = field(default_factory=Counter)
    min_steps: int | None = None
    max_steps: int | None = None

    def add(self, summary: EpisodeSummary) -> None:
        self.episodes += 1
        self.total_steps += summary.steps
        self.total_reward += summary.total_reward
        self.winners[summary.winner or "unfinished"] += 1
        self.action_counts.update(summary.action_counts)
        self.score_totals.update(summary.final_scores)
        self.min_steps = summary.steps if self.min_steps is None else min(self.min_steps, summary.steps)
        self.max_steps = summary.steps if self.max_steps is None else max(self.max_steps, summary.steps)

    def as_dict(self) -> dict[str, Any]:
        return {
            "episodes": self.episodes,
            "total_steps": self.total_steps,
            "average_steps_per_episode": (
                self.total_steps / self.episodes if self.episodes else 0.0
            ),
            "total_reward": round(self.total_reward, 8),
            "average_reward_per_episode": (
                self.total_reward / self.episodes if self.episodes else 0.0
            ),
            "min_steps": self.min_steps,
            "max_steps": self.max_steps,
            "winners": dict(self.winners),
            "action_counts": dict(self.action_counts),
            "average_final_scores": {
                player_id: score / self.episodes
                for player_id, score in self.score_totals.items()
            },
        }


def _enabled_actions(observation: dict[str, Any]) -> list[int]:
    mask = observation.get("action_mask")
    if not isinstance(mask, list):
        raise ValueError("adapter observation must contain an action_mask list")
    actions = [index for index, enabled in enumerate(mask) if enabled]
    if not actions:
        raise ValueError("adapter returned no legal actions for a non-terminal step")
    return actions


def run_episode(
    adapter: RLAdapter,
    *,
    episode: int,
    seed: int,
    rng: random.Random | None = None,
    summary_stream: TextIO | None = None,
    flush_summary: bool = False,
    action_selector: Callable[[RLAdapter, dict[str, Any], random.Random], int] | None = None,
    max_steps: int | None = None,
) -> EpisodeSummary:
    """Run one random-policy episode and optionally stream one JSONL summary."""
    chooser = rng or random.Random(seed)
    started = time.perf_counter()
    observation = adapter.reset(seed)
    steps = 0
    total_reward = 0.0
    winner: str | None = None
    final_scores: dict[str, float] = {}
    action_counts: Counter[str] = Counter()
    done = False

    while not done:
        if max_steps is not None and steps >= max_steps:
            break
        if action_selector is None:
            action_id = chooser.choice(_enabled_actions(observation))
        else:
            action_id = action_selector(adapter, observation, chooser)
        action_counts[str(action_id)] += 1
        observation, reward, done, info = adapter.step(action_id)
        total_reward += reward
        winner = info.get("winner")
        final_scores = {
            str(player_id): float(score)
            for player_id, score in info.get("final_scores", {}).items()
        }
        steps += 1

    summary = EpisodeSummary(
        episode=episode,
        seed=seed,
        steps=steps,
        winner=winner,
        total_reward=total_reward,
        elapsed_seconds=time.perf_counter() - started,
        action_counts=dict(action_counts),
        final_scores=final_scores,
        terminated=done,
    )
    if summary_stream is not None:
        summary_stream.write(json.dumps(summary.as_dict(), separators=(",", ":")) + "\n")
        if flush_summary:
            summary_stream.flush()
    return summary


def run_episodes(
    adapter_factory,
    *,
    episodes: int,
    seed: int = 20261015,
    summary_path: str | Path | None = None,
    flush_summaries: bool = False,
    action_selector: Callable[[RLAdapter, dict[str, Any], random.Random], int] | None = None,
    max_steps_per_episode: int | None = None,
) -> RunStatistics:
    """Run episodes with bounded memory and optional streamed JSONL summaries."""
    if episodes < 1:
        raise ValueError("episodes must be positive")
    statistics = RunStatistics()
    stream = None
    try:
        if summary_path is not None:
            stream = Path(summary_path).open("w", encoding="utf-8")
        for episode in range(episodes):
            summary = run_episode(
                adapter_factory(seed + episode),
                episode=episode,
                seed=seed + episode,
                summary_stream=stream,
                flush_summary=flush_summaries,
                action_selector=action_selector,
                max_steps=max_steps_per_episode,
            )
            statistics.add(summary)
    finally:
        if stream is not None:
            stream.close()
    return statistics
