"""Training-harness pieces for Twilight Struggle that run without training: opponent mix, win reward, CLI."""
from __future__ import annotations

import random

import pytest

from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv, parse_opponent_mix
from app.games.twilight_struggle.rl_policies import FIXED_POLICIES


def test_parse_opponent_mix_accepts_snapshot_and_rejects_bad_input():
    assert parse_opponent_mix("rule=0.6,random=0.1,snapshot=0.3") == {"rule": 0.6, "random": 0.1, "snapshot": 0.3}
    with pytest.raises(ValueError):
        parse_opponent_mix("snapshot=1")  # needs a fixed opponent for the empty-pool case
    with pytest.raises(ValueError):
        parse_opponent_mix("bogus=1")
    with pytest.raises(ValueError):
        parse_opponent_mix("rule=-1,random=1")


def test_snapshot_weight_is_ignored_until_a_snapshot_is_registered():
    env = TwilightStruggleGymEnv(seed=1, opponents={"rule": 0.1, "snapshot": 0.9})
    for seed in range(5):
        _, info = env.reset(seed=seed)
        assert info["opponent"] == "rule"
    assert env.add_opponent_snapshot("a.zip", max_snapshots=2) == 1
    env.add_opponent_snapshot("b.zip", max_snapshots=2)
    assert env.add_opponent_snapshot("c.zip", max_snapshots=2) == 2
    assert env.snapshot_paths == ["b.zip", "c.zip"]


def _play_out(env, seed):
    env.reset(seed=seed)
    rng = random.Random(seed)
    total = 0.0
    while True:
        _, reward, terminated, truncated, info = env.step(
            FIXED_POLICIES["random"](env.adapter, env.adapter_observation, rng)
        )
        total += reward
        if terminated or truncated:
            return total, terminated, info


def test_win_reward_is_zero_sum_with_the_default_off_and_applied_when_set():
    base = TwilightStruggleGymEnv(seed=2, opponents={"rule": 1.0}, learner_faction="us", win_reward=0.0, curriculum_stage=0)
    bonus = TwilightStruggleGymEnv(seed=2, opponents={"rule": 1.0}, learner_faction="us", win_reward=1.0, curriculum_stage=0)
    total_base, done_base, info_base = _play_out(base, 2)
    total_bonus, done_bonus, info_bonus = _play_out(bonus, 2)
    assert done_base and done_bonus
    
    # Account for DEFCON-1 penalty if applicable
    terminal_base = info_base.get("terminal_result") or {}
    winner_base = info_base.get("winner")
    learner_base = info_base.get("learner")
    expected_base = base.reward_scale * info_base["vp_margin"]
    if terminal_base.get("reason") == "defcon_1" and winner_base is not None and learner_base is not None and winner_base != learner_base:
        expected_base -= 2.0
    assert total_base == pytest.approx(expected_base)
    
    terminal_bonus = info_bonus.get("terminal_result") or {}
    winner_bonus = info_bonus.get("winner")
    learner_bonus = info_bonus.get("learner")
    expected_bonus = bonus.reward_scale * info_bonus["vp_margin"]
    if terminal_bonus.get("reason") == "defcon_1" and winner_bonus is not None and learner_bonus is not None and winner_bonus != learner_bonus:
        expected_bonus -= 2.0
    expected_bonus += 1.0 if winner_bonus == learner_bonus else -1.0
    assert total_bonus == pytest.approx(expected_bonus)


def test_training_cli_parser_builds_with_documented_defaults():
    from scripts.train_twilight_ppo import build_parser

    args = build_parser().parse_args([])
    assert args.gamma == 0.9995 and args.win_reward == 1.0 and args.learner_faction is None
    assert args.output == "runtime/twilight-ppo"
