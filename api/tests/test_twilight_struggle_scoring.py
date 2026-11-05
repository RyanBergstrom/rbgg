from __future__ import annotations

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.scoring import (
    calculate_major_region_final_score,
    classify_region,
    score_southeast_asia,
    score_region,
    resolve_scoring_card,
)


def test_europe_presence_and_battleground_bonus_are_counted() -> None:
    data = load_country_data()
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    influence["France"]["us"] = 3
    influence["Italy"]["us"] = 2

    result = score_region("Europe", influence, data)

    assert result["presence"]["us"]
    assert result["battleground_count"]["us"] == 2
    assert result["score"]["us"] == 5
    assert result["vp_delta_us"] == 5


def test_domination_requires_a_non_battleground_country() -> None:
    data = load_country_data()
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    for name, amount in {"France": 3, "Italy": 2, "W. Germany": 4, "E. Germany": 3}.items():
        influence[name]["us"] = amount
    influence["France"]["ussr"] = 3

    result = classify_region("Europe", influence, data, set())

    assert result["domination"]["us"] is False


def test_southeast_asia_card_scoring_counts_control_and_double_thailand() -> None:
    data = load_country_data()
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    influence["Thailand"]["us"] = 2
    influence["Burma"]["ussr"] = 2
    influence["Laos/Cambodia"]["us"] = 1

    result = score_southeast_asia(influence, data)

    assert result["score"] == {"us": 3, "ussr": 1}
    assert result["vp_delta_us"] == 2


def test_final_scoring_includes_southeast_asia_and_europe_control() -> None:
    data = load_country_data()
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    for country in data["countries"].values():
        if country["region"] == "Europe" and country["battleground"]:
            influence[country["name"]]["us"] = country["stability"]
    influence["Canada"]["us"] = 4
    influence["Thailand"]["us"] = 2

    result = calculate_major_region_final_score(0, influence, data)

    assert result["winner"] == "us"
    assert result["reason"] == "final_scoring"
    assert result["regions"]["Europe"]["control"]["us"] is True
    assert result["regions"]["Europe"]["score"]["us"] == 6
    assert result["southeast_asia"]["score"]["us"] == 2
    assert result["complete"] is False
    assert "China Card owner" in result["incomplete_reason"]

    with_china_card = calculate_major_region_final_score(
        0, influence, data, china_card_owner="us"
    )
    assert with_china_card["complete"] is True
    assert with_china_card["china_card_vp_delta_us"] == 1


def test_asia_scoring_excludes_southeast_asia_before_final_country_points() -> None:
    data = load_country_data()
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    influence["Thailand"]["us"] = 2

    asia = score_region("Asia", influence, data)
    final = calculate_major_region_final_score(0, influence, data, china_card_owner="us")

    assert asia["presence"] == {"us": False, "ussr": False}
    assert asia["score"] == {"us": 0, "ussr": 0}
    assert final["southeast_asia"]["score"]["us"] == 2
    assert final["region_vp_delta_us"] == 2
    assert final["final_vp_us_relative"] == 3


def test_australia_contributes_to_asia_scoring_not_southeast_asia_scoring() -> None:
    data = load_country_data()
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    influence["Australia"]["us"] = 4

    asia = score_region("Asia", influence, data)
    southeast_asia = score_southeast_asia(influence, data)

    assert asia["presence"]["us"] is True
    assert asia["score"]["us"] == 3
    assert southeast_asia["score"]["us"] == 0


def test_scoring_card_updates_vp_and_checks_europe_control() -> None:
    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    for country in data["countries"].values():
        if country["region"] == "Europe" and country["battleground"]:
            countries[country["name"]]["us"] = country["stability"]
    countries["Canada"]["us"] = 4
    game_data = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    outcome = resolve_scoring_card(
        game_data,
        {"id": 2, "name": "Europe Scoring", "scoring": True},
        "ussr",
        data,
    )

    assert outcome["region"] == "Europe"
    assert outcome["game_data"]["tracks"]["victory_points"] == 6
    assert outcome["terminal_result"] == {"winner": "us", "reason": "europe_control"}
    assert game_data["tracks"]["victory_points"] == 0


def test_southeast_asia_scoring_card_applies_country_delta_once():
    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries["Thailand"]["us"] = 2
    countries["Burma"]["ussr"] = 2
    game_data = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    outcome = resolve_scoring_card(
        game_data,
        {"id": 38, "name": "SouthEast Asia Scoring*", "scoring": True},
        "us",
        data,
    )

    assert outcome["region"] == "Southeast Asia"
    assert outcome["game_data"]["tracks"]["victory_points"] == 1
    assert outcome["terminal_result"] is None


def test_region_control_requires_all_battlegrounds_but_not_all_spaces() -> None:
    data = load_country_data()
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    for country in data["countries"].values():
        if country["region"] == "Europe" and country["battleground"]:
            influence[country["name"]]["us"] = country["stability"]
    influence["Canada"]["us"] = 4

    result = classify_region("Europe", influence, data, set())

    assert result["control"]["us"] is True

    scored = score_region("Europe", influence, data)
    assert scored["score"]["us"] == result["battleground_count"]["us"] + 1


def test_regional_scoring_adds_controlled_countries_adjacent_to_enemy_superpower() -> None:
    data = load_country_data()
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    influence["Canada"]["ussr"] = 4

    result = score_region("Europe", influence, data)

    assert result["score"]["ussr"] == 4
    assert result["vp_delta_us"] == -4

def test_final_scoring_ignores_europe_control_for_winner() -> None:
    data = load_country_data()
    influence = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    for country in data["countries"].values():
        if country["region"] == "Europe" and country["battleground"]:
            influence[country["name"]]["us"] = country["stability"]
    # Give USSR more VP than the US control of Europe contributes.
    result = calculate_major_region_final_score(-20, influence, data)

    assert result["regions"]["Europe"]["control"]["us"] is True
    assert result["winner"] == "ussr"
    assert result["reason"] == "final_scoring"

def test_asia_scoring_card_applies_asia_region_delta_only() -> None:
    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries["Japan"]["us"] = 4
    countries["Thailand"]["us"] = 2
    game_data = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    expected = score_region("Asia", countries, data)["vp_delta_us"]
    outcome = resolve_scoring_card(
        game_data,
        {"id": 1, "name": "Asia Scoring", "scoring": True},
        "us",
        data,
    )

    assert outcome["region"] == "Asia"
    assert expected > 0
    assert outcome["game_data"]["tracks"]["victory_points"] == expected
    assert outcome["terminal_result"] is None


def test_middle_east_scoring_card_applies_middle_east_region_delta_only() -> None:
    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries["Israel"]["us"] = 4
    countries["Lebanon"]["us"] = 1
    game_data = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    expected = score_region("Middle East", countries, data)["vp_delta_us"]
    outcome = resolve_scoring_card(
        game_data,
        {"id": 3, "name": "Middle East Scoring", "scoring": True},
        "us",
        data,
    )

    assert outcome["region"] == "Middle East"
    assert expected > 0
    assert outcome["game_data"]["tracks"]["victory_points"] == expected
    assert outcome["terminal_result"] is None


def test_central_america_scoring_card_applies_region_delta_only() -> None:
    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries["Mexico"]["us"] = 2
    countries["Guatemala"]["us"] = 1
    countries["Honduras"]["us"] = 2
    game_data = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    expected = score_region("Central America", countries, data)["vp_delta_us"]
    outcome = resolve_scoring_card(
        game_data,
        {"id": 37, "name": "Central America Scoring", "scoring": True},
        "us",
        data,
    )

    assert outcome["region"] == "Central America"
    assert expected > 0
    assert outcome["game_data"]["tracks"]["victory_points"] == expected
    assert outcome["terminal_result"] is None
