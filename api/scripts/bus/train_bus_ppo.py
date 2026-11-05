"""Train a masked PPO Bus policy for one seat against fixed/pool opponents.

Pipeline:

1. Optional behavior cloning from a teacher policy (default: ``rule``). The
   policy head imitates teacher actions and the value head is fitted to the
   teacher's discounted returns under the same reward used by PPO.
2. PPO against an opponent mix (fixed policies plus frozen snapshots of the
   learner, refreshed every ``--snapshot-frequency`` timesteps).

Bus supports 3-5 players; ``--player-counts`` controls which counts are
sampled each episode (default: all of 3, 4, 5).
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from app.games.bus.gym_env import BusGymEnv, parse_opponent_mix
from app.games.bus.rl_adapter import OBSERVATION_SIZES
from app.games.bus.rl_policies import FIXED_POLICIES


class OpponentSnapshotCallback(BaseCallback):
    """Periodically freeze the learner and add it to every env's opponent pool."""

    def __init__(self, frequency: int, directory: Path, prefix: str, max_snapshots: int, start: int = 0):
        super().__init__()
        self.frequency = frequency
        self.directory = directory
        self.prefix = prefix
        self.max_snapshots = max_snapshots
        self.last_snapshot = start

    def _on_step(self) -> bool:
        if self.num_timesteps - self.last_snapshot >= self.frequency:
            self.last_snapshot = self.num_timesteps
            add_snapshot(self.model, self.directory / f"{self.prefix}_{self.num_timesteps}", self.max_snapshots)
        return True


def add_snapshot(model, path: Path, max_snapshots: int) -> None:
    model.save(str(path))
    model.get_env().env_method("add_opponent_snapshot", f"{path}.zip", max_snapshots)


def override_resume_hyperparameters(model, learning_rate: float | None, ent_coef: float | None) -> None:
    """Apply explicitly supplied PPO overrides to a loaded model."""
    if learning_rate is not None:
        model.learning_rate = learning_rate
        model.lr_schedule = lambda _: learning_rate
    if ent_coef is not None:
        model.ent_coef = ent_coef


def collect_teacher_data(env_kwargs: dict, teacher: str, episodes: int, seed: int, gamma: float):
    """Play the teacher in the learner seat and record (obs, mask, action, return)."""
    env = BusGymEnv(**env_kwargs)
    selector = FIXED_POLICIES[teacher]
    rng = random.Random(seed)
    observations, masks, actions, returns = [], [], [], []
    scores = []
    for episode in range(episodes):
        vector, _ = env.reset(seed=seed + episode)
        rewards = []
        done = False
        while not done:
            observations.append(vector)
            masks.append(env.action_masks())
            action = selector(env.adapter, env.adapter_observation, rng)
            actions.append(action)
            vector, reward, terminated, truncated, info = env.step(action)
            rewards.append(reward)
            done = terminated or truncated
        scores.append(info["final_scores"].get(env.learner, 0))
        running = 0.0
        episode_returns = []
        for reward in reversed(rewards):
            running = reward + gamma * running
            episode_returns.append(running)
        returns.extend(reversed(episode_returns))
    print(f"teacher={teacher} episodes={episodes} decisions={len(actions)} "
          f"avg_learner_score={np.mean(scores):.2f}")
    return (
        np.asarray(observations, dtype=np.float32),
        np.asarray(masks, dtype=bool),
        np.asarray(actions, dtype=np.int64),
        np.asarray(returns, dtype=np.float32),
    )


def behavior_clone(model, data, epochs: int, batch_size: int, value_coef: float = 0.5) -> None:
    observations, masks, actions, returns = (torch.as_tensor(array, device=model.device) for array in data)
    policy = model.policy
    policy.set_training_mode(True)
    generator = torch.Generator().manual_seed(0)
    for epoch in range(epochs):
        order = torch.randperm(len(actions), generator=generator).to(model.device)
        policy_losses, value_losses, correct = [], [], 0
        for start in range(0, len(actions), batch_size):
            index = order[start:start + batch_size]
            values, log_prob, _ = policy.evaluate_actions(observations[index], actions[index], action_masks=masks[index])
            policy_loss = -log_prob.mean()
            value_loss = torch.nn.functional.mse_loss(values.flatten(), returns[index])
            loss = policy_loss + value_coef * value_loss
            policy.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), model.max_grad_norm)
            policy.optimizer.step()
            policy_losses.append(policy_loss.item())
            value_losses.append(value_loss.item())
            with torch.no_grad():
                probs = policy.get_distribution(observations[index], action_masks=masks[index]).distribution.probs
                correct += int((probs.argmax(dim=1) == actions[index]).sum())
        print(f"bc_epoch={epoch + 1} policy_loss={np.mean(policy_losses):.4f} "
              f"value_loss={np.mean(value_losses):.4f} accuracy={correct / len(actions):.3f}")
    policy.set_training_mode(False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--timesteps", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20261017)
    parser.add_argument("--output", default="runtime/bus-ppo")
    parser.add_argument("--checkpoint-frequency", type=int, default=0,
                        help="Save intermediate checkpoints every N timesteps; 0 disables them.")
    parser.add_argument("--n-envs", type=int, default=8)
    parser.add_argument("--vec-env", choices=("dummy", "subproc"), default="dummy")
    parser.add_argument("--n-steps", type=int, default=1024, help="Rollout steps per environment.")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--n-epochs", type=int, default=10)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--ent-coef", type=float)
    parser.add_argument("--net-arch", default="256,256")
    parser.add_argument("--opponents", default="rule=0.6,random=0.1,snapshot=0.3",
                        help="Weighted opponent mix: random, null, rule, snapshot.")
    parser.add_argument("--player-counts", default="3,4,5",
                        help="Comma-separated player counts to sample each episode, subset of 3,4,5.")
    parser.add_argument("--snapshot-frequency", type=int, default=50_000)
    parser.add_argument("--max-snapshots", type=int, default=5)
    parser.add_argument("--reward-scale", type=float, default=0.5)
    parser.add_argument("--win-reward", type=float, default=0.0)
    parser.add_argument("--timeout-penalty", type=float, default=-0.25)
    parser.add_argument("--max-episode-steps", type=int, default=3000)
    parser.add_argument("--random-setup-probability", type=float, default=0.25,
                        help="Chance opponents choose random legal moves during setup.")
    parser.add_argument("--rule-pass-probability", type=float, default=0.25,
                        help="Chance rule opponents pass once passing becomes legal.")
    parser.add_argument("--observation-version", type=int, choices=sorted(OBSERVATION_SIZES),
                        default=max(OBSERVATION_SIZES), help="Bus observation schema to train against.")
    parser.add_argument("--pretrain-episodes", type=int, default=0,
                        help="Teacher episodes for behavior cloning before PPO; 0 disables it.")
    parser.add_argument("--pretrain-epochs", type=int, default=10)
    parser.add_argument("--pretrain-teacher", choices=sorted(FIXED_POLICIES), default="rule")
    parser.add_argument("--resume", help="Continue training this saved model (.zip); --timesteps are added "
                        "to its step count. Saved PPO settings are retained unless --learning-rate or "
                        "--ent-coef is explicitly supplied.")
    args = parser.parse_args()

    if args.timesteps < 0:
        parser.error("timesteps cannot be negative")
    for name in ("checkpoint_frequency", "pretrain_episodes"):
        if getattr(args, name) < 0:
            parser.error(f"{name.replace('_', '-')} cannot be negative")
    for name in ("n_envs", "n_steps", "batch_size", "n_epochs", "snapshot_frequency", "max_snapshots", "max_episode_steps"):
        if getattr(args, name) < 1:
            parser.error(f"{name.replace('_', '-')} must be positive")
    if args.timeout_penalty > 0:
        parser.error("timeout-penalty must be zero or negative")
    if args.reward_scale <= 0:
        parser.error("reward-scale must be positive")
    for name in ("random_setup_probability", "rule_pass_probability"):
        if not 0.0 <= getattr(args, name) <= 1.0:
            parser.error(f"{name.replace('_', '-')} must be between 0 and 1")
    if args.learning_rate is not None and args.learning_rate <= 0:
        parser.error("learning-rate must be positive")
    if args.ent_coef is not None and args.ent_coef < 0:
        parser.error("ent-coef cannot be negative")
    if args.resume and args.pretrain_episodes:
        parser.error("--resume cannot be combined with --pretrain-episodes")
    if args.resume and not Path(args.resume).is_file():
        parser.error(f"resume model not found: {args.resume}")
    try:
        opponents = parse_opponent_mix(args.opponents)
        net_arch = [int(width) for width in args.net_arch.split(",")]
        player_counts = tuple(int(count) for count in args.player_counts.split(","))
        if any(count not in (3, 4, 5) for count in player_counts):
            raise ValueError("player-counts must be a subset of 3,4,5")
    except ValueError as error:
        parser.error(str(error))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    env_kwargs = {
        "opponents": opponents,
        "reward_scale": args.reward_scale,
        "win_reward": args.win_reward,
        "timeout_penalty": args.timeout_penalty,
        "player_counts": player_counts,
        "max_episode_steps": args.max_episode_steps,
        "random_setup_probability": args.random_setup_probability,
        "rule_pass_probability": args.rule_pass_probability,
        "observation_version": args.observation_version,
    }
    env = make_vec_env(
        BusGymEnv,
        n_envs=args.n_envs,
        seed=args.seed,
        env_kwargs={**env_kwargs, "seed": args.seed},
        vec_env_cls=SubprocVecEnv if args.vec_env == "subproc" else DummyVecEnv,
    )
    if args.resume:
        model = MaskablePPO.load(args.resume, env=env)
        model.set_random_seed(args.seed)
        override_resume_hyperparameters(model, args.learning_rate, args.ent_coef)
        print(f"resumed_model={args.resume} num_timesteps={model.num_timesteps}")
        print(f"resume_learning_rate={model.learning_rate} resume_ent_coef={model.ent_coef}")
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

    snapshot_dir = output.parent / f"{output.stem}-opponents"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    if args.resume and opponents.get("snapshot", 0) > 0:
        add_snapshot(model, snapshot_dir / f"{output.stem}_{start_timesteps}", args.max_snapshots)
    if args.pretrain_episodes:
        teacher_kwargs = {**env_kwargs, "opponents": {k: v for k, v in opponents.items() if k != "snapshot"}}
        data = collect_teacher_data(teacher_kwargs, args.pretrain_teacher, args.pretrain_episodes,
                                    args.seed + 1_000_000, args.gamma)
        behavior_clone(model, data, args.pretrain_epochs, args.batch_size)
        model.save(f"{output}-pretrained")
        print(f"pretrained_model={output}-pretrained.zip")
        if opponents.get("snapshot", 0) > 0:
            add_snapshot(model, snapshot_dir / f"{output.stem}_0", args.max_snapshots)

    callbacks = []
    if opponents.get("snapshot", 0) > 0:
        callbacks.append(OpponentSnapshotCallback(args.snapshot_frequency, snapshot_dir, output.stem,
                                                  args.max_snapshots, start=start_timesteps))
    if args.checkpoint_frequency:
        checkpoint_dir = output.parent / f"{output.stem}-checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        callbacks.append(CheckpointCallback(
            # CheckpointCallback counts vectorized calls, not timesteps.
            save_freq=max(1, args.checkpoint_frequency // args.n_envs),
            save_path=str(checkpoint_dir),
            name_prefix=output.stem,
        ))
    if args.timesteps:
        model.learn(total_timesteps=args.timesteps, callback=CallbackList(callbacks), progress_bar=False,
                    reset_num_timesteps=not args.resume)
    model.save(str(output))
    print(f"model={output}.zip")
    print(f"timesteps={model.num_timesteps}")


if __name__ == "__main__":
    main()
