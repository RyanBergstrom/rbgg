"""Deterministic default choices for choice-required headline events.

Headlines are committed secretly and carry no choice input, so a choice-required
headline resolves with its first legal candidate in a fixed order. The engine's
own rules decide legality: callers must keep only candidates the event accepts.

This is a rules simplification (a player does not pick their own target for a
headline). Review it against the 2nd Edition rulebook before playable sign-off.
"""
from __future__ import annotations

import random
import re
from typing import Any

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.scoring import SCORING_CARD_REGIONS

EASTERN_EUROPE = ("E. Germany", "Poland", "Czechoslovakia", "Hungary", "Romania", "Bulgaria")


def _names(data: dict[str, Any], predicate) -> list[str]:
    return sorted(name for name, info in data["countries"].items() if predicate(name, info))


def _hand_ids(gd: dict[str, Any], faction: str) -> list[int]:
    return [c["id"] for c in gd.get("hands", {}).get(faction, [])]


def _hand_discard_ids(gd: dict[str, Any]) -> list[int]:
    return [c["id"] for c in gd.get("discard_pile", []) if not c.get("scoring") and not c.get("special")]


def named_scoring_regions(gd: dict[str, Any]) -> set[str]:
    """Regions named on US scoring cards in hand (Cambridge Five, card 104)."""
    regions: set[str] = set()
    for card in gd.get("hands", {}).get("us", []):
        if not card.get("scoring"):
            continue
        key = re.sub(r"[^a-z ]", "", card.get("name", "").casefold()).strip()
        region = SCORING_CARD_REGIONS.get(key)
        if region:
            regions.add(region)
    return regions


def candidate_choices(
    gd: dict[str, Any],
    card: dict[str, Any],
    faction: str,
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    """Return candidate ``event_choices`` payloads for ``card``.

    Only keys the card's handler reads are populated; unknown handlers get no
    candidates. Order is deterministic unless ``rng`` is given, in which case the
    list is shuffled. The event's own validation decides which candidates count.
    """
    data = load_country_data()
    countries = gd.get("countries", {})
    handler = card.get("effect_handler")
    out: list[dict[str, Any]] = []

    def add(payload: dict[str, Any]) -> None:
        out.append(payload)

    def us(name: str) -> int:
        return countries.get(name, {}).get("us", 0)

    def ussr(name: str) -> int:
        return countries.get(name, {}).get("ussr", 0)

    if handler == "ask_not_what":
        ids = _hand_ids(gd, faction)
        for k in range(0, min(len(ids), 3) + 1):
            add({"ask_not_what": ids[:k]})
    elif handler == "our_man_in_tehran":
        top = [c["id"] for c in gd.get("draw_pile", [])[:5]]
        for k in range(0, len(top) + 1):
            add({"our_man_in_tehran": top[:k]})
    elif handler == "che":
        targets = _names(
            data,
            lambda n, i: i.get("region") in {"Central America", "South America", "Africa"}
            and not i.get("battleground") and us(n) > 0,
        )
        for first in targets[:6]:
            add({"che": first})
    elif handler == "star_wars":
        for cid in _hand_discard_ids(gd):
            add({"star_wars": cid})
    elif handler == "reformer":
        europe = _names(data, lambda n, i: i.get("region") == "Europe")
        ahead = (gd.get("tracks") or {}).get("victory_points", 0) < 0
        total = 6 if ahead else 4
        for start in range(0, min(len(europe), 6)):
            spread: dict[str, int] = {}
            remaining = total
            for pick in europe[start:] + europe[:start]:
                if remaining <= 0:
                    break
                take = min(2, remaining)
                spread[pick] = take
                remaining -= take
            if remaining == 0:
                add({"reformer": spread})
    elif handler == "aldrich_ames_remix":
        for cid in _hand_ids(gd, "us")[:6]:
            add({"aldrich_ames_remix": cid})
    elif handler == "chernobyl":
        from app.games.twilight_struggle.scoring import load_scoring_config

        for region in sorted(load_scoring_config()["regions"]):
            add({"chernobyl": region})
    elif handler == "latin_america_debt_crisis":
        sa = _names(data, lambda n, i: i.get("region") == "South America")
        for a in sa[:4]:
            for b in sa[:4]:
                if a != b:
                    add({"debt_crisis_countries": [a, b]})
    elif handler == "one_small_step":
        add({})
    elif handler == "iran_iraq_war":
        add({"iran_iraq_war": "Iran"})
        add({"iran_iraq_war": "Iraq"})
    elif handler == "truman_doctrine":
        for name in _names(data, lambda n, i: i.get("region") == "Europe")[:6]:
            add({"truman_doctrine": name})
    elif handler == "socialist_governments":
        western = {"U.K.", "Norway", "Sweden", "Denmark", "Benelux", "France",
                   "Spain/Portugal", "W. Germany", "Italy", "Greece", "Turkey"}
        spots = sorted(n for n in western if us(n) > 0)
        for a in spots:
            for b in spots:
                for c in spots:
                    dist: dict[str, int] = {}
                    for name in (a, b, c):
                        dist[name] = dist.get(name, 0) + 1
                    if sum(dist.values()) == 3 and all(v <= 2 and v <= us(k) for k, v in dist.items()):
                        add({"socialist_governments": dict(dist)})
    elif handler == "warsaw_pact_formed":
        eastern = sorted(n for n in EASTERN_EUROPE if us(n) > 0)
        if len(eastern) >= 4:
            add({"warsaw_pact_formed": {"mode": "remove_us", "countries": eastern[:4]}})
        pool = sorted(n for n in EASTERN_EUROPE if us(n) == 0)
        spread: dict[str, int] = {}
        remaining = 5
        for name in pool:
            if remaining <= 0:
                break
            take = min(2, remaining)
            spread[name] = take
            remaining -= take
        if remaining == 0 and spread:
            add({"warsaw_pact_formed": {"mode": "add_ussr", "distribution": spread}})
    elif handler == "olympic_games":
        add({"olympic_games": "participate"})
        add({"olympic_games": "boycott"})
    elif handler == "east_european_unrests":
        eastern = sorted(n for n in EASTERN_EUROPE if ussr(n) >= 1)
        removal = 2 if gd.get("turn", 1) >= 8 else 1
        eligible = [n for n in eastern if ussr(n) >= removal]
        if len(eligible) >= 3:
            add({"east_european_unrests": eligible[:3]})
    elif handler in {"decolonization", "colonial_rearguards"}:
        southeast_asia = {"Burma", "Laos/Cambodia", "Thailand", "Vietnam", "Malaysia", "Indonesia", "Philippines"}
        pool = sorted(n for n, i in data["countries"].items() if i.get("region") == "Africa" or n in southeast_asia)
        add({handler: pool[:4]})
    elif handler == "south_african_unrest":
        add({"south_african_unrest": {"mode": "south_africa"}})
        add({"south_african_unrest": {"mode": "adjacent"}})
    elif handler == "de_stalinization":
        ussr_spots = sorted(n for n in countries if ussr(n) > 0)
        place_spots = sorted(n for n in data["countries"] if us(n) == 0 and n not in ussr_spots)[:2]
        for src in ussr_spots[:3]:
            for dst in place_spots:
                amount = min(2, ussr(src), 4)
                if amount > 0:
                    add({"de_stalinization": {"from": {src: amount}, "to": {dst: amount}}})
    elif handler == "indo_pakistani_war":
        add({"indo_pakistani_war": "India"})
        add({"indo_pakistani_war": "Pakistan"})
    elif handler == "brush_war":
        nato = "nato" in (gd.get("persistent_events") or {})
        cancelled = set((gd.get("persistent_events") or {}).get("nato_cancelled_countries") or [])
        for name, info in sorted(data["countries"].items()):
            if info.get("stability") not in {1, 2} or name not in countries:
                continue
            if nato and info.get("region") == "Europe" and name not in cancelled and us(name) > 0:
                continue
            add({"brush_war": name})
    elif handler == "suez_crisis":
        spots = sorted(n for n in ("France", "U.K.", "Israel") if us(n) > 0)
        seen: set[tuple[tuple[str, int], ...]] = set()
        for a in spots:
            for b in spots:
                for c in spots:
                    for d in spots:
                        dist: dict[str, int] = {}
                        for name in (a, b, c, d):
                            dist[name] = dist.get(name, 0) + 1
                        if sum(dist.values()) != 4 or any(v > 2 for v in dist.values()):
                            continue
                        if not all(v <= us(k) for k, v in dist.items()):
                            continue
                        key = tuple(sorted(dist.items()))
                        if key not in seen:
                            seen.add(key)
                            add({"suez_crisis": dict(dist)})
    elif handler == "cambridge_five":
        named = named_scoring_regions(gd)
        for name in _names(data, lambda n, i: i.get("region") in named)[:6]:
            add({"cambridge_five": name})
    elif handler == "comecon":
        eastern = sorted(n for n in (*EASTERN_EUROPE, "Yugoslavia") if n in data["countries"] and us(n) == 0)
        if len(eastern) >= 4:
            add({"comecon": eastern[:4]})
    elif handler == "independent_reds":
        for name in ("Yugoslavia", "Romania", "Bulgaria", "Hungary", "Czechoslovakia"):
            add({"independent_reds": name})
    elif handler == "marshall_plan":
        eastern = {*EASTERN_EUROPE, "Yugoslavia"}
        west = sorted(
            n for n, i in data["countries"].items()
            if i.get("region") == "Europe" and n not in eastern and ussr(n) < countries.get(n, {}).get("stability", 0) + 1
        )
        if len(west) >= 7:
            add({"marshall_plan": west[:7]})
    elif handler == "special_relationship":
        if "nato" in (gd.get("persistent_events") or {}):
            for name in ("Benelux", "Denmark", "France", "Italy")[:4]:
                add({"special_relationship": name})
        else:
            for name in data["adjacency"].get("U.K.", []):
                add({"special_relationship": name})
    elif handler == "liberation_theology":
        ca = _names(data, lambda n, i: i.get("region") == "Central America")[:5]
        for a in ca:
            for b in ca:
                if a < b:
                    add({"liberation_theology": {a: 2, b: 1}})
                    add({"liberation_theology": {a: 1, b: 2}})
            for b in ca:
                for c in ca:
                    if a < b < c:
                        add({"liberation_theology": {a: 1, b: 1, c: 1}})
    elif handler == "muslim_revolution":
        if "awacs_sale_played" not in (gd.get("persistent_events") or {}):
            listed = ["Sudan", "Iran", "Iraq", "Egypt", "Libya", "Saudi Arabia", "Syria", "Jordan"]
            for i, a in enumerate(listed):
                for b in listed[i + 1:]:
                    add({"muslim_revolution": [a, b]})
    elif handler == "the_voice_of_america":
        ussr_held = sorted(n for n, i in data["countries"].items() if i.get("region") != "Europe" and ussr(n) > 0)
        for a in ussr_held[:4]:
            add({"the_voice_of_america": {a: min(2, ussr(a))}})
            for b in ussr_held[:4]:
                if a < b:
                    add({"the_voice_of_america": {a: min(2, ussr(a)), b: min(2, ussr(b))}})
    elif handler == "puppet_governments":
        empty = [n for n in sorted(data["countries"]) if us(n) == 0 and ussr(n) == 0]
        if len(empty) >= 3:
            add({"puppet_governments": empty[:3]})
            add({"puppet_governments": empty[-3:]})
    elif handler == "junta":
        for name in _names(data, lambda n, i: i.get("region") in {"Central America", "South America"})[:8]:
            add({"junta": name})
    elif handler == "oas_founded":
        cs = _names(data, lambda n, i: i.get("region") in {"Central America", "South America"})[:6]
        for a in cs:
            add({"oas_founded": {a: 2}})
            for b in cs:
                if a < b:
                    add({"oas_founded": {a: 1, b: 1}})
    elif handler == "marine_barracks_bombing":
        add({"marine_barracks_bombing": {}})
        held = _names(data, lambda n, i: i.get("region") == "Middle East" and n != "Lebanon" and us(n) > 0)
        for name in held[:4]:
            add({"marine_barracks_bombing": {name: min(2, us(name))}})
    elif handler == "ussuri_river_skirmish":
        asia = _names(data, lambda n, i: i.get("region") == "Asia")[:6]
        for i, a in enumerate(asia):
            for b in asia[i + 1:]:
                add({"ussuri_river_skirmish": {a: 2, b: 2}})
    elif handler == "missile_envy":
        # The swapped-in card is the opponent's highest-Ops non-scoring card (first on ties); when it resolves for
        # the phasing faction, its choices ride in the same payload, so reuse that card's candidates.
        opponent = "ussr" if faction == "us" else "us"
        eligible = [c for c in gd.get("hands", {}).get(opponent, []) if not c.get("scoring")]
        if eligible:
            top = max(int(c.get("operations", 0)) for c in eligible)
            taken = next(c for c in eligible if int(c.get("operations", 0)) == top)
            if taken.get("alignment") in {faction, "both"} and taken.get("effect_handler") != "missile_envy":
                out.extend(candidate_choices(gd, taken, faction))

    if rng is not None:
        rng.shuffle(out)
    return out
