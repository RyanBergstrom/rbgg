import pytest

from scripts.evaluate_twilight_model import mean_interval, summarize, wilson_interval


def test_wilson_interval_is_finite_and_contains_observed_rate():
    low, high = wilson_interval(12, 98)
    assert low < 12 / 98 < high
    assert 0 <= low < high <= 1


def test_summarize_reports_completion_and_completed_game_metrics_separately():
    results = [
        {"finished": True, "win": True, "margin": 8.0, "stalled": False},
        {"finished": True, "win": False, "margin": -2.0, "stalled": False},
        {"finished": False, "win": False, "margin": 0.0, "stalled": True},
    ]

    result = summarize(results)

    assert result["games"] == 3
    assert result["finished"] == 2
    assert result["stalled"] == 1
    assert result["wins"] == 1
    assert result["win_rate"] == pytest.approx(0.5)
    assert result["mean_vp"] == pytest.approx(3.0)
    assert result["finish_ci95"][0] < 2 / 3 < result["finish_ci95"][1]
    assert result["win_ci95"][0] < 0.5 < result["win_ci95"][1]


def test_mean_interval_handles_empty_and_single_value_samples():
    assert mean_interval([])[0] != mean_interval([])[0]  # NaN for no observations
    assert mean_interval([3.5]) == (3.5, 3.5)
