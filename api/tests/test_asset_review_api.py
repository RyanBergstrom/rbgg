import csv
import json

from fastapi.testclient import TestClient

from app import app


def client():
    return TestClient(app)


def test_list_load_and_update_csv_in_place(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_ASSET_REVIEW_ROOT", str(tmp_path))
    game = tmp_path / "twilight-struggle"
    game.mkdir()
    csv_path = game / "cards.csv"
    csv_path.write_text('File Name,Name,Validated\r\ncard.png,Asia Scoring,\r\n', encoding="utf-8")
    response = client().get("/api/v1/asset-review/games")
    assert response.status_code == 200
    assert response.json()["games"] == [{"id": "twilight-struggle", "csv_files": ["cards.csv"]}]

    response = client().get("/api/v1/asset-review/twilight-struggle/cards.csv")
    assert response.status_code == 200
    assert response.json()["rows"][0]["Name"] == "Asia Scoring"

    response = client().patch(
        "/api/v1/asset-review/twilight-struggle/cards.csv/rows/0",
        json={"validated": True},
    )
    assert response.status_code == 200
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["Validated"] == "1"


def test_add_and_remove_csv_columns(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_ASSET_REVIEW_ROOT", str(tmp_path))
    game = tmp_path / "my-game"
    game.mkdir()
    path = game / "cards.csv"
    path.write_text('File Name,Validated,Note\na.png,,keep\n', encoding="utf-8")
    response = client().patch(
        "/api/v1/asset-review/my-game/cards.csv/fields",
        json={"add": ["Editor"], "remove": ["Note"]},
    )
    assert response.status_code == 200
    assert response.json()["fields"] == ["File Name", "Validated", "Editor"]
    result = client().get("/api/v1/asset-review/my-game/cards.csv").json()
    assert result["rows"] == [{"File Name": "a.png", "Validated": "", "Editor": ""}]


def test_update_existing_row_field(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_ASSET_REVIEW_ROOT", str(tmp_path))
    game = tmp_path / "my-game"
    game.mkdir()
    path = game / "cards.csv"
    path.write_text('File Name,Validated,Name\na.png,,Asia Scoring\n', encoding="utf-8")
    response = client().patch(
        "/api/v1/asset-review/my-game/cards.csv/rows/0",
        json={"updates": {"File Name": "renamed.png", "Name": "Updated name"}},
    )
    assert response.status_code == 200
    assert response.json()["row"] == {
        "File Name": "renamed.png", "Validated": "", "Name": "Updated name"
    }
    with path.open(encoding="utf-8-sig", newline="") as handle:
        saved = next(csv.DictReader(handle))
    assert saved["File Name"] == "renamed.png"
    assert saved["Name"] == "Updated name"


def test_reject_path_traversal_and_missing_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_ASSET_REVIEW_ROOT", str(tmp_path))
    client_instance = client()
    assert client_instance.get("/api/v1/asset-review/../api/pyproject.toml").status_code in {400, 404}
    assert client_instance.get("/api/v1/asset-review/not-a-game/missing.csv").status_code == 404


def test_serve_nested_game_image(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_ASSET_REVIEW_ROOT", str(tmp_path))
    image_dir = tmp_path / "my-game" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "art.png").write_bytes(b"image-data")
    (image_dir / "card.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    response = client().get("/api/v1/asset-review/my-game/images/art.png")
    assert response.status_code == 200
    svg_response = client().get("/api/v1/asset-review/my-game/images/card.svg")
    assert svg_response.status_code == 200
    assert svg_response.headers["content-type"] == "image/svg+xml"


def test_sync_json_record_matches_image_filename_replaces_duplicates_and_deletes(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_CONFIG_ROOT", str(tmp_path))
    game = tmp_path / "fof"
    game.mkdir()
    path = game / "cards-final.json"
    path.write_text(
        '[{"id":"old-id-1","image":{"filename":"cards/N01 Hill.jpg"},"value":1},'
        '{"id":"old-id-2","image":{"filename":"cards/N01 Hill.jpg"},"value":2}]',
        encoding="utf-8",
    )
    record = {
        "id": "FOF-TERRAIN-N01-HILL",
        "name": "Hill",
        "card_type": "terrain",
        "deck": "Normandy Terrain",
        "expansion": "Volume I",
        "purpose": "Map Terrain Grid",
        "image": {"filename": "cards/N01 Hill.jpg", "width": 274, "height": 384, "format": "jpg"},
        "terrain_details": {"terrain_name": "Hill", "cover_high": 1, "cover_low": 0},
        "action_details": None,
        "classification": {"reviewed": True, "reviewed_at": None, "reviewer": None, "notes": None},
    }

    response = client().post(
        "/api/v1/asset-review/fof/config/cards-final.json/sync-record",
        json={"action": "upsert", "record": record, "id": "cards/N01 Hill.jpg"},
    )
    assert response.status_code == 200
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["id"] == "FOF-TERRAIN-N01-HILL"
    assert saved[0]["terrain_details"]["cover_high"] == 1
    assert saved[0]["classification"]["reviewed"] is True

    response = client().post(
        "/api/v1/asset-review/fof/config/cards-final.json/sync-record",
        json={"action": "delete", "id": "cards/N01 Hill.jpg"},
    )
    assert response.status_code == 200
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_sync_json_record_preserves_unreviewed_state(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_CONFIG_ROOT", str(tmp_path))
    game = tmp_path / "fof"
    game.mkdir()
    response = client().post(
        "/api/v1/asset-review/fof/config/cards-final.json/sync-record",
        json={
            "action": "upsert",
            "id": "cards/N01 Hill.jpg",
            "record": {
                "id": "FOF-TERRAIN-N01-HILL",
                "name": "Hill",
                "card_type": "terrain",
                "deck": "Normandy Terrain",
                "expansion": "Volume I",
                "purpose": "Map Terrain Grid",
                "image": {"filename": "cards/N01 Hill.jpg", "width": 274, "height": 384, "format": "jpg"},
                "terrain_details": {"terrain_name": "Hill", "cover_high": 0, "cover_low": 0},
                "action_details": None,
                "classification": {"reviewed": False, "reviewed_at": "old-date", "reviewer": None, "notes": None},
            },
        },
    )
    assert response.status_code == 200
    saved = json.loads((game / "cards-final.json").read_text(encoding="utf-8"))
    assert saved[0]["classification"]["reviewed"] is False
    assert saved[0]["classification"]["reviewed_at"] is None


def test_fof_card_sync_rejects_schema_invalid_record(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_CONFIG_ROOT", str(tmp_path))
    (tmp_path / "fof").mkdir()
    record = {
        "id": "FOF-TERRAIN-N01-HILL",
        "name": "Hill",
        "card_type": "terrain",
        "deck": "Normandy Terrain",
        "expansion": "Volume I",
        "purpose": "Map Terrain Grid",
        "image": {"filename": "cards/N01 Hill.jpg", "width": 274, "height": 384, "format": "jpg"},
        "terrain_details": {"cover_high": 9},
        "action_details": None,
        "classification": {"reviewed": True},
    }
    response = client().post(
        "/api/v1/asset-review/fof/config/cards-final.json/sync-record",
        json={"action": "upsert", "record": record, "id": "cards/N01 Hill.jpg"},
    )
    assert response.status_code == 422
    assert "cover_high" in str(response.json()["detail"])
    assert not (tmp_path / "fof" / "cards-final.json").exists()


def test_fof_card_sync_accepts_schema_valid_record(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_CONFIG_ROOT", str(tmp_path))
    (tmp_path / "fof").mkdir()
    record = {
        "id": "FOF-TERRAIN-N01-HILL",
        "name": "Hill",
        "card_type": "terrain",
        "deck": "Normandy Terrain",
        "expansion": "Volume I",
        "purpose": "Map Terrain Grid",
        "image": {"filename": "cards/N01 Hill.jpg", "width": 274, "height": 384, "format": "jpg"},
        "terrain_details": {"cover_high": 0, "cover_low": 0, "elevation": 1},
        "action_details": None,
        "classification": {"reviewed": False, "reviewed_at": None, "reviewer": None, "notes": None},
    }
    response = client().post(
        "/api/v1/asset-review/fof/config/cards-final.json/sync-record",
        json={"action": "upsert", "record": record, "id": "cards/N01 Hill.jpg"},
    )
    assert response.status_code == 200
    saved = json.loads((tmp_path / "fof" / "cards-final.json").read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["terrain_details"]["cover_high"] == 0


def test_json_config_etag_rejects_stale_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_CONFIG_ROOT", str(tmp_path))
    game = tmp_path / "fof"
    game.mkdir()
    path = game / "cards-final.json"
    path.write_text("[]\n", encoding="utf-8")
    loaded = client().get("/api/v1/asset-review/fof/config/cards-final.json")
    assert loaded.status_code == 200
    old_revision = loaded.headers["etag"]
    path.write_text('[{"external_edit":true}]\n', encoding="utf-8")
    response = client().post(
        "/api/v1/asset-review/fof/config/cards-final.json/sync-record",
        headers={"If-Match": old_revision},
        json={"action": "upsert", "id": "cards/N01 Hill.jpg", "record": {
            "id": "FOF-TERRAIN-N01-HILL", "name": "Hill", "card_type": "terrain",
            "deck": "Normandy Terrain", "expansion": "Volume I", "purpose": "Map Terrain Grid",
            "image": {"filename": "cards/N01 Hill.jpg", "width": 274, "height": 384, "format": "jpg"},
            "terrain_details": {"cover_high": 0}, "action_details": None,
            "classification": {"reviewed": True},
        }},
    )
    assert response.status_code == 409
    assert json.loads(path.read_text(encoding="utf-8")) == [{"external_edit": True}]


def test_json_config_etag_rejects_stale_row_patch(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_CONFIG_ROOT", str(tmp_path))
    game = tmp_path / "fof"
    game.mkdir()
    path = game / "cards.json"
    path.write_text('[{"id":"card-1","name":"Original"}]\n', encoding="utf-8")
    loaded = client().get("/api/v1/asset-review/fof/config/cards.json")
    assert loaded.status_code == 200
    stale_revision = loaded.headers["etag"]
    path.write_text('[{"id":"card-1","name":"External edit"}]\n', encoding="utf-8")

    response = client().patch(
        "/api/v1/asset-review/fof/config/cards.json/rows/0",
        headers={"If-Match": stale_revision},
        json={"updates": {"name": "Stale edit"}},
    )
    assert response.status_code == 409
    assert json.loads(path.read_text(encoding="utf-8"))[0]["name"] == "External edit"


def test_fof_final_row_patch_enforces_card_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGG_CONFIG_ROOT", str(tmp_path))
    game = tmp_path / "fof"
    game.mkdir()
    path = game / "cards-final.json"
    record = {
        "id": "FOF-TERRAIN-N01-HILL",
        "name": "Hill",
        "card_type": "terrain",
        "deck": "Normandy Terrain",
        "expansion": "Volume I",
        "purpose": "Map Terrain Grid",
        "image": {"filename": "cards/N01 Hill.jpg", "width": 274, "height": 384, "format": "jpg"},
        "terrain_details": {"cover_high": 0},
        "action_details": None,
        "classification": {"reviewed": True, "reviewed_at": None, "reviewer": None, "notes": None},
    }
    path.write_text(json.dumps([record]), encoding="utf-8")

    response = client().patch(
        "/api/v1/asset-review/fof/config/cards-final.json/rows/0",
        json={"updates": {"terrain_details": {"cover_high": 99}}},
    )
    assert response.status_code == 422
    assert "cover_high" in str(response.json()["detail"])
    assert json.loads(path.read_text(encoding="utf-8"))[0]["terrain_details"]["cover_high"] == 0