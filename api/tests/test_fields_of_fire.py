from app.games.fields_of_fire.validator import FieldsOfFireValidator
from app.games.fields_of_fire.terrain import terrain_card, get_card, get_deck, list_decks


def test_initial_state():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    assert gd["phase"] == "setup"
    assert gd["current_player"] == "player_1"


def test_start_mission_transition():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["N01"] * 12
    # Place all units
    for u in gd["company"]["units"]:
        u["position"] = 0
    for veh in gd["company"]["vehicles"]:
        veh["position"] = 0
    state = {"game_data": gd, "players": []}
    moves = v.get_legal_moves(state, "player_1")
    assert any(m["type"] == "start_mission" for m in moves)
    start_move = [m for m in moves if m["type"] == "start_mission"][0]
    new = v.apply_move(state, start_move)
    assert new["game_data"]["phase"] == "friendly_higher_hq_event"


def test_terrain_card_from_csv_starter1():
    card = terrain_card("hill", "N01")
    assert card["card_id"] == "N01"
    assert card["type"] == "hill"
    assert card["name"] == "Hill"
    assert card["cover_high"] == 0
    assert card["cover_low"] == 0
    assert card["elevation"] == 1
    assert card["trafficability"] == "fair"


def test_terrain_card_from_csv_woods():
    card = terrain_card("woods", "N17")
    assert card["card_id"] == "N17"
    assert card["type"] == "woods"
    assert card["name"] == "Woods"
    assert card["cover_high"] == 2
    assert card["cover_low"] == 2
    assert card["borders"] == ["dark", "dark", "dark", "dark"]


def test_get_deck_starter1():
    deck = get_deck("Starter 1 Terrain")
    assert len(deck) == 54
    assert all("card_id" in c for c in deck)
    assert all(c["deck"] == "Starter 1 Terrain" for c in deck)


def test_list_decks():
    decks = list_decks()
    assert "Starter 1 Terrain" in decks
    assert len(decks) > 0


def test_terrain_card_fallback_to_type():
    card = terrain_card("open_field", "A02")
    assert card["card_id"] == "A02"
    assert "type" in card


def test_lay_out_map():
    v = FieldsOfFireValidator()
    state = {"game_data": v.initial_game_data(), "players": []}
    moves = v.get_legal_moves(state, "player_1")
    lay_move = [m for m in moves if m["type"] == "lay_out_map"][0]
    lay_move["cards"] = ["N01"] * 12
    new = v.apply_move(state, lay_move)
    assert len(new["game_data"]["map"]["cards"]) == 12


def test_command_activation():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["co_hq"] = "co_hq_1"
    state = {"game_data": gd, "players": []}
    moves = v.get_legal_moves(state, "player_1")
    activate_moves = [m for m in moves if m["type"] == "activate_hq"]
    assert len(activate_moves) > 0
    new = v.apply_move(state, activate_moves[0])
    # Activation marks the HQ as activated
    assert activate_moves[0]["hq_id"] in new["game_data"]["company"]["command"]["activated"]


def test_place_unit():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "setup"
    gd["map"]["cards"] = ["N01"] * 12
    state = {"game_data": gd, "players": []}
    move = {"type": "place_unit", "unit_id": "squad_1", "position": 0, "player_id": "player_1"}
    assert v.validate_move(state, move)
    new = v.apply_move(state, move)
    placed = [u for u in new["game_data"]["company"]["units"] if u.get("id") == "squad_1"]
    assert len(placed) == 1
    assert placed[0].get("position") == 0


def test_can_communicate():
    v = FieldsOfFireValidator()
    u1 = {"position": 0}
    u2 = {"position": 1}
    assert v.can_communicate(u1, u2) is True


def test_has_los():
    v = FieldsOfFireValidator()
    ok, reason = v.has_los("N01", "N02")
    assert ok is True


def test_get_elevation():
    v = FieldsOfFireValidator()
    elev = v.get_elevation("N01")
    assert isinstance(elev, int)


