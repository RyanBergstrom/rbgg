"""Train a masked PPO Twilight Struggle policy with dynamic opponent curriculum and rule pretraining.

Combines two improvement strategies:

1. **Dynamic opponent curriculum (Option 2):** Tracks US win rate vs each opponent type
   (rule, random, snapshot) and dynamically reweights the opponent mix during training.
   If US is beating an opponent too often (>70%), that opponent's weight decreases.
   If US is losing too often (<40%), that opponent's weight increases. This keeps the
   learner in a zone of productive challenge.

2. **Behavior cloning from rule policy (Option 3):** Pretrains the policy on actions
   from the fixed rule policy before PPO self-play. Gives US a competent heuristic
   foundation so training starts from "plays like rule" rather than random.

Usage example:

    python train_twilight_ppo_v10.py ^
        --timesteps 1000000 ^
        --resume PATH_TO_V72 ^
        --opponents "rule=0.7,random=0.2,snapshot=0.1" ^
        --learner-faction us ^
        --pretrain-episodes 2000 ^
        --pretrain-teacher rule ^
        --output PATH_TO_OUTPUT ^
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
from collections import defaultdict
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv, parse_opponent_mix
from app.games.twilight_struggle.rl_policies import FIXED_POLICIES


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


class DynamicOpponentCallback(BaseCallback):
    """Adjust opponent mix weights based on US win rate vs each opponent type.

    Tracks win rate per opponent (rule, random, snapshot) for learner faction == "us".
    Every ``check_interval`` timesteps, shifts weights toward opponents the learner
    struggles against and away from opponents it dominates.
    """

    def __init__(
        self,
        check_interval: int = 50_000,
        window: int = 100,
        min_weight: float = 0.05,
        max_weight: float = 0.60,
        low_threshold: float = 0.40,
        high_threshold: float = 0.70,
        step: float = 0.10,
    ):
        super().__init__()
        self.check_interval = check_interval
        self.window = window
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.step = step
        self.last_check = 0
        self.wins: dict[str, list[float]] = defaultdict(list)
        self.total: dict[str, int] = defaultdict(int)

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        dones = self.locals.get("dones", [])
        for info, done in zip(infos, dones):
            if not done or info is None:
                continue
            if info.get("faction") != "us":
                continue
            opponent = info.get("opponent", "rule")
            winner = info.get("winner")
            learner = info.get("learner")
            won = winner is not None and winner == learner
            self.wins[opponent].append(float(won))
            self.total[opponent] += 1
            if len(self.wins[opponent]) > self.window:
                self.wins[opponent] = self.wins[opponent][-self.window:]

        if self.num_timesteps < self.last_check + self.check_interval:
            return True
        self.last_check = self.num_timesteps

        envs = self.model.get_env()
        if envs is None:
            return True

        try:
            current = envs.envs[0].opponents
        except (AttributeError, IndexError):
            return True

        new_weights = dict(current)
        changed = False

        for opponent in ("rule", "random", "snapshot"):
            recent = self.wins.get(opponent, [])
            if len(recent) < 10:
                continue
            win_rate = float(np.mean(recent))
            weight = new_weights.get(opponent, 0.0)

            if win_rate > self.high_threshold and opponent != "snapshot":
                # US is dominating this opponent — make it less likely
                new_weight = max(self.min_weight, weight - self.step)
            elif win_rate < self.low_threshold and opponent != "snapshot":
                # US is struggling — make it more likely for more signal
                new_weight = min(self.max_weight, weight + self.step)
            else:
                new_weight = weight

            if abs(new_weight - weight) > 1e-6:
                new_weights[opponent] = new_weight
                changed = True

        if changed:
            # Normalize to sum to 1
            total = sum(new_weights.values())
            new_weights = {k: v / total for k, v in new_weights.items()}

            print(
                f"[DynamicOpponent] timesteps={self.num_timesteps} "
                f"weights={ {k: round(v, 3) for k, v in new_weights.items()} } "
                f"win_rates={ {k: round(float(np.mean(v)), 2) for k, v in self.wins.items() if v} }",
                flush=True,
            )

            try:
                for env in envs.envs:
                    env.set_opponent_weights(new_weights)
            except Exception as exc:
                print(f"[DynamicOpponent] failed to apply weights: {exc}", flush=True)

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
    parser.add_argument("--opponents", default="rule=0.7,random=0.2,snapshot=0.1",
                        help="Initial opponent mix weights.")
    parser.add_argument("--learner-faction", choices=("us", "ussr"), required=True,
                        help="Faction the learner plays.")
    parser.add_argument("--curriculum-stage", type=int, default=2, choices=(0, 1, 2),
                        help="Manual curriculum stage: 0=auto-DONE, 1=guided DONE, 2=full staged.")
    parser.add_argument("--max-episode-steps", type=int, default=3000)
    parser.add_argument("--reward-scale", type=float, default=0.1)
    parser.add_argument("--timeout-penalty", type=float, default=-0.5)
    parser.add_argument("--win-reward", type=float, default=1.0)
    parser.add_argument("--resume", help="Continue training this saved model (.zip).")
    parser.add_argument("--pretrain-episodes", type=int, default=2000,
                        help="Behavior cloning episodes from teacher before PPO; 0 disables.")
    parser.add_argument("--pretrain-teacher", choices=sorted(FIXED_POLICIES), default="rule",
                        help="Teacher policy for behavior cloning.")
    parser.add_argument("--pretrain-epochs", type=int, default=10)
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
    if "." in Path(args.output).name and not args.output.endswith(".zip"):
        parser.error("--output must not contain a dot before the final component (SB3 would not append .zip)")

    net_arch = [int(width) for width in args.net_arch.split(",")]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    opponents = parse_opponent_mix(args.opponents)

    env_kwargs = {
        "opponents": opponents,
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

    # Behavior cloning from rule policy (Option 3)
    if args.pretrain_episodes:
        teacher_kwargs = {**env_kwargs, "opponents": {k: v for k, v in opponents.items() if k != "snapshot"}}
        from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv as _GymEnv
        teacher_env = _GymEnv(**{**teacher_kwargs, "seed": args.seed + 1_000_000})
        selector = FIXED_POLICIES[args.pretrain_teacher]
        rng = random.Random(args.seed + 2_000_000)
        observations, masks, actions, returns = [], [], [], []
        margins, finished = [], 0
        gamma = args.gamma
        for episode in range(args.pretrain_episodes):
            vector, _ = teacher_env.reset(seed=args.seed + 1_000_000 + episode)
            rewards = []
            done = False
            while not done:
                if not teacher_env.action_masks().any():
                    break
                observations.append(vector)
                masks.append(teacher_env.action_masks())
                action = selector(teacher_env.adapter, teacher_env.adapter_observation, rng)
                actions.append(action)
                vector, reward, terminated, truncated, info = teacher_env.step(action)
                rewards.append(reward)
                done = terminated or truncated
            if rewards and info.get("terminal_result") is not None:
                finished += 1
                margins.append(info["vp_margin"])
            running = 0.0
            episode_returns = []
            for reward in reversed(rewards):
                running = reward + gamma * running
                episode_returns.append(running)
            returns.extend(reversed(episode_returns))
        teacher_env.close()

        print(f"pretrain teacher={args.pretrain_teacher} episodes={args.pretrain_episodes} "
              f"finished={finished} decisions={len(actions)} "
              f"avg_vp_margin={np.mean(margins) if margins else float('nan'):.2f}", flush=True)

        data = (
            np.asarray(observations, dtype=np.float32),
            np.asarray(masks, dtype=bool),
            np.asarray(actions, dtype=np.int64),
            np.asarray(returns, dtype=np.float32),
        )

        import torch
        observations, masks, actions, returns = (
            torch.as_tensor(array, device=model.device) for array in data
        )
        policy = model.policy
        policy.set_training_mode(True)
        generator = torch.Generator().manual_seed(0)
        for epoch in range(args.pretrain_epochs):
            order = torch.randperm(len(actions), generator=generator).to(model.device)
            policy_losses, value_losses, correct = [], [], 0
            for start in range(0, len(actions), args.batch_size):
                index = order[start:start + args.batch_size]
                values, log_prob, _ = policy.evaluate_actions(
                    observations[index], actions[index], action_masks=masks[index]
                )
                policy_loss = -log_prob.mean()
                value_loss = torch.nn.functional.mse_loss(values.flatten(), returns[index])
                loss = policy_loss + 0.5 * value_loss
                policy.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(policy.parameters(), model.max_grad_norm)
                policy.optimizer.step()
                policy_losses.append(policy_loss.item())
                value_losses.append(value_loss.item())
                with torch.no_grad():
                    probs = policy.get_distribution(
                        observations[index], action_masks=masks[index]
                    ).distribution.probs
                    correct += int((probs.argmax(dim=1) == actions[index]).sum())
            print(f"bc_epoch={epoch + 1} policy_loss={np.mean(policy_losses):.4f} "
                  f"value_loss={np.mean(value_losses):.4f} accuracy={correct / len(actions):.3f}", flush=True)
        policy.set_training_mode(False)
        model.save(f"{output}-pretrained")
        print(f"pretrained_model={output}-pretrained.zip", flush=True)

    callbacks: list[BaseCallback] = [EpisodeStatsCallback(), DynamicOpponentCallback()]
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
