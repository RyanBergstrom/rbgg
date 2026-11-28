"""Fields of Fire sequence of play (rulebook section 3), as reference data.

This is the single source for the on-screen turn tracker. Phase ids match
``validator.PHASES``. Rule references point to the rulebook sections.

Offensive missions (e.g. Normandy Mission 1) run Enemy Activity (3.4) after
Friendly Command (3.3); defensive missions run it before (3.2). The order
here follows the offensive sequence used by the scenario configs.
"""
from __future__ import annotations

from typing import Any

TURN_SEQUENCE: list[dict[str, Any]] = [
    {
        "phase": "setup",
        "label": "Setup",
        "rule": "2.3",
        "segments": [
            {"label": "Place units on the Staging Area cards", "rule": "2.3.5"},
            {"label": "Lay out the map and start the mission", "rule": "2.3"},
        ],
    },
    {
        "phase": "friendly_higher_hq_event",
        "label": "Higher HQ Event",
        "rule": "3.1",
        "segments": [
            {"label": "Draw an Action card; HQ icon means a Higher HQ Event (from Turn 2)", "rule": "3.1"},
        ],
    },
    {
        "phase": "friendly_command",
        "label": "Friendly Command",
        "rule": "3.3",
        "segments": [
            {"label": "Activation - BN HQ", "rule": "3.3.1a"},
            {"label": "Activation - CO HQ", "rule": "3.3.1b"},
            {"label": "Activation - PLT HQ/CO Staff", "rule": "3.3.1c"},
            {"label": "Initiative - CO HQ", "rule": "3.3.2a"},
            {"label": "Initiative - PLT HQ", "rule": "3.3.2b"},
            {"label": "Initiative - CO Staff", "rule": "3.3.2c"},
            {"label": "General Initiative", "rule": "3.3.2d"},
        ],
    },
    {
        "phase": "enemy_activity",
        "label": "Enemy Activity",
        "rule": "3.4",
        "segments": [
            {"label": "Enemy Higher HQ Event (from Turn 2)", "rule": "3.4.1"},
            {"label": "Enemy Activity Check: place PC markers, check every enemy unit", "rule": "3.4.2"},
        ],
    },
    {
        "phase": "mutual_capture_retreat",
        "label": "Capture & Retreat",
        "rule": "3.5",
        "segments": [
            {"label": "Capture Paralyzed / Litter Teams", "rule": "3.5.1"},
            {"label": "Retreat under VOF markers", "rule": "3.5.2"},
        ],
    },
    {
        "phase": "at_combat_vehicle_movement",
        "label": "AT Combat & Vehicles",
        "rule": "3.6",
        "segments": [
            {"label": "Fire AT-capable units; move or spot with vehicles; reaction fire", "rule": "3.6"},
        ],
    },
    {
        "phase": "mutual_combat",
        "label": "Mutual Combat",
        "rule": "3.7",
        "segments": [
            {"label": "Fire Mission update: remove incoming markers, flip Pending", "rule": "3.7.1"},
            {"label": "Potential Contact evaluation", "rule": "3.7.2"},
            {"label": "Pinned recovery", "rule": "3.7.3"},
            {"label": "Combat effects on units under VOF", "rule": "3.7.4"},
        ],
    },
    {
        "phase": "clean_up",
        "label": "Clean Up",
        "rule": "3.8",
        "segments": [
            {"label": "Remove temporary markers; evacuate casualties", "rule": "3.8"},
            {"label": "Adjust VOF, PDF and Activity Levels", "rule": "3.8"},
        ],
    },
    {
        "phase": "game_over",
        "label": "Game Over",
        "rule": "—",
        "segments": [],
    },
]
