import csv

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