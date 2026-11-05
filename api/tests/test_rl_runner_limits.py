from app.core.rl_runner import run_episodes
from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv


def test_runner_can_bound_an_episode_for_policy_diagnostics(tmp_path):
    stats = run_episodes(
        lambda seed: LostCitiesReferenceEnv(seed=seed),
        episodes=1,
        seed=707,
        summary_path=tmp_path / "bounded.jsonl",
        max_steps_per_episode=3,
    )

    assert stats.episodes == 1
    assert stats.total_steps == 3
    assert '"terminated":false' in (tmp_path / "bounded.jsonl").read_text()