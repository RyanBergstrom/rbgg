"""Test-bot access to the shared default-choice candidates.

The candidate logic lives in ``app.games.twilight_struggle.default_choices`` so the
rules engine (headline defaults) and the random-bot playthrough use one list.
"""
from app.games.twilight_struggle.default_choices import candidate_choices, named_scoring_regions

__all__ = ["candidate_choices", "named_scoring_regions"]
