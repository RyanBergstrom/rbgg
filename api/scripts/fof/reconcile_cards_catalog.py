"""Safely reconcile cards.json suggestions into the single validated card catalog.

Default is dry-run. Use --apply only after reviewing the printed summary.
Rules:
- cards.json is the authoritative terrain source (per user instruction).
- For Action Cards, fields declared in action_details.verified_fields in cards.json
  remain authoritative; final review metadata is retained.
- Existing final-only records are retained, and duplicate image keys collapse to
  the latest reviewed_at record.
- Reviewed status is preserved from either source; unreviewed catalog entries
  remain available but explicitly unreviewed.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "api" / "configs" / "fof"
RAW_PATH = BASE / "cards.json"
FINAL_PATH = BASE / "cards-final.json"


def record_key(record: dict[str, Any]) -> str | None:
    image = record.get("image")
    return (image.get("filename") if isinstance(image, dict) else None) or record.get("id")


def reviewed_sort_key(record: dict[str, Any], index: int) -> tuple[bool, str, int]:
    classification = record.get("classification") or {}
    return bool(classification.get("reviewed")), classification.get("reviewed_at") or "", index


def load_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"Expected a JSON array of records: {path}")
    return data


def reconcile(raw: list[dict[str, Any]], final: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_by_key = {record_key(record): record for record in raw if record_key(record)}
    final_groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for index, record in enumerate(final):
        key = record_key(record)
        if key:
            final_groups[key].append((index, record))

    chosen_final = {
        key: max(group, key=lambda pair: reviewed_sort_key(pair[1], pair[0]))[1]
        for key, group in final_groups.items()
    }
    merged: list[dict[str, Any]] = []
    raw_only = 0
    conflicts: dict[str, list[tuple[str, Any, Any]]] = defaultdict(list)

    for raw_record in raw:
        key = record_key(raw_record)
        if not key:
            continue
        out = json.loads(json.dumps(raw_record))
        final_record = chosen_final.get(key)
        if final_record is None:
            raw_only += 1
            # Ensure the record is explicitly available to testing without being
            # mistaken for a human-reviewed card.
            out.setdefault("classification", {})["reviewed"] = bool(
                (raw_record.get("classification") or {}).get("reviewed")
            )
            merged.append(out)
            continue

        raw_class = raw_record.get("classification") or {}
        final_class = final_record.get("classification") or {}
        out_class = out.setdefault("classification", {})
        out_class["reviewed"] = bool(raw_class.get("reviewed") or final_class.get("reviewed"))
        for field in ("reviewer", "reviewed_at"):
            if final_class.get(field) is not None:
                out_class[field] = final_class[field]

        if raw_record.get("card_type") == "terrain":
            # User selected cards.json as the sole authoritative terrain source.
            out["terrain_details"] = json.loads(json.dumps(raw_record.get("terrain_details")))
            final_terrain = final_record.get("terrain_details") or {}
            raw_terrain = raw_record.get("terrain_details") or {}
            for field in set(raw_terrain) | set(final_terrain):
                if raw_terrain.get(field) != final_terrain.get(field):
                    if len(conflicts[f"terrain_details.{field}"]) < 8:
                        conflicts[f"terrain_details.{field}"].append(
                            (key, raw_terrain.get(field), final_terrain.get(field))
                        )
        elif raw_record.get("card_type") == "action":
            # cards.json contains the manually verified action values.
            out_details = json.loads(json.dumps(raw_record.get("action_details") or {}))
            out["action_details"] = out_details
            final_details = final_record.get("action_details") or {}
            for field in out_details.get("verified_fields", []):
                if out_details.get(field) != final_details.get(field):
                    if len(conflicts[f"action_details.{field}"]) < 8:
                        conflicts[f"action_details.{field}"].append(
                            (key, out_details.get(field), final_details.get(field))
                        )
        merged.append(out)

    # Keep any final-only rows rather than dropping user data.
    raw_keys = set(raw_by_key)
    final_only = [record for key, record in chosen_final.items() if key not in raw_keys]
    merged.extend(json.loads(json.dumps(record)) for record in final_only)
    report = {
        "raw_count": len(raw),
        "final_before_count": len(final),
        "raw_unique_keys": len(raw_by_key),
        "final_unique_keys": len(chosen_final),
        "duplicate_final_keys": {key: len(group) for key, group in final_groups.items() if len(group) > 1},
        "raw_only_count": raw_only,
        "final_only_count": len(final_only),
        "output_count": len(merged),
        "conflicts": dict(conflicts),
    }
    return merged, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the reconciled catalog; default only reports")
    args = parser.parse_args()

    raw, final = load_records(RAW_PATH), load_records(FINAL_PATH)
    merged, report = reconcile(raw, final)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.apply:
        FINAL_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Applied reconciled catalog to {FINAL_PATH}")
    else:
        print("Dry run only; no files changed. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
