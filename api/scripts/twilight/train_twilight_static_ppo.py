"""Train a masked PPO Twilight Struggle policy against a single static opponent model.

Use this to measure genuine improvement: the opponent never changes, so if the
learner's win rate vs that static opponent rises over versions, the learner is
actually getting better — not just keeping pace with a moving target.

Usage example (US learner vs frozen v7 as USSR opponent):

    python train_twilight_static_ppo.py ^
        --timesteps 1000000 ^
        --resume api/runtime/twilight-ppo-v72.zip ^
        --static-opponent api/runtime/twilight-ppo-v7.zip ^
        --learner-faction us ^
        --output api/runtime/twilight/twilight-ppo-v8 ^
        --checkpoint-frequency 100000 ^
        --n-envs 4 ^
        --max-episode-steps 3000 ^
        --curriculum-stage 2
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv


class EpisodeStatsCallback(BaseCallback):
    """Log finished-episode statistics (VP margin, win rate, stalls)."""

    def __init__(self, window: int = 200):
        super().__init__()
        self.window = window
        self.margins: list[float] = []
        self.wins: list[float] = []
        self.stalls: list[float] = []
        self.finished: list[float] = []
        self.next_log = 0

    def _on_step(self) -> bool:
        for info, done in zip(self.locals["infos"], self.locals["dones"]):
            if not done:
                continue
            terminal = info.get("terminal_result") is not None
            self.finished.append(float(terminal))
            self.stalls.append(float(bool(info.get("stalled"))))
            if terminal:
                self.margins.append(float(info["vp_margin"]))
                self.wins.append(float(info.get("winner") == info.get("learner")))
        if self.num_timesteps >= self.next_log and self.finished:
            self.next_log = self.num_timesteps + 500
            tail = slice(-self.window, None)
            self.logger.record("twilight/finish_rate", float(np.mean(self.finished[tail])))
            self.logger.record("twilight/stall_rate", float(np.mean(self.stalls[tail])))
            if self.margins:
                self.logger.record("twilight/vp_margin", float(np.mean(self.margins[tail])))
                self.logger.record("twilight/win_rate", float(np.mean(self.wins[tail])))
        return True

    def _on_rollout_start(self) -> bool:
        print(f"[rollout_start] timesteps={self.num_timesteps}", flush=True)
        return True

    def _on_rollout_end(self) -> bool:
        print(f"[rollout_end] timesteps={self.num_timesteps}", flush=True)
        return True


def override_resume_hyperparameters(model, learning_rate: float | None, ent_coef: float | None) -> None:
    """Apply explicitly supplied PPO overrides to a loaded model."""
    if learning_rate is not None:
        model.learning_rate = learning_rate
        model.lr_schedule = lambda _: learning_rate
    if ent_coef is not None:
        model.ent_coef = ent_coef


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--timesteps", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument("--output", required=True,
                        help="Output model path (no dots before final .zip component).")
    parser.add_argument("--checkpoint-frequency", type=int, default=100_000,
                        help="Save intermediate checkpoints every N timesteps; 0 disables.")
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--vec-env", choices=("dummy", "subproc"), default="dummy")
    parser.add_argument("--n-steps", type=int, default=1024, help="Rollout steps per environment.")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--n-epochs", type=int, default=10)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--gamma", type=float, default=0.9995)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--ent-coef", type=float)
    parser.add_argument("--net-arch", default="512,512")
    parser.add_argument("--static-opponent", required=True,
                        help="Frozen MaskablePPO .zip to play against every episode.")
    parser.add_argument("--learner-faction", choices=("us", "ussr"), required=True,
                        help="Faction the learner plays; static opponent plays the other.")
    parser.add_argument("--curriculum-stage", type=int, default=2, choices=(0, 1, 2),
                        help="Manual curriculum stage: 0=auto-DONE, 1=guided DONE, 2=full staged.")
    parser.add_argument("--max-episode-steps", type=int, default=3000)
    parser.add_argument("--reward-scale", type=float, default=0.1)
    parser.add_argument("--timeout-penalty", type=float, default=-0.5)
    parser.add_argument("--win-reward", type=float, default=1.0)
    parser.add_argument("--resume", help="Continue training this saved model (.zip).")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.timesteps < 0:
        parser.error("timesteps cannot be negative")
    if args.checkpoint_frequency < 0:
        parser.error("checkpoint-frequency cannot be negative")
    for name in ("n_envs", "n_steps", "batch_size", "n_epochs", "max_episode_steps"):
        if getattr(args, name) < 1:
            parser.error(f"{name.replace('_', '-')} must be positive")
    if args.timeout_penalty > 0:
        parser.error("timeout-penalty must be zero or negative")
    if args.reward_scale <= 0:
        parser.error("reward-scale must be positive")
    if args.learning_rate is not None and args.learning_rate <= 0:
        parser.error("learning-rate must be positive")
    if args.ent_coef is not None and args.ent_coef < 0:
        parser.error("ent-coef cannot be negative")
    if args.resume and not Path(args.resume).is_file():
        parser.error(f"resume model not found: {args.resume}")
    if not Path(args.static_opponent).is_file():
        parser.error(f"static opponent model not found: {args.static_opponent}")
    if "." in Path(args.output).name and not args.output.endswith(".zip"):
        parser.error("--output must not contain a dot before the final component (SB3 would not append .zip)")

    net_arch = [int(width) for width in args.net_arch.split(",")]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    env_kwargs = {
        "opponents": {"snapshot": 0.99, "rule": 0.01},
        "reward_scale": args.reward_scale,
        "timeout_penalty": args.timeout_penalty,
        "win_reward": args.win_reward,
        "max_episode_steps": args.max_episode_steps,
        "learner_faction": args.learner_faction,
        "curriculum_stage": args.curriculum_stage,
    }
    env = make_vec_env(
        TwilightStruggleGymEnv,
        n_envs=args.n_envs,
        seed=args.seed,
        env_kwargs={**env_kwargs, "seed": args.seed},
        vec_env_cls=SubprocVecEnv if args.vec_env == "subproc" else DummyVecEnv,
    )

    # Register the static opponent model as the only snapshot opponent.
    env.env_method("add_opponent_snapshot", str(args.static_opponent), 1)

    if args.resume:
        model = MaskablePPO.load(args.resume, env=env)
        model.set_random_seed(args.seed)
        override_resume_hyperparameters(model, args.learning_rate, args.ent_coef)
        print(f"resumed_model={args.resume} num_timesteps={model.num_timesteps}", flush=True)
    else:
        model = MaskablePPO(
            "MlpPolicy",
            env,
            seed=args.seed,
            verbose=1,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            n_epochs=args.n_epochs,
            learning_rate=args.learning_rate if args.learning_rate is not None else 3e-4,
            gamma=args.gamma,
            gae_lambda=args.gae_lambda,
            ent_coef=args.ent_coef if args.ent_coef is not None else 0.01,
            policy_kwargs={"net_arch": net_arch},
        )
    start_timesteps = model.num_timesteps

    callbacks: list[BaseCallback] = [EpisodeStatsCallback()]
    if args.checkpoint_frequency:
        checkpoint_dir = output.parent / f"{output.stem}-checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        callbacks.append(CheckpointCallback(
            save_freq=max(1, args.checkpoint_frequency // args.n_envs),
            save_path=str(checkpoint_dir),
            name_prefix=output.stem,
        ))

    if args.timesteps:
        print(f"[learn_start] total_timesteps={args.timesteps} reset_num_timesteps={not args.resume}", flush=True)
        model.learn(total_timesteps=args.timesteps, callback=CallbackList(callbacks), progress_bar=False,
                    reset_num_timesteps=not args.resume)
        print(f"[learn_done] final_timesteps={model.num_timesteps}", flush=True)
    model.save(str(output))
    print(f"model={output}.zip")
    print(f"timesteps={model.num_timesteps}")


if __name__ == "__main__":
    main()
