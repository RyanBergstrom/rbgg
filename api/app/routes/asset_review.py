"""Local API for browsing game asset folders and updating their CSV manifests."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/asset-review", tags=["asset-review"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]


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
    configured = os.environ.get("RBGG_CONFIG_ROOT")
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


# â”€â”€ API Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/config-games")
def list_config_games() -> dict:
    """List game folders from the configs directory with their CSV and JSON files."""
    games = config_game_folders()
    return {"games": games, "root_name": Path(config_games_root()).name}


@router.get("/{game_id}/config/{json_name}")
def get_config_json(game_id: str, json_name: str) -> dict:
    """Read a counters.json or other JSON config file for a game."""
    return read_counter_json(game_id, json_name)


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


@router.patch("/{game_id}/{json_name}/rows/{row_index}")
def update_json_row(game_id: str, json_name: str, row_index: int, body: dict) -> dict:
    if row_index < 0:
        raise HTTPException(status_code=400, detail="Invalid row index")
    root = config_games_root()
    folder = safe_child(root, game_id)
    path = safe_child(folder, json_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="JSON config not found")
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
    return {"row_index": row_index, "row": data[row_index]}
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
