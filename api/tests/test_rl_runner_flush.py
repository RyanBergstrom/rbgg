from io import StringIO

from app.core.rl_runner import run_episode
from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv


class TrackingStream(StringIO):
    def __init__(self):
        super().__init__()
        self.flushes = 0

    def flush(self):
        self.flushes += 1
        super().flush()


def test_episode_summary_flush_is_opt_in():
    stream = TrackingStream()
    run_episode(
        LostCitiesReferenceEnv(seed=703),
        episode=0,
        seed=703,
        summary_stream=stream,
        flush_summary=True,
    )

    assert stream.flushes == 1
    assert stream.getvalue().endswith("\n")