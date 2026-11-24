"""Local API for browsing game asset folders and updating their CSV manifests."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from jsonschema import Draft7Validator

from fastapi import APIRouter, Header, HTTPException, Response
from fastapi.responses import Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/asset-review", tags=["asset-review"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FOF_CARD_SCHEMA_PATH = PROJECT_ROOT / "documentation" / "fof" / "card-schema.json"


def validate_fof_card_record(record: dict) -> None:
    """Reject invalid FoF card edits without making legacy catalog reads fail."""
    try:
        with FOF_CARD_SCHEMA_PATH.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="FoF card schema is unavailable or invalid") from exc
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(record), key=lambda error: list(map(str, error.absolute_path)))
    if errors:
        messages = []
        for error in errors[:20]:
            field_path = ".".join(str(part) for part in error.absolute_path) or "record"
            messages.append(f"{field_path}: {error.message}")
        raise HTTPException(status_code=422, detail={"message": "Card record does not match the FoF card schema", "errors": messages})


def asset_root() -> Path:
    configured = os.environ.get("RBGG_ASSET_REVIEW_ROOT")
    root = Path(configured).expanduser() if configured else PROJECT_ROOT / "api" / "img"
    return root.resolve()


def image_root() -> Path:
    configured = os.environ.get("RBGG_ASSET_IMAGE_ROOT")
    root = Path(configured).expanduser() if configured else PROJECT_ROOT / "api" / "img"
    return root.resolve()


def safe_child(base: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise HTTPException(status_code=400, detail="Invalid relative path")
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path escapes configured asset root") from exc
    return candidate


def csv_path(game_id: str, csv_name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", game_id):
        raise HTTPException(status_code=400, detail="Invalid game directory")
    if Path(csv_name).name != csv_name or Path(csv_name).suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="CSV name must be a filename ending in .csv")
    folder = safe_child(config_games_root(), game_id)
    path = safe_child(folder, csv_name)
    if not folder.is_dir() or not path.is_file():
        raise HTTPException(status_code=404, detail="Game folder or CSV not found")
    return path


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            if not any(field.strip().casefold() == "file name" for field in fields) or not any(
                field.strip().casefold() == "validated" for field in fields
            ):
                raise HTTPException(status_code=422, detail="CSV requires File Name and Validated columns")
            return fields, [{key: value or "" for key, value in row.items() if key is not None} for row in reader]
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded") from exc


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    data = buffer.getvalue().encode("utf-8-sig")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        if temporary:
            temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail=f"Could not update CSV (it may be open or locked): {exc}") from exc


def config_games_root() -> Path:
    """Return the configs folder path: C:\Dev\rbgg\api\configs"""
    configured = os.environ.get("RBGG_CONFIG_ROOT") or os.environ.get("RBGG_ASSET_REVIEW_ROOT")
    root = Path(configured).expanduser() if configured else PROJECT_ROOT / "api" / "configs"
    return root.resolve()


def config_game_folders() -> list[dict]:
    """Read subfolders from the configs directory, each representing a game."""
    root = config_games_root()
    if not root.is_dir():
        return []
    games = []
    for folder in sorted(root.iterdir()):
        if folder.is_dir() and not folder.is_symlink():
            csv_files = sorted(path.name for path in folder.glob("*.csv") if path.is_file() and not path.is_symlink())
            json_files = sorted(path.name for path in folder.glob("*.json") if path.is_file() and not path.is_symlink() and path.name != "counter-schema.json")
            first_config = csv_files[0] if csv_files else (json_files[0] if json_files else None)
            games.append({
                "id": folder.name,
                "csv_files": csv_files,
                "json_files": json_files,
                "first_config": first_config,
            })
    return games


def read_counter_json(game_id: str, json_name: str) -> dict:
    """Read a counters.json file from the game's config folder."""
    root = config_games_root()
    folder = safe_child(root, game_id)
    path = safe_child(folder, json_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="JSON config not found")
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return {"csv_name": json_name, "records": data}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="JSON config must be valid JSON") from exc


def json_file_etag(path: Path) -> str:
    """Return a strong content revision for optimistic JSON config writes."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f'"{digest}"'


# â”€â”€ API Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/games")
def list_games() -> dict:
    games = config_game_folders()
    return {"games": [{"id": g["id"], "csv_files": g["csv_files"]} for g in games]}


@router.get("/config-games")
def list_config_games() -> dict:
    """List game folders from the configs directory with their CSV and JSON files."""
    games = config_game_folders()
    return {"games": games, "root_name": Path(config_games_root()).name}


@router.get("/{game_id}/config/{json_name}")
def get_config_json(game_id: str, json_name: str, response: Response) -> dict:
    """Read a counters.json or other JSON config file for a game."""
    data = read_counter_json(game_id, json_name)
    path = safe_child(safe_child(config_games_root(), game_id), json_name)
    revision = json_file_etag(path)
    response.headers["ETag"] = revision
    data["revision"] = revision
    return data


@router.get("/{game_id}/{csv_name}")
def get_csv(game_id: str, csv_name: str) -> dict:
    path = csv_path(game_id, csv_name)
    fields, rows = read_rows(path)
    return {"game_id": game_id, "csv_name": csv_name, "fields": fields, "rows": rows}


@router.patch("/{game_id}/{csv_name}/rows/{row_index}")
def update_row(game_id: str, csv_name: str, row_index: int, body: dict) -> dict:
    if row_index < 0:
        raise HTTPException(status_code=400, detail="Invalid row index")
    path = csv_path(game_id, csv_name)
    fields, rows = read_rows(path)
    # Find the validated field
    validated_field = next((f for f in fields if f.strip().casefold() == "validated"), None)
    if not validated_field:
        raise HTTPException(status_code=422, detail="CSV must have a Validated field")
    if row_index >= len(rows):
        raise HTTPException(status_code=404, detail="CSV row not found")
    if "validated" in body:
        rows[row_index][validated_field] = "1" if body["validated"] else ""
    for field, value in body.get("updates", {}).items():
        matching_field = next((candidate for candidate in fields if candidate.casefold() == field.casefold()), None)
        if matching_field is None:
            raise HTTPException(status_code=422, detail=f"Unknown CSV field: {field}")
        if matching_field.strip().casefold() != "validated":
            rows[row_index][matching_field] = value
    write_rows(path, fields, rows)
    return {"row_index": row_index, "validated": rows[row_index][validated_field] == "1", "row": rows[row_index]}


@router.patch("/{game_id}/{csv_name}/fields")
def update_fields(game_id: str, csv_name: str, body: dict) -> dict:
    path = csv_path(game_id, csv_name)
    fields, rows = read_rows(path)
    required = {field.casefold() for field in fields if field.strip().casefold() in {"file name", "validated"}}
    removals = {name for name in body.get("remove", []) if name.casefold() not in required}
    fields = [field for field in fields if field not in removals]
    for name in body.get("add", []):
        name = name.strip()
        if not name or "," in name or "\n" in name or "\r" in name:
            raise HTTPException(status_code=422, detail="Field names must be non-empty single-line values")
        if not any(field.casefold() == name.casefold() for field in fields):
            fields.append(name)
    if not any(field.strip().casefold() == "file name" for field in fields) or not any(
        field.strip().casefold() == "validated" for field in fields
    ):
        raise HTTPException(status_code=422, detail="Required fields cannot be removed")
    for row in rows:
        for field in body.get("add", []):
            if field.strip() in fields:
                row.setdefault(field.strip(), "")
        for field in removals:
            row.pop(field, None)
    write_rows(path, fields, rows)
    return {"fields": fields}


@router.patch("/{game_id}/config/{json_name}/rows/{row_index}")
def update_json_row(
    game_id: str,
    json_name: str,
    row_index: int,
    body: dict,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    if row_index < 0:
        raise HTTPException(status_code=400, detail="Invalid row index")
    root = config_games_root()
    folder = safe_child(root, game_id)
    path = safe_child(folder, json_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="JSON config not found")
    if if_match is not None and json_file_etag(path) != if_match:
        raise HTTPException(status_code=409, detail="JSON config changed since it was loaded; reload before saving")
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="JSON config must be valid JSON") from exc
    if not isinstance(data, list):
        raise HTTPException(status_code=422, detail="JSON config must be an array")
    if row_index >= len(data):
        raise HTTPException(status_code=404, detail="JSON row not found")
    updates = body.get("updates") or {}
    if isinstance(updates, dict):
        if isinstance(data[row_index], dict):
            data[row_index] = {**data[row_index], **updates}
        else:
            data[row_index] = updates
    elif isinstance(updates, (list, str, int, float, bool)) or updates is None:
        data[row_index] = updates
    else:
        data[row_index] = updates
    if game_id == "fof" and json_name == "cards-final.json":
        if not isinstance(data[row_index], dict):
            raise HTTPException(status_code=422, detail="FoF card record must be an object")
        validate_fof_card_record(data[row_index])
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False, encoding="utf-8") as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        if 'temporary' in locals() and temporary:
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                pass
        raise HTTPException(status_code=409, detail=f"Could not update JSON (it may be open or locked): {exc}") from exc
    return {"row_index": row_index, "row": data[row_index], "revision": json_file_etag(path)}


@router.post("/{game_id}/config/{json_name}/sync-record")
def sync_config_json_record(
    game_id: str,
    json_name: str,
    body: dict,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    """Sync a single record into or out of a config JSON file (e.g. counters-final.json)."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", game_id):
        raise HTTPException(status_code=400, detail="Invalid game directory")
    if Path(json_name).name != json_name or Path(json_name).suffix.lower() != ".json":
        raise HTTPException(status_code=400, detail="JSON config name must be a filename ending in .json")

    action = body.get("action")
    target_id = body.get("id")
    if not action or action not in {"upsert", "delete"}:
        raise HTTPException(status_code=400, detail="Action must be 'upsert' or 'delete'")
    if not target_id:
        raise HTTPException(status_code=400, detail="Counter ID ('id') is required")

    root = config_games_root()
    folder = safe_child(root, game_id)
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="Game folder not found")
    path = safe_child(folder, json_name)

    # Clients that have fetched the JSON should send its ETag on writes. Older
    # clients remain compatible until updated; once supplied, a stale revision
    # is rejected instead of silently replacing another editor's changes.
    if if_match is not None:
        if not path.is_file() or json_file_etag(path) != if_match:
            raise HTTPException(status_code=409, detail="JSON config changed since it was loaded; reload before saving")

    data = []
    if path.is_file():
        try:
            with path.open("r", encoding="utf-8-sig") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    data = loaded
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="Existing JSON config is invalid JSON") from exc

    def matches_target(item: object) -> bool:
        if not isinstance(item, dict):
            return False
        image_filename = (item.get("image") or {}).get("filename") if isinstance(item.get("image"), dict) else None
        return target_id in {item.get("id"), image_filename}

    if action == "upsert":
        record = body.get("record")
        if not isinstance(record, dict):
            raise HTTPException(status_code=422, detail="Valid record dictionary is required for upsert")
        if game_id == "fof" and json_name == "cards-final.json":
            validate_fof_card_record(record)
        if "classification" in record and isinstance(record["classification"], dict):
            classification = record["classification"]
            classification["reviewed"] = bool(classification.get("reviewed", True))
            if classification["reviewed"] and not classification.get("reviewed_at"):
                record["classification"]["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            elif not classification["reviewed"]:
                classification["reviewed_at"] = None

        record_image = (record.get("image") or {}).get("filename") if isinstance(record.get("image"), dict) else None
        record_ids = {record.get("id"), record_image}
        if target_id not in record_ids:
            raise HTTPException(status_code=422, detail="Sync id must match the record id or image filename")

        matching_indexes = [idx for idx, item in enumerate(data) if matches_target(item)]
        if matching_indexes:
            first_index = matching_indexes[0]
            data[first_index] = record
            data = [item for idx, item in enumerate(data) if idx == first_index or not matches_target(item)]
        else:
            data.append(record)
    elif action == "delete":
        if not path.is_file():
            return {"success": True, "action": "delete", "id": target_id, "total_records": 0}
        data = [item for item in data if not matches_target(item)]

    # Atomic write to path
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False, encoding="utf-8") as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        if 'temporary' in locals() and temporary:
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                pass
        raise HTTPException(status_code=409, detail=f"Could not update JSON: {exc}") from exc

    return {
        "success": True,
        "action": action,
        "id": target_id,
        "total_records": len(data),
        "revision": json_file_etag(path),
    }


@router.get("/{game_id}/images/{image_path:path}")
def get_image(game_id: str, image_path: str) -> Response:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", game_id):
        raise HTTPException(status_code=400, detail="Invalid game directory")
    img_base = safe_child(image_root(), game_id)
    path = safe_child(img_base, image_path)
    if not path.is_file() and "/" not in image_path and "\\" not in image_path:
        matches = []
        for candidate in img_base.rglob(image_path):
            resolved = candidate.resolve()
            try:
                resolved.relative_to(img_base.resolve())
            except ValueError:
                continue
            if resolved.is_file() and not candidate.is_symlink():
                matches.append(resolved)
        path = matches[0].resolve() if matches else path
    if not path.is_file() or path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}:
        base = safe_child(asset_root(), game_id)
        path = safe_child(base, image_path)
        if not path.is_file() and "/" not in image_path and "\\" not in image_path:
            matches = []
            for candidate in base.rglob(image_path):
                resolved = candidate.resolve()
                try:
                    resolved.relative_to(base.resolve())
                except ValueError:
                    continue
                if resolved.is_file() and not candidate.is_symlink():
                    matches.append(resolved)
            path = matches[0].resolve() if matches else path
    if not path.is_file() or path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}:
        try:
            config_root = config_games_root()
            config_base = safe_child(config_root, game_id)
            path2 = safe_child(config_base, image_path)
            if not path2.is_file() and "/" not in image_path and "\\" not in image_path:
                matches2 = []
                for candidate in config_base.rglob(image_path):
                    resolved = candidate.resolve()
                    try:
                        resolved.relative_to(config_base.resolve())
                    except ValueError:
                        continue
                    if resolved.is_file() and not candidate.is_symlink():
                        matches2.append(resolved)
                path2 = matches2[0].resolve() if matches2 else path2
            if path2.is_file() and path2.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}:
                path = path2
            else:
                raise HTTPException(status_code=404, detail='Image not found')
        except Exception:
            raise HTTPException(status_code=404, detail='Image not found')
    media_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}.get(path.suffix.lower(), f"image/{path.suffix.lower()[1:]}")
    return Response(path.read_bytes(), media_type=media_type, headers={'Cache-Control': 'no-store'})
