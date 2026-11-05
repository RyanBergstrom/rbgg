from __future__ import annotations

import pytest

from app.games.twilight_struggle.country_data import are_adjacent, load_country_data
from app.games.twilight_struggle.rules import (
    controlled_by,
    influence_operation_cost,
    apply_influence_operations,
    resolve_coup,
    resolve_realignment,
    award_military_operations_penalty,
    check_victory_conditions,
    influence_points_from_operations,
)


def test_country_reference_loads_expected_spaces_and_confirmed_values() -> None:
    data = load_country_data()
    assert len(data["countries"]) == 85
    assert data["countries"]["Canada"] == {
        "name": "Canada",
        "region": "Europe",
        "stability": 4,
        "battleground": False,
    }
    assert data["countries"]["China"]["stability"] is None
    assert data["countries"]["China"]["battleground"] is None
    assert data["countries"]["Australia"]["region"] == "Asia"
    assert "United States" in data["superpowers"]
    assert "USSR" in data["superpowers"]


def test_country_adjacency_aliases_and_symmetry() -> None:
    data = load_country_data()
    assert are_adjacent("Dominican Republic", "Haiti", data)
    assert are_adjacent("Haiti", "Dominican Rep", data)
    assert are_adjacent("USA", "Mexico", data) is False
    assert all(
        country in data["adjacency"][neighbor]
        for country, neighbors in data["adjacency"].items()
        for neighbor in neighbors
    )
    assert {"United States", "Canada"} in [set(edge) for edge in data["superpower_adjacency"]]


def test_country_data_can_be_corrected_by_config_file_only(tmp_path) -> None:
    config = tmp_path / "countries.md"
    config.write_text(
        "Country | Region | Stability | BG | Adjacent Countries\n"
        "A | Europe | 2 | N | B\n"
        "B | Europe | 3 | Y | —\n",
        encoding="utf-8",
    )
    data = load_country_data(config)
    assert are_adjacent("A", "B", data)
    assert are_adjacent("B", "A", data)
    assert data["countries"]["B"]["battleground"] is True


def test_control_and_influence_operation_cost() -> None:
    country = {"stability": 3}
    assert controlled_by({"us": 3, "ussr": 0}, country) == "us"
    assert controlled_by({"us": 3, "ussr": 3}, country) is None
    assert controlled_by({"us": 2, "ussr": 3}, country) == "ussr"
    assert influence_operation_cost("us", {"us": 0, "ussr": 3}, country) == 2
    assert influence_operation_cost("ussr", {"us": 0, "ussr": 3}, country) == 1
    assert influence_points_from_operations(
        "us", 5, {"us": 0, "ussr": 3}, country
    ) == 2

def test_influence_placements_are_connected_and_atomic() -> None:
    data = load_country_data()
    board = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    board["Guatemala"]["us"] = 1

    result = apply_influence_operations(
        "us", 2, [{"country": "Mexico", "points": 2}], board, data
    )
    assert result["board"]["Mexico"]["us"] == 2
    assert result["operations_remaining"] == 0
    assert board["Mexico"]["us"] == 0

    with pytest.raises(ValueError, match="not adjacent"):
        apply_influence_operations(
            "us",
            2,
            [{"country": "Mexico", "points": 1}, {"country": "Nicaragua", "points": 1}],
            board,
            data,
        )
    assert board["Mexico"]["us"] == 0

    empty_board = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    allowed = apply_influence_operations(
        "us", 1, [{"country": "Mexico", "points": 1}], empty_board, data
    )
    assert allowed["board"]["Mexico"]["us"] == 1

    try:
        apply_influence_operations("us", 1, [{"country": "Mexico", "points": 2}], board, data)
    except ValueError as error:
        assert "exceed" in str(error)
    else:
        raise AssertionError("over-budget placement should be rejected")
    assert board["Mexico"]["us"] == 0


def test_battleground_coup_removes_influence_and_costs_defcon() -> None:
    data = load_country_data()
    board = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    board["Italy"]["ussr"] = 2

    result = resolve_coup("us", "Italy", 3, 6, board, data)

    assert result["coup_margin"] == 5
    assert result["opponent_influence_removed"] == 2
    assert result["friendly_influence_placed"] == 3
    assert result["defcon_loss"] == 1
    assert board["Italy"] == {"us": 0, "ussr": 2}


def test_realignment_applies_target_and_adjacent_control_modifiers() -> None:
    data = load_country_data()
    board = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    board["Mexico"]["us"] = 2
    board["Guatemala"]["us"] = 1
    board["Mexico"]["ussr"] = 1

    result = resolve_realignment("Mexico", 2, 3, board, data)

    assert result["modifiers"] == {"us": 3, "ussr": 0}
    assert result["modified_rolls"] == {"us": 5, "ussr": 3}
    assert result["influence_removed"] == {"us": 0, "ussr": 1}
    assert board["Mexico"]["ussr"] == 1


def test_military_operations_shortfall_awards_opponent_and_resets() -> None:
    result = award_military_operations_penalty({"us": 3, "ussr": 5}, 5)

    assert result["shortfall"] == {"us": 2, "ussr": 0}
    assert result["vp_delta_us"] == -2
    assert result["reset_military_operations"] == {"us": 0, "ussr": 0}


def test_victory_conditions_respect_defcon_and_final_scoring_rules() -> None:
    assert check_victory_conditions(20, 5, "ussr") == {
        "winner": "us", "reason": "twenty_vp"
    }
    assert check_victory_conditions(20, 5, "ussr", final_scoring=True) is None
    assert check_victory_conditions(0, 1, "us") == {
        "winner": "ussr", "reason": "defcon_1"
    }
    assert check_victory_conditions(0, 5, "ussr", europe_control="us") == {
        "winner": "us", "reason": "europe_control"
    }


def test_defcon_restrictions_block_region_actions() -> None:
    data = load_country_data()
    board = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    board["Italy"]["ussr"] = 1
    board["Iran"]["ussr"] = 1

    with pytest.raises(ValueError, match="prohibited in Europe"):
        resolve_coup("us", "Italy", 3, 5, board, data, defcon=4)
    with pytest.raises(ValueError, match="prohibited in Middle East"):
        resolve_realignment("Iran", 4, 2, board, data, defcon=2)
    with pytest.raises(ValueError, match="DEFCON 1"):
        resolve_realignment("Mexico", 4, 2, board, data, defcon=1)
