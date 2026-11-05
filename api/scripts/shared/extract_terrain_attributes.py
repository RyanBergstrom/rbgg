"""Extract terrain card attributes from Fields of Fire card PNGs.

Pipeline: Pillow (crop + color) + easyocr (text/numbers) -> update terrain_cards.csv.
Calibrate the bounding boxes in CALIBRATION below using a single sample card.
"""
from __future__ import annotations

import csv
import os
import re
from pathlib import Path

from PIL import Image

try:
    import easyocr
    _OCR = easyocr.Reader(["en"], gpu=False)
except Exception:  # pragma: no cover
    _OCR = None


# ---------------------------------------------------------------------------
# CALIBRATION: adjust these (left, top, right, bottom) to your sample card.
# Use the helper calibrate() to print cropped regions and tune.
# ---------------------------------------------------------------------------
REGIONS = {
    "card_id": (5, 5, 60, 35),          # upper-left white ID
    "terrain_name": (40, 40, 260, 80),  # center name text
    "cover_high": (20, 90, 70, 130),
    "cover_low": (20, 130, 70, 170),
    "burst": (20, 170, 70, 210),
    "top_border": (100, 0, 140, 12),
    "bottom_border": (100, 288, 140, 300),
    "left_border": (0, 140, 12, 180),
    "right_border": (288, 140, 300, 180),
}


def calibrate(image_path: str) -> None:
    """Print region crops to a folder for manual tuning."""
    img = Image.open(image_path)
    out = Path("calib_out")
    out.mkdir(exist_ok=True)
    for name, box in REGIONS.items():
        img.crop(box).save(out / f"{name}.png")
    print(f"saved crops to {out.resolve()}")


def _border_color(img: Image.Image, box) -> str:
    r, g, b = img.crop(box).resize((1, 1)).getpixel((0, 0))[:3]
    # white if bright, else dark
    return "white" if (r + g + b) / 3 > 128 else "dark"


def _ocr_text(img: Image.Image, box) -> str:
    if _OCR is None:
        return ""
    crop = img.crop(box)
    res = _OCR.readtext(crop, detail=0)
    return " ".join(res).strip()


def extract_attributes(image_path: str) -> dict:
    img = Image.open(image_path).convert("RGB")
    attrs = {}
    attrs["card_id"] = _ocr_text(img, REGIONS["card_id"])
    attrs["terrain_name"] = _ocr_text(img, REGIONS["terrain_name"])
    for key in ("cover_high", "cover_low", "burst"):
        txt = _ocr_text(img, REGIONS[key])
        m = re.search(r"-?\d+", txt)
        attrs[key] = int(m.group()) if m else None
    attrs["borders"] = [
        _border_color(img, REGIONS["top_border"]),
        _border_color(img, REGIONS["right_border"]),
        _border_color(img, REGIONS["bottom_border"]),
        _border_color(img, REGIONS["left_border"]),
    ]
    return attrs


def update_csv(csv_path: str, image_root: str, output_path: str) -> None:
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)

    for row in rows:
        rel = row.get("File Name", "")
        if not rel:
            continue
        img_path = os.path.join(image_root, rel)
        if not os.path.isfile(img_path):
            continue
        attrs = extract_attributes(img_path)
        for k, v in attrs.items():
            if k in fields:
                row[k] = "" if v is None else (v if not isinstance(v, list) else "|".join(v))
            else:
                # add new column lazily
                if k not in fields:
                    fields.append(k)
                row[k] = "" if v is None else (v if not isinstance(v, list) else "|".join(v))

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--images", required=True, help="root containing organized/Cards/...")
    ap.add_argument("--out", required=True)
    ap.add_argument("--calibrate", help="path to a sample card PNG to crop regions")
    args = ap.parse_args()
    if args.calibrate:
        calibrate(args.calibrate)
    else:
        update_csv(args.csv, args.images, args.out)
PY