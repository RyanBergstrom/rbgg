import numpy as np
import pytest

from app.games.lost_cities.gym_env import LostCitiesGymEnv, parse_opponent_mix
from app.games.lost_cities.rl_policies import choose_rule


def _rule_action(env: LostCitiesGymEnv) -> int:
    return choose_rule(env.adapter, env.adapter_observation, None)


def test_gym_env_exposes_fixed_spaces_and_legal_masks():
    env = LostCitiesGymEnv(seed=705)
    observation, info = env.reset()

    assert observation.shape == env.observation_space.shape
    assert observation.dtype == np.float32
    assert env.action_space.n == 22
    assert env.action_masks().shape == (22,)
    assert env.action_masks().any()
    assert info["player_id"] == env.learner
    assert env.adapter.current_player == env.learner


def test_gym_observation_space_allows_negative_score_features():
    env = LostCitiesGymEnv(seed=709)
    observation, _ = env.reset()

    assert env.observation_space.contains(observation)
    assert np.isneginf(env.observation_space.low).all()
    assert np.isposinf(env.observation_space.high).all()


def test_gym_env_step_returns_gymnasium_transition_for_the_learner():
    env = LostCitiesGymEnv(seed=706)
    env.reset()
    action = int(np.flatnonzero(env.action_masks())[0])

    observation, reward, terminated, truncated, info = env.step(action)

    assert observation.shape == env.observation_space.shape
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert truncated is False
    assert info["move"]["move_id"]
    assert info["move"]["player_id"] == env.learner
    assert env.adapter.current_player == env.learner


def test_gym_env_truncates_stalled_episodes():
    env = LostCitiesGymEnv(seed=707, max_episode_steps=1, learner_seat="player_1")
    env.reset()
    action = int(np.flatnonzero(env.action_masks())[0])

    _, _, terminated, truncated, info = env.step(action)

    assert terminated is False
    assert truncated is True
    assert info["truncated_reason"] == "max_episode_steps"
    assert info["reward_breakdown"]["timeout"] == pytest.approx(-0.25)


@pytest.mark.parametrize("opponent", ["rule", "random", "never_play"])
def test_dense_rewards_sum_to_the_final_score_margin(opponent):
    env = LostCitiesGymEnv(seed=711, opponents={opponent: 1.0}, reward_scale=0.01)
    env.reset()
    total = 0.0
    terminated = truncated = False
    while not (terminated or truncated):
        _, reward, terminated, truncated, info = env.step(_rule_action(env))
        total += reward

    assert terminated
    scores = info["final_scores"]
    margin = scores[env.learner] - scores[env.opponent]
    assert total == pytest.approx(0.01 * margin)


def test_playing_a_card_is_charged_immediately():
    env = LostCitiesGymEnv(seed=712, opponents={"never_play": 1.0}, learner_seat="player_1")
    env.reset()
    hand = env.adapter.state["game_data"]["player_hands"]["player_1"]
    numbered = next(index for index, card in enumerate(hand) if not card.endswith("_i"))
    value = int(hand[numbered].split("_")[1])

    _, reward, _, _, info = env.step(numbered)

    assert info["reward_breakdown"]["own_score"] == pytest.approx(0.01 * (value - 20))
    assert reward == pytest.approx(0.01 * (value - 20))


def test_auto_resets_deal_new_games():
    env = LostCitiesGymEnv(seed=713, learner_seat="player_1")
    _, first = env.reset()
    _, second = env.reset()

    assert first["episode_seed"] != second["episode_seed"]
    again = LostCitiesGymEnv(seed=713, learner_seat="player_1")
    assert again.reset()[1]["episode_seed"] == first["episode_seed"]


def test_learner_seat_and_opponent_kind_vary_between_episodes():
    env = LostCitiesGymEnv(seed=714, opponents={"rule": 1.0, "random": 1.0})
    seen = {(env.reset()[1]["player_id"], env.opponent_kind) for _ in range(40)}

    assert {seat for seat, _ in seen} == {"player_1", "player_2"}
    assert {kind for _, kind in seen} == {"rule", "random"}


def test_snapshot_pool_is_bounded_and_unused_until_registered():
    env = LostCitiesGymEnv(seed=715, opponents={"rule": 1.0, "snapshot": 5.0})
    for _ in range(10):
        env.reset()
        assert env.opponent_kind == "rule"

    for index in range(4):
        env.add_opponent_snapshot(f"snapshot-{index}.zip", max_snapshots=2)
    assert env.snapshot_paths == ["snapshot-2.zip", "snapshot-3.zip"]


@pytest.mark.parametrize("spec", ["unknown=1", "rule=-1", "snapshot=1"])
def test_invalid_opponent_mixes_are_rejected(spec):
    with pytest.raises(ValueError):
        parse_opponent_mix(spec)


def test_opponent_mix_parsing():
    assert parse_opponent_mix("rule=0.6,random=0.1,snapshot=0.3") == {
        "rule": 0.6, "random": 0.1, "snapshot": 0.3,
    }


def test_training_script_exposes_main():
    from scripts.train_lost_cities_ppo import behavior_clone, collect_teacher_data, main

    assert callable(main)
    assert callable(behavior_clone)
    assert callable(collect_teacher_data)


def test_resume_hyperparameter_overrides_are_explicit():
    from scripts.train_lost_cities_ppo import override_resume_hyperparameters

    class Model:
        learning_rate = 3e-4
        lr_schedule = None
        ent_coef = 0.01

    model = Model()
    override_resume_hyperparameters(model, learning_rate=1e-4, ent_coef=None)

    assert model.learning_rate == 1e-4
    assert model.lr_schedule(1.0) == pytest.approx(1e-4)
    assert model.ent_coef == 0.01


@pytest.mark.parametrize("extra", [
    ["--resume", "missing-model.zip"],
    ["--resume", __file__, "--pretrain-episodes", "1"],
])
def test_training_script_rejects_invalid_resume(monkeypatch, extra):
    from scripts.train_lost_cities_ppo import main

    monkeypatch.setattr("sys.argv", ["train", "--timesteps", "0", *extra])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2

def test_teacher_data_matches_decisions_and_returns():
    from scripts.train_lost_cities_ppo import collect_teacher_data

    observations, masks, actions, returns = collect_teacher_data(
        {"opponents": {"rule": 1.0}}, "rule", episodes=1, seed=716, gamma=1.0,
    )

    assert len(observations) == len(masks) == len(actions) == len(returns)
    assert masks[np.arange(len(actions)), actions].all()

    replay = LostCitiesGymEnv(opponents={"rule": 1.0})
    replay.reset(seed=716)
    done = False
    while not done:
        _, _, terminated, truncated, info = replay.step(_rule_action(replay))
        done = terminated or truncated
    scores = info["final_scores"]
    # With gamma=1 the first return is the whole scaled final margin.
    assert returns[0] == pytest.approx(0.01 * (scores[replay.learner] - scores[replay.opponent]), abs=1e-5)


def test_reward_totals_accumulate_component_diagnostics():
    env = LostCitiesGymEnv(seed=710)
    env.reset()
    action = int(np.flatnonzero(env.action_masks())[0])

    _, reward, _, _, info = env.step(action)

    assert set(info["reward_breakdown"]) == {"own_score", "opponent_score", "win", "timeout"}
    assert sum(info["reward_totals"].values()) == pytest.approx(reward)
