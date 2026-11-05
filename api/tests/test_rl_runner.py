import json

from app.core.rl_runner import run_episodes
from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv


def test_runner_streams_episode_summaries_without_retaining_states(tmp_path):
    output = tmp_path / "episodes.jsonl"
    statistics = run_episodes(
        lambda seed: LostCitiesReferenceEnv(seed=seed),
        episodes=2,
        seed=700,
        summary_path=output,
    )

    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert statistics.episodes == 2
    assert statistics.total_steps == sum(record["steps"] for record in records)
    assert statistics.min_steps <= statistics.max_steps
    assert all("action_counts" in record for record in records)
    assert all("final_scores" in record for record in records)
    assert set(statistics.as_dict()["average_final_scores"]) == {"player_1", "player_2"}
    assert "episode_lengths" not in statistics.as_dict()


def test_runner_is_seed_deterministic():
    factory = lambda seed: LostCitiesReferenceEnv(seed=seed)
    first = run_episodes(factory, episodes=2, seed=701)
    second = run_episodes(factory, episodes=2, seed=701)

    assert first.as_dict() == second.as_dict()


def test_runner_accepts_an_alternate_action_selector():
    def first_legal(adapter, observation, rng):
        return next(index for index, enabled in enumerate(observation["action_mask"]) if enabled)

    statistics = run_episodes(
        lambda seed: LostCitiesReferenceEnv(seed=seed),
        episodes=1,
        seed=702,
        action_selector=first_legal,
    )

    assert statistics.episodes == 1
    assert statistics.total_steps > 0