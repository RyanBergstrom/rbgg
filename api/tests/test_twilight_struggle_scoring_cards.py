from __future__ import annotations

import pytest

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.scoring import score_region


def _ussr_adjacent_countries(data: dict, region: str) -> list[str]:
    names: list[str] = []
    for left, right in data["superpower_adjacency"]:
        for country, superpower in ((left, right), (right, left)):
            if superpower == "USSR" and country in data["countries"]:
                if data["countries"][country]["region"] == region:
                    names.append(country)
    return sorted(set(names))


@pytest.mark.parametrize(
    ("region", "presence_value", "expects_adjacency"),
    [
        ("Middle East", 3, False),
        ("Africa", 1, False),
        ("South America", 2, False),
        ("Europe", 3, True),
        ("Central America", 1, True),
    ],
)
def test_adjacency_bonus_matches_scoring_card_text(
    region: str, presence_value: int, expects_adjacency: bool
) -> None:
    data = load_country_data()
    candidates = _ussr_adjacent_countries(data, region)
    if not candidates:
        pytest.skip(f"No USSR-adjacent country in {region} in the country reference")
    country = candidates[0]
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    influence[country]["us"] = data["countries"][country]["stability"]

    result = score_region(region, influence, data)

    battleground_bonus = 1 if data["countries"][country]["battleground"] else 0
    adjacency_bonus = 1 if expects_adjacency else 0
    # Only one controlled country is needed for the adjacency clause to apply.
    expected = presence_value + battleground_bonus + adjacency_bonus
    assert result["presence"]["us"]
    assert result["score"]["us"] == expected
