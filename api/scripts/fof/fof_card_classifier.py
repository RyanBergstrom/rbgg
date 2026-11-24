"""Fields of Fire - Card Computer Vision & OCR Classifier (fof_card_classifier.py)

Classifies Fields of Fire card images into functional categories:
1. High-level classification:
   - terrain: Tactical map grid cards
   - action: Action deck cards (initiative, attempts, combat resolution)
   - fsa: Fire Support Area cards
   - staging_area: Staging Area cards
   - utility: Card backs, reference aids, reshuffle cards

2. Terrain Card Details Extraction:
   - Borders (North, East, South, West):
       'dark' = Green/dark band (blocks LOS; fire crossing takes Higher Cover & Concealment)
       'white' = Clear/light band (open LOS; fire crossing takes Lower Cover & Concealment)
       'black' = Impassable obstacle
   - Top-Left: Cover & Concealment modifiers (Cover High, Cover Low)
   - Top-Right: Elevation (+0, +1, +2, +3, +4, +5, -1)
   - Bottom-Left: Cover Potential (foxholes/capacity) and Seek Cover card draw
   - Bottom-Right: Card designation / number
   - Center: Terrain name
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rn_reader import read_random_number_row  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CARDS_DIR = PROJECT_ROOT / "api" / "img" / "fof" / "cards"
CONFIG_DIR = PROJECT_ROOT / "api" / "configs" / "fof"
OUTPUT_JSON = CONFIG_DIR / "cards.json"
REGION_MAP_PATH = CONFIG_DIR / "card_regions.json"

with REGION_MAP_PATH.open("r", encoding="utf-8") as region_file:
    CARD_REGIONS = json.load(region_file)


def _crop_region(image: np.ndarray, region: dict) -> np.ndarray:
    """Crop a normalized region from an image using the shared card region map."""
    h, w = image.shape[:2]
    x1 = max(0, min(w, round(float(region["x"]) * w)))
    y1 = max(0, min(h, round(float(region["y"]) * h)))
    x2 = max(x1 + 1, min(w, round((float(region["x"]) + float(region["width"])) * w)))
    y2 = max(y1 + 1, min(h, round((float(region["y"]) + float(region["height"])) * h)))
    return image[y1:y2, x1:x2]


def _terrain_region(deck: str | None, key: str) -> dict:
    terrain_regions = CARD_REGIONS["terrain"]
    deck_regions = terrain_regions.get(deck or "", {})
    return deck_regions.get(key) or terrain_regions["default"][key]

# Normandy terrain coverage badges are small printed symbols rather than clean
# OCR text. Values below were transcribed from the card artwork contact sheets.
# A single printed cover value applies to both high and low; a second badge value
# (e.g. +2 / +1 on Gully and Hedgerow cards) is stored as the low value.
NORMANDY_COVERAGE: dict[int, tuple[int, int, int | None, int | None]] = {}
for _n in range(1, 7):
    NORMANDY_COVERAGE[_n] = (0, 0, None, None)  # Hill cards have blank capacity/draw straps.
for _n in (7, 8):
    NORMANDY_COVERAGE[_n] = (1, 1, 1, 2)
for _n in range(9, 17):
    NORMANDY_COVERAGE[_n] = (1, 1, 2, 3)
for _n in range(17, 25):
    NORMANDY_COVERAGE[_n] = (2, 2, 3, 4)
for _n in (25, 26):
    NORMANDY_COVERAGE[_n] = (2, 2, 2, 4)
for _n in range(27, 37):
    NORMANDY_COVERAGE[_n] = (2, 1, 2, 4)
for _n in range(37, 41):
    NORMANDY_COVERAGE[_n] = (3, 3, 3, 4)
for _n in range(41, 45):
    NORMANDY_COVERAGE[_n] = (0, 0, 1, 2)
for _n in range(45, 49):
    NORMANDY_COVERAGE[_n] = (2, 1, 1, 3)
for _n in range(49, 54):
    NORMANDY_COVERAGE[_n] = (2, 2, 1, 3)
NORMANDY_COVERAGE[54] = (3, 3, 1, 3)
NORMANDY_COVERAGE[55] = (1, 1, 1, 3)

# Configure tesseract path
DEFAULT_TESSERACT = r"C:\Users\p211587\AppData\Local\Tesseract-OCR\tesseract.exe"
if os.path.exists(DEFAULT_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_high_level(img_bgr: np.ndarray, filename: str) -> tuple[str, str, str, str]:
    """Determine card_type, deck, expansion, and purpose."""
    lower = filename.lower()
    h, w, _ = img_bgr.shape

    # 1. Staging Areas
    if "staging" in lower:
        return "staging_area", "Staging Areas", "Volume III", "Off-map Staging"

    # 2. Fire Support Areas
    if "fire support" in lower or "fsa" in lower:
        return "fsa", "Fire Support Areas", "Volume III", "Fire Support Base"

    # 3. Card Backs and References
    if "card back" in lower or "card - back" in lower or lower.endswith("back.png") or lower.endswith("back.jpg"):
        return "utility", "Card Backs / Aids", "Base / Shared", "Card Back"
    if "keep up the fire" in lower:
        return "utility", "Card Backs / Aids", "Volume I", "Rule Aid / Reference"

    # 4. Action Deck Check (Action cards or reshuffle)
    if "reshuffle" in lower:
        return "action", "Action Deck", "Volume I", "Deck Reshuffle"
    if re.match(r"^a(0[1-9]|[1-4][0-9]|50)\.jpe?g$", lower):
        return "action", "Action Deck", "Volume I", "Combat & Command Resolution"

    # Check for Action Deck text if present
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    center_crop = gray[int(h * 0.25):int(h * 0.75), int(w * 0.15):int(w * 0.85)]
    scaled_center = cv2.resize(center_crop, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    txt_center = pytesseract.image_to_string(scaled_center).lower()

    if "staging area" in txt_center:
        return "staging_area", "Staging Areas", "Volume III", "Off-map Staging"
    if "fire support area" in txt_center:
        return "fsa", "Fire Support Areas", "Volume III", "Fire Support Base"

    # 5. Terrain Decks
    if filename.startswith("N") and re.match(r"^N\d{2}", filename):
        return "terrain", "Normandy Terrain", "Volume I", "Map Terrain Grid"
    if filename.startswith("K") and re.match(r"^K\d{2}", filename):
        return "terrain", "Korea Terrain", "Volume I", "Map Terrain Grid"
    if filename.startswith("V") and re.match(r"^V\d{2}", filename) and not filename.startswith("Vol"):
        return "terrain", "Vietnam Terrain", "Volume I", "Map Terrain Grid"
    if filename.startswith("HBR"):
        return "terrain", "Heartbreak Ridge Terrain", "Volume I", "Elevation Overlay"
    if filename.startswith("A") and re.match(r"^A\d{2}", filename) and not re.match(r"^A\d{2}\.jpe?g$", filename, re.IGNORECASE):
        return "terrain", "Ardennes Terrain", "Volume II", "Map Terrain Grid"
    if filename.startswith("C") and re.match(r"^C\d{2}", filename):
        return "terrain", "Chosin Reservoir Terrain", "Volume II", "Map Terrain Grid"
    if filename.startswith("P") and re.match(r"^P\d{2}", filename):
        return "terrain", "Peleliu Terrain", "Volume II", "Map Terrain Grid"
    if filename.startswith("Hue") and re.match(r"^Hue\d{2}", filename):
        return "terrain", "Hue Terrain", "Volume II", "Map Terrain Grid"
    if re.match(r"^0\d{2}", filename):
        return "terrain", "Ardennes Terrain", "Volume II", "Map Terrain Grid"
    if "falklands" in lower or "goose green" in lower:
        return "terrain", "Falklands - Goose Green Terrain", "Volume III", "Map Terrain Grid"
    if "plantation" in lower:
        return "terrain", "Vietnam Terrain", "Volume I", "Map Terrain Grid"

    return "terrain", "Terrain Deck", "Unknown", "Map Terrain Grid"


def detect_terrain_borders(img_bgr: np.ndarray) -> dict[str, str]:
    """Detect whether each perimeter edge (North, East, South, West) is dark (green/obstructed) or white (clear)."""
    border_regions = CARD_REGIONS["terrain"]["default"]["borders"]
    crops = {side: _crop_region(img_bgr, region) for side, region in border_regions.items()}

    borders = {}
    for side, crop in crops.items():
        if crop.size == 0:
            borders[side] = "white"
            continue

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        mean_v = float(np.mean(gray))

        # Green HSV mask: H in 25..90, S > 35, V in 20..210
        green_mask = cv2.inRange(hsv, np.array([25, 35, 20]), np.array([90, 255, 210]))
        green_pct = float(cv2.countNonZero(green_mask)) / float(crop.shape[0] * crop.shape[1])

        # Black HSV mask: V < 45
        black_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 45]))
        black_pct = float(cv2.countNonZero(black_mask)) / float(crop.shape[0] * crop.shape[1])

        if black_pct > 0.45:
            borders[side] = "black"
        elif green_pct > 0.30 or (mean_v < 112 and green_pct > 0.14):
            borders[side] = "dark"
        else:
            borders[side] = "white"

    return borders


def extract_terrain_card_features(img_bgr: np.ndarray, filename: str) -> dict:
    """Extract Top-Left (Cover & Concealment), Top-Center (Vehicle Access & Terrain Name),
    Top-Right (Card # & Elevation & Burst), Bottom-Left (Cover Capacity), Bottom-Center (Cover Draw),
    and Bottom-Right (Movement Cost)."""
    h, w, _ = img_bgr.shape
    deck_regions = CARD_REGIONS["terrain"].get(
        "Normandy Terrain" if re.match(r"^N\d{2}\b", filename, re.IGNORECASE) else "",
        CARD_REGIONS["terrain"]["default"],
    )
    features = {
        "cover_high": None,
        "cover_low": None,
        "elevation": None,
        "burst_modifier": 0,
        "vehicle_access": "Unknown",
        "terrain_name_ocr": "",
        "card_number": "",
        "cover_potential": None,
        "cover_draw": None,
        "movement_cost": None,
    }

    # 1. Top-Left Corner: Cover & Concealment Circle (+1/+0, +2/+1, +3/+1, +0, +2, +3, etc.)
    try:
        tl = _crop_region(img_bgr, deck_regions["cover"]["crop"])
        tl_gray = cv2.cvtColor(tl, cv2.COLOR_BGR2GRAY)

        cx, cy, r = 43, 42, 26
        if cx + r > tl_gray.shape[1] or cy + r > tl_gray.shape[0]:
            cx, cy, r = int(tl_gray.shape[1] * 0.45), int(tl_gray.shape[0] * 0.45), int(min(tl_gray.shape[:2]) * 0.28)
        inner = tl_gray[max(0, cy - r):min(tl_gray.shape[0], cy + r), max(0, cx - r):min(tl_gray.shape[1], cx + r)]

        scaled = cv2.resize(inner, (0, 0), fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        pad = cv2.copyMakeBorder(scaled, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)

        txts = {}
        for psm in [6, 11, 8, 13]:
            t = pytesseract.image_to_string(pad, config=f"--psm {psm} -c tessedit_char_whitelist=+-012345Il|/").strip()
            if t:
                txts[psm] = t.replace("I", "1").replace("l", "1").replace("|", "1")

        multi_lines = []
        for psm in [6, 11]:
            if psm in txts:
                lines = [l.strip() for l in txts[psm].splitlines() if l.strip()]
                if len(lines) >= 2:
                    multi_lines.append(lines)

        if multi_lines:
            top_digits = []
            bot_digits = []
            for lines in multi_lines:
                d_top = re.findall(r"\+?\s*([0-5])", lines[0])
                if d_top:
                    top_digits.extend([int(x) for x in d_top])
                d_bot = re.findall(r"\+?\s*([0-5])", lines[1])
                if d_bot:
                    bot_digits.extend([int(x) for x in d_bot])

            if not top_digits:
                top_half = inner[0:25, :]
                digit_crop = top_half[:, 14:38]
                s_d = cv2.resize(digit_crop, (0, 0), fx=4, fy=4)
                p_d = cv2.copyMakeBorder(s_d, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
                t_d = pytesseract.image_to_string(p_d, config="--psm 7 -c tessedit_char_whitelist=012345Il|/").strip()
                t_d = t_d.replace("I", "1").replace("l", "1").replace("|", "1")
                d = re.findall(r"([0-5])", t_d)
                if d:
                    top_digits.extend([int(x) for x in d])

            if not bot_digits:
                bot_half = inner[26:, :]
                s_b = cv2.resize(bot_half, (0, 0), fx=4, fy=4)
                p_b = cv2.copyMakeBorder(s_b, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
                t_b = pytesseract.image_to_string(p_b, config="--psm 6 -c tessedit_char_whitelist=+-012345").strip()
                d = re.findall(r"\+?\s*([0-5])", t_b)
                if d:
                    bot_digits.extend([int(x) for x in d])

            from collections import Counter
            c_high = Counter(top_digits).most_common(1)[0][0] if top_digits else 1
            c_low = Counter(bot_digits).most_common(1)[0][0] if bot_digits else 0
            if c_high == c_low:
                features["cover_high"] = c_high
                features["cover_low"] = None
            else:
                features["cover_high"] = c_high
                features["cover_low"] = c_low
        else:
            single_digits = []
            for psm, t in txts.items():
                d = re.findall(r"\+?\s*([0-5])", t)
                if d:
                    single_digits.extend([int(x) for x in d])
            if not single_digits:
                m = ((inner < 135).astype(np.uint8) * 255)
                p_mask = cv2.copyMakeBorder(cv2.resize(m, (0, 0), fx=4, fy=4, interpolation=cv2.INTER_NEAREST), 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
                for psm in [8, 13, 7]:
                    t = pytesseract.image_to_string(p_mask, config=f"--psm {psm} -c tessedit_char_whitelist=+-012345Il|").strip()
                    t = t.replace("I", "1").replace("l", "1").replace("|", "1")
                    d = re.findall(r"\+?\s*([0-5])", t)
                    if d:
                        single_digits.extend([int(x) for x in d])
            from collections import Counter
            features["cover_high"] = Counter(single_digits).most_common(1)[0][0] if single_digits else 0
            features["cover_low"] = None
    except Exception:
        features["cover_high"] = 0
        features["cover_low"] = None

    # 2. Top-Center Banner: Vehicle Accessibility & Terrain Name
    try:
        tc = _crop_region(img_bgr, deck_regions["terrain_name_and_vehicle"]["crop"])
        tc_gray = cv2.cvtColor(tc, cv2.COLOR_BGR2GRAY)
        t_raw = pytesseract.image_to_string(tc_gray, config="--psm 11").strip().replace("\n", " ")
        t_p3 = pytesseract.image_to_string(tc_gray, config="--psm 3").strip().replace("\n", " ")
        tc_txt = f"{t_raw} {t_p3}"
        features["terrain_name_ocr"] = tc_txt

        if re.search(r"\b(slow|stow|srow|psrow)\b", tc_txt, re.IGNORECASE):
            features["vehicle_access"] = "Slow"
        elif re.search(r"\b(no|na|n0|noy)\b", tc_txt, re.IGNORECASE):
            features["vehicle_access"] = "Prohibited (No)"
        elif re.search(r"\b(yes|road)\b", tc_txt, re.IGNORECASE):
            features["vehicle_access"] = "Allowed (Yes)"
        elif re.search(r"\b(track|tracked)\b", tc_txt, re.IGNORECASE):
            features["vehicle_access"] = "Tracked Only"
    except Exception:
        pass

    # 3. Top-Right Corner: Card Number, Burst Modifier, & Elevation
    try:
        tr = _crop_region(img_bgr, deck_regions["card_number_and_burst"]["crop"])
        tr_gray = cv2.cvtColor(tr, cv2.COLOR_BGR2GRAY)
        tr_scaled = cv2.resize(tr_gray, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        tr_txt = pytesseract.image_to_string(tr_scaled, config="--psm 6").strip().replace("\n", " ")

        m_burst = re.search(r"([+-]\s*[123])", tr_txt)
        if m_burst:
            features["burst_modifier"] = int(re.sub(r"\s+", "", m_burst.group(1)))

        m_num = re.search(r"\b(\d{1,3}[a-z]?)\b", tr_txt, re.IGNORECASE)
        if m_num:
            features["card_number"] = m_num.group(1)

        is_normandy = bool(re.match(r"^N\d{2}\b", filename, re.IGNORECASE))
        m_elev = re.search(r"([+-]?\d)", tr_txt)
        if m_elev and features["elevation"] is None and not is_normandy:
            features["elevation"] = int(m_elev.group(1))
    except Exception:
        pass

    # Normandy terrain cards print elevation in the small top-right contour
    # badge, beside (but separate from) the card number. Read only that badge;
    # the bottom-right area on these cards is blank artwork.
    if re.match(r"^N\d{2}\b", filename, re.IGNORECASE):
        features["elevation"] = read_normandy_elevation(gray)

    # Fallback for card_number from filename (e.g. N01, 001, A02)
    if not features["card_number"]:
        m_fn = re.search(r"^([A-Za-z]?\d{2,3})", filename)
        if m_fn:
            features["card_number"] = m_fn.group(1)

    # 4. Bottom-Left: Cover Potential / Capacity (max cover positions: 0, 1, 2, 3, 4)
    try:
        bl = _crop_region(img_bgr, deck_regions["cover_capacity"]["crop"])
        bl_gray = cv2.cvtColor(bl, cv2.COLOR_BGR2GRAY)
        bh, bw = bl_gray.shape
        icon_bl = bl_gray[int(bh * 0.12):int(bh * 0.88), int(bw * 0.08):int(bw * 0.88)]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        votes_bl = []
        for th in [165, 175, 185, 195, 205, 75, 90, 105]:
            mask = (icon_bl > th).astype(np.uint8) * 255 if th >= 160 else (icon_bl < th).astype(np.uint8) * 255
            closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            scaled = cv2.resize(closed, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
            pad = cv2.copyMakeBorder(scaled, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=0)
            for p in [pad, cv2.bitwise_not(pad)]:
                for psm in [10, 7, 8]:
                    t = pytesseract.image_to_string(p, config=f"--psm {psm} -c tessedit_char_whitelist=01234").strip()
                    if t and re.match(r"^[0-4]$", t):
                        votes_bl.append(int(t))
        if votes_bl:
            from collections import Counter
            features["cover_potential"] = Counter(votes_bl).most_common(1)[0][0]
    except Exception:
        pass

    # 5. Bottom-Center: Seek Cover Action Card Draw (cards drawn: 1, 2, 3, 4, 5)
    try:
        bc = _crop_region(img_bgr, deck_regions["cover_draw"]["crop"])
        bc_gray = cv2.cvtColor(bc, cv2.COLOR_BGR2GRAY)
        bh, bw = bc_gray.shape
        icon_bc = bc_gray[int(bh * 0.12):int(bh * 0.88), int(bw * 0.08):int(bw * 0.88)]
        votes_bc = []
        for th in [65, 80, 95, 110, 170, 185, 200]:
            mask = (icon_bc < th).astype(np.uint8) * 255 if th <= 110 else (icon_bc > th).astype(np.uint8) * 255
            scaled = cv2.resize(mask, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
            pad = cv2.copyMakeBorder(scaled, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=0)
            for p in [pad, cv2.bitwise_not(pad)]:
                for psm in [10, 7, 8]:
                    t = pytesseract.image_to_string(p, config=f"--psm {psm} -c tessedit_char_whitelist=12345").strip()
                    if t and re.match(r"^[1-5]$", t):
                        votes_bc.append(int(t))
        if votes_bc:
            from collections import Counter
            features["cover_draw"] = Counter(votes_bc).most_common(1)[0][0]
    except Exception:
        pass

    # 6. Bottom-Right elevation badge (used on decks other than Normandy).
    if not re.match(r"^N\d{2}\b", filename, re.IGNORECASE):
        try:
            br = _crop_region(img_bgr, deck_regions["elevation"]["crop"])
            br_gray = cv2.cvtColor(br, cv2.COLOR_BGR2GRAY)
            bh, bw = br_gray.shape
            icon_br = br_gray[int(bh * 0.12):int(bh * 0.88), int(bw * 0.08):int(bw * 0.88)]
            votes_br = []
            for th in [165, 175, 185, 195, 205, 75, 90, 105]:
                mask = (icon_br > th).astype(np.uint8) * 255 if th >= 160 else (icon_br < th).astype(np.uint8) * 255
                scaled = cv2.resize(mask, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
                pad = cv2.copyMakeBorder(scaled, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=0)
                for candidate in [pad, cv2.bitwise_not(pad)]:
                    for psm in [10, 7, 8]:
                        text = pytesseract.image_to_string(candidate, config=f"--psm {psm} -c tessedit_char_whitelist=012345").strip()
                        if text and re.fullmatch(r"[0-5]", text):
                            votes_br.append(int(text))
            if votes_br:
                from collections import Counter
                features["elevation"] = Counter(votes_br).most_common(1)[0][0]
        except Exception:
            pass

    return features


def read_normandy_elevation(gray: np.ndarray) -> int | None:
    """Read the tiny top-right contour badge, not the bottom-right strap or card number."""
    elevation_region = CARD_REGIONS["terrain"]["Normandy Terrain"]["elevation"]["crop"]
    badge = _crop_region(gray, elevation_region)
    bh, bw = badge.shape
    # The elevation marker is a signed value (e.g. +1) inside the contour icon;
    # card number is the separate small stamp farther right. Require the sign
    # from its own crop so card-number digits cannot become elevations.
    sign_crop = badge[:, :max(1, int(bw * 0.45))]
    sign_img = cv2.resize(sign_crop, (0, 0), fx=16, fy=16, interpolation=cv2.INTER_CUBIC)
    sign_votes = []
    for psm in (6, 7, 8, 10, 13):
        sign = pytesseract.image_to_string(
            sign_img, config=f"--psm {psm} -c tessedit_char_whitelist=+-"
        ).strip()
        if "+" in sign:
            sign_votes.append("+")
        elif "-" in sign:
            sign_votes.append("-")
    if not sign_votes:
        return None
    from collections import Counter
    sign, sign_count = Counter(sign_votes).most_common(1)[0]
    # This badge is only ~10 px tall; Tesseract's reliable sparse-text mode may
    # return a single signed reading, so one explicit sign is sufficient.

    # Include the following digit while excluding the separate card-number stamp.
    crop = badge
    if crop.size == 0:
        return None
    enlarged = cv2.resize(crop, (0, 0), fx=16, fy=16, interpolation=cv2.INTER_CUBIC)
    votes = []
    for psm in (7, 10, 13):
        text = pytesseract.image_to_string(
            enlarged, config=f"--psm {psm} -c tessedit_char_whitelist=+-012345"
        ).strip()
        matches = re.findall(r"([+-])\s*([0-6])", text)
        matching_sign = [int(digit) * (1 if polarity == "+" else -1)
                         for polarity, digit in matches if polarity == sign]
        if matching_sign:
            value = matching_sign[-1]
            if -2 <= value <= 6:
                votes.append(value)
    if not votes:
        return None
    value, count = Counter(votes).most_common(1)[0]
    return value if count >= 1 else None


def extract_action_card_features(img_bgr: np.ndarray, filename: str) -> dict:
    """Extract Action Card anatomy:
    1. Card Number (from filename A01..A50 or top-right OCR)
    2. Activated Commands (Top-left Helmet icon number: 1 to 5)
    3. Initiative Commands (Square box below helmet: 1 to 4)
    4. Action Attempt Header (Top-center: Cover, Rally, or Contact)
    5. Anti-Tank Number (Lower-right tank reticle: AT 5 to AT 9)
    6. Attempt & Specialty Icons (Cover, Rally, Contact, HQ Event, etc.)
    7. Hit Effect Section (Lower-center table)
    8. Combat Resolution Summary (Left column direct-fire table)
    """
    h, w, _ = img_bgr.shape
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    action_regions = CARD_REGIONS["action"]

    m_num = re.search(r"^A(\d{2})", filename, re.IGNORECASE)
    card_num = int(m_num.group(1)) if m_num else None

    # 1. Action Attempt Header (Cover / Rally / Contact)
    # y: 4%..18%, x: 40%..92%
    crop_hdr = _crop_region(gray, action_regions["header"]["crop"])
    s_hdr = cv2.resize(crop_hdr, (0, 0), fx=3, fy=3)
    txt_hdr = pytesseract.image_to_string(s_hdr, config="--psm 11").strip().lower()
    if not txt_hdr:
        txt_hdr = pytesseract.image_to_string(s_hdr, config="--psm 6").strip().lower()

    action_attempt = None
    if "cover" in txt_hdr:
        action_attempt = "Cover"
    elif "rally" in txt_hdr:
        action_attempt = "Rally"
    elif "contact" in txt_hdr:
        action_attempt = "Contact"

    # 2. Activated Commands: read only the printed numeral inside the helmet.
    # The former broad crop included helmet artwork and nearby card graphics,
    # which frequently won OCR votes over the actual digit. Crop the centered
    # numeral itself to avoid the helmet rim and adjacent printed marks.
    helmet_digit = _crop_region(gray, action_regions["commands"]["crop"])
    helmet_scaled = cv2.resize(helmet_digit, (0, 0), fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    cmd_val = None
    helmet_votes = []
    for threshold in [185, 205, 225, 245]:
        # Numerals are light within the dark helmet. Threshold to black ink on white.
        foreground = (helmet_scaled > threshold).astype(np.uint8) * 255
        ocr_image = cv2.copyMakeBorder(
            cv2.bitwise_not(foreground), 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=255
        )
        for psm in [10, 8]:
            text = pytesseract.image_to_string(
                ocr_image,
                config=f"--psm {psm} -c tessedit_char_whitelist=0123456789GgSsBb",
            ).strip()
            text = (
                text.replace("G", "6").replace("g", "6")
                .replace("S", "5").replace("s", "5")
                .replace("b", "6")
            )
            # Require a single valid command digit; reject multi-digit artwork noise.
            if len(text) == 1 and text in "123456":
                helmet_votes.append(int(text))
    if helmet_votes:
        from collections import Counter
        cmd_val = Counter(helmet_votes).most_common(1)[0][0]

    # The Action Deck uses consistent printed command bands. The helmet scans
    # are too small/noisy for reliable independent OCR (the rim and silhouette
    # often become false digits), so use the verified card-number bands as the
    # authoritative value. Keep OCR above as a fallback for nonstandard files.
    if card_num is not None:
        if card_num <= 2:
            cmd_val = 6
        elif card_num <= 10:
            cmd_val = 5
        elif card_num <= 24:
            cmd_val = 4
        elif card_num <= 36:
            cmd_val = 3
        elif card_num <= 46:
            cmd_val = 2
        else:
            cmd_val = 1

    # 3. Initiative Box (Below helmet: y: 18%..30%, x: 18%..40%)
    box_init = _crop_region(gray, action_regions["initiative"]["crop"])
    init_val = None
    for th in [110, 125, 95, 140]:
        m = ((box_init < th).astype(np.uint8) * 255)
        pad = cv2.copyMakeBorder(cv2.resize(m, (0, 0), fx=4, fy=4), 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=0)
        for psm in [8, 10, 13, 6]:
            t = pytesseract.image_to_string(pad, config=f"--psm {psm} -c tessedit_char_whitelist=0123456").strip()
            if t in ["0", "1", "2", "3", "4", "5", "6"]:
                init_val = int(t)
                break
        if init_val is not None:
            break

    # 4. Anti-Tank Rating: printed value follows five-card bands across this deck.
    # Use the card number as authoritative; reticle strokes make OCR unreliable.
    crop_at = _crop_region(gray, action_regions["anti_tank"]["crop"])
    at_val = 9 - ((card_num - 1) // 5) if card_num is not None and 1 <= card_num <= 50 else None

    # 5. Icons in Attempt & Specialty area
    icons = []
    if action_attempt:
        icons.append(action_attempt)

    # 5b. Text inside the attempt area (Short! / Jam!) comes from the same
    # shared region map as UI highlights and the visual-icon crop.
    attempt_area = _crop_region(gray, action_regions["attempt_text"]["crop"])
    txt_all = pytesseract.image_to_string(cv2.resize(attempt_area, (0, 0), fx=2, fy=2), config="--psm 11").strip()

    # Detect Higher HQ only from its small printed label beside the handset;
    # broad OCR over the whole attempt area can misread map/artwork as "HQ".
    hq_label = gray[int(h * 0.63):int(h * 0.72), int(w * 0.39):int(w * 0.56)]
    hq_scaled = cv2.resize(hq_label, (0, 0), fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    has_hq = any(
        pytesseract.image_to_string(
            hq_scaled,
            config=f"--psm {psm} -c tessedit_char_whitelist=HQhq",
        ).strip().upper() == "HQ"
        for psm in [6, 7, 8, 11]
    )
    has_short = bool(re.search(r"Short", txt_all, re.IGNORECASE))
    has_jam = bool(re.search(r"Jam", txt_all, re.IGNORECASE))

    # Main icon graphic area: y: 20%..56%, x: 40%..92%
    main_color = _crop_region(img_bgr, action_regions["attempt_icons"]["crop"])
    main_gray = cv2.cvtColor(main_color, cv2.COLOR_BGR2GRAY)

    hsv = cv2.cvtColor(main_color, cv2.COLOR_BGR2HSV)
    yellow_mask = cv2.inRange(hsv, np.array([12, 80, 120]), np.array([42, 255, 255]))
    num_y, labels_y, stats_y, _ = cv2.connectedComponentsWithStats(yellow_mask)
    burst_count = sum(1 for i in range(1, num_y) if stats_y[i, cv2.CC_STAT_AREA] > 25)

    m_dark = ((main_gray < 75).astype(np.uint8) * 255)
    num_d, labels_d, stats_d, _ = cv2.connectedComponentsWithStats(m_dark)
    comps = []
    for i in range(1, num_d):
        bw = stats_d[i, cv2.CC_STAT_WIDTH]
        bh = stats_d[i, cv2.CC_STAT_HEIGHT]
        a = stats_d[i, cv2.CC_STAT_AREA]
        if a > 40:
            comps.append((bw, bh, a))

    has_spot = False
    has_infil = False
    has_grenade = False
    has_cff = False
    has_bn_cff = False

    if has_jam:
        pass
    elif has_short:
        has_cff = True
    elif burst_count >= 3:
        has_bn_cff = True
    elif burst_count >= 1:
        has_cff = True
    else:
        for bw, bh, a in comps:
            aspect = float(bw) / float(bh) if bh > 0 else 0
            if (aspect > 1.7 and bw >= 55 and a > 400) or (len(comps) >= 4 and any(c[0] > 55 for c in comps)):
                has_infil = True
                break

        if not has_infil:
            for bw, bh, a in comps:
                if 16 <= bw <= 38 and 22 <= bh <= 48 and 180 < a < 800:
                    has_grenade = True
                    break

        if not has_infil and not has_grenade:
            for bw, bh, a in comps:
                if bw >= 48 and bh >= 48 and a > 800:
                    has_spot = True
                    break

    if has_spot and "Spotting" not in icons:
        icons.append("Spotting")
    if has_infil and "Infiltrate" not in icons:
        icons.append("Infiltrate")
    if has_grenade and "Grenade" not in icons:
        icons.append("Grenade")
    if has_cff and "Call for Fire" not in icons:
        icons.append("Call for Fire")
    if has_bn_cff and "Battalion Fire Mission" not in icons:
        icons.append("Battalion Fire Mission")
    if has_short and "Call for Fire Short!" not in icons:
        icons.append("Call for Fire Short!")
    if has_hq and "HQ Event" not in icons:
        icons.append("HQ Event")
    if has_jam and "Jam!" not in icons:
        icons.append("Jam!")

    # 6. Hit Effect row (y: 75%..87%, x: 38%..96%). Store only the three
    # result values, ordered Vet, Line, Green; omit the title and headers.
    crop_hit = _crop_region(img_bgr, action_regions["hit_effects"]["crop"])
    hit_text = pytesseract.image_to_string(
        cv2.resize(crop_hit, (0, 0), fx=2, fy=2), config="--psm 6"
    ).strip()
    hit_tail = re.split(r"vet\s+line\s+green", hit_text, flags=re.IGNORECASE)[-1]
    if hit_tail == hit_text:
        rows = [row.strip() for row in re.split(r"[|\n]+", hit_text) if row.strip()]
        hit_tail = rows[-1] if rows else ""
    hit_values = re.findall(r"[A-Za-z0-9]+", hit_tail)
    if len(hit_values) < 3:
        # OCR may miss small result codes. Keep three explicit slots so that
        # their positional meaning remains Vet, Line, Green for manual review.
        hit_values.extend(["?"] * (3 - len(hit_values)))
    t_hit = " ".join(hit_values[:3])

    # 7. Combat Resolution summary (y: 26%..76%, x: 3%..35%)
    crop_combat = _crop_region(gray, action_regions["combat_resolution"]["crop"])
    t_comb = pytesseract.image_to_string(cv2.resize(crop_combat, (0, 0), fx=2, fy=2), config="--psm 6").strip()
    comb_results = []
    for line in t_comb.splitlines():
        line = line.strip().upper()
        if any(res in line for res in ["HIT", "PIN", "MISS"]):
            comb_results.append(line)
    combat_summary = "; ".join(comb_results[:6]) if comb_results else None

    # 8. Random Number Section (Columns 2 through 12): template matching against
    # verified cards #48/#50 (see rn_reader.py). Never decreases left to right.
    rn_matrix = read_random_number_row(gray, region=action_regions["random_numbers"]["crop"])
    rn_summary = " ".join(str(rn_matrix[str(c)]) for c in range(2, 13))

    return {
        "card_number": card_num,
        "commands": cmd_val,
        "initiative": init_val,
        "action_attempt": action_attempt,
        "anti_tank": at_val,
        "attempt_icons": icons,
        "spot_concentrate_fire": has_spot,
        "infiltrate": has_infil,
        "grenade": has_grenade,
        "call_for_fire": has_cff,
        "battalion_fire_mission": has_bn_cff,
        "call_for_fire_short": has_short,
        "hq_event": has_hq,
        "jam": has_jam,
        "hit_effects": t_hit or None,
        "combat_resolution": combat_summary,
        "random_numbers": rn_matrix,
        "random_number": rn_summary,
    }


def infer_terrain_category(name: str) -> str:
    canonical = name.lower()
    if any(k in canonical for k in ["woods", "forest", "jungle", "bamboo", "orchard", "grove", "plantation"]):
        return "Forest / Woods"
    if any(k in canonical for k in ["hill", "rocky", "ridge", "peak", "cliff"]):
        return "Rough / Hill"
    if any(k in canonical for k in ["village", "farm", "church", "cemetery", "graveyard", "building", "citadel"]):
        return "Urban / Building"
    if any(k in canonical for k in ["marsh", "swamp", "canal", "paddy", "surf", "beach", "pond", "water"]):
        return "Water / Marsh"
    if any(k in canonical for k in ["bocage", "hedgerow", "embankment", "dune"]):
        return "Linear Obstacle"
    return "Open"


def classify_single_card(path: Path) -> dict:
    filename = path.name
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Could not load image: {path}")

    h, w, _ = img.shape
    fmt = path.suffix.strip(".").lower()

    card_type, deck, expansion, purpose = classify_high_level(img, filename)

    stem = path.stem
    clean_id = re.sub(r"[^A-Za-z0-9_-]", "-", stem).strip("-").upper()
    prefix = "FOF-CARD"
    if card_type == "terrain":
        prefix = "FOF-TERRAIN"
    elif card_type == "action":
        prefix = "FOF-ACTION"
    elif card_type == "fsa":
        prefix = "FOF-FSA"
    elif card_type == "staging_area":
        prefix = "FOF-STAGING"
    card_id = f"{prefix}-{clean_id}"

    terrain_details = None
    action_details = None
    cv_labels = []

    if card_type == "terrain":
        borders = detect_terrain_borders(img)
        features = extract_terrain_card_features(img, filename)

        # Clean display title and terrain name
        title = stem
        if filename.startswith(("N", "K", "V", "A", "C", "P")) and re.match(r"^[NKACP]\d{2}", filename):
            raw = filename[3:].rsplit(".", 1)[0].replace("-", "").strip()
            title = f"{filename[:3]} - {raw or 'Terrain'}"
            terrain_name = raw.title() or "Terrain"
        elif filename.startswith("Hue") and re.match(r"^Hue\d{2}", filename):
            title = f"Hue {filename[3:5]}"
            terrain_name = "Urban Street / Building"
        elif re.match(r"^0\d{2}", filename):
            # Check if OCR found a real name like GRAVEYARD, CHURCH, FARM, VILLAGE, ROAD EMBANKMENT
            ocr_upper = features["terrain_name_ocr"].upper()
            found_name = None
            if "EMBANKMENT" in ocr_upper or "EMBAN" in ocr_upper:
                found_name = "Road Embankment"
            else:
                for cand in ["GRAVEYARD", "CHURCH", "VILLAGE", "FARM", "FOREST", "SCRUB", "DRAW", "ROAD", "FIELD"]:
                    if cand in ocr_upper:
                        found_name = cand.title()
                        break
            terrain_name = found_name or "Ardennes Terrain"
            title = f"Ardennes #{filename[:3]} - {terrain_name}"
        else:
            terrain_name = stem.title()

        category = infer_terrain_category(terrain_name)

        # Apply detected corner values or defaults
        cov_h = features["cover_high"] if features["cover_high"] is not None else (2 if category == "Urban / Building" else (1 if category == "Forest / Woods" else 0))
        cov_l = features["cover_low"]  # None if the card has only a single cover value!
        elev = features["elevation"] if features["elevation"] is not None else (1 if category == "Rough / Hill" else 0)
        cov_pot = features["cover_potential"] if features["cover_potential"] is not None else (2 if category in ["Urban / Building", "Forest / Woods"] else 1)
        cov_draw = features["cover_draw"] if features["cover_draw"] is not None else 3

        terrain_details = {
            "terrain_name": terrain_name,
            "terrain_category": category,
            "card_number": features["card_number"] or filename[:3],
            "vehicle_access": features["vehicle_access"],
            "cover_high": cov_h,
            "cover_low": cov_l,
            "elevation": elev,
            "cover_potential": cov_pot,
            "cover_draw": cov_draw,
            "burst_modifier": features.get("burst_modifier", 0),
            "landing_zone": "Good" if category == "Open" else "None",
            "trafficability": "good" if category == "Open" else ("poor" if category in ["Forest / Woods", "Water / Marsh"] else "fair"),
            "borders": borders,
            "features": [terrain_name],
        }

        # Normandy's cover/capacity/draw digits are stylized badges. Use the
        # visually calibrated deck map rather than the unreliable broad OCR.
        m_normandy = re.match(r"^N(\d{2})\b", filename, re.IGNORECASE)
        if m_normandy:
            coverage = NORMANDY_COVERAGE.get(int(m_normandy.group(1)))
            if coverage:
                (terrain_details["cover_high"], terrain_details["cover_low"],
                 terrain_details["cover_potential"], terrain_details["cover_draw"]) = coverage

        cv_labels = [
            f"border_N:{borders['north']}",
            f"border_E:{borders['east']}",
            f"border_S:{borders['south']}",
            f"border_W:{borders['west']}",
            f"cover:+{cov_h}" + (f"/+{cov_l}" if cov_l is not None else ""),
            f"veh:{features['vehicle_access']}",
            f"cap:{cov_pot}",
            f"draw:{cov_draw}",
            f"elev:{elev}",
        ]
        if features["card_number"]:
            cv_labels.append(f"card#:{features['card_number']}")

    elif card_type == "action":
        if "reshuffle" in filename.lower():
            title = "Reshuffle Card"
            card_id = "FOF-ACTION-RESHUFFLE"
            action_details = {
                "card_number": None,
                "commands": None,
                "initiative": None,
                "action_attempt": None,
                "anti_tank": None,
                "random_number": None,
                "attempt_icons": ["Reshuffle"],
                "hit_effects": None,
                "combat_resolution": None,
                "direction_arrow": None,
            }
            cv_labels.append("action:Reshuffle")
        else:
            act_feat = extract_action_card_features(img, filename)
            num = act_feat["card_number"]
            card_id = f"FOF-ACTION-{num:03d}" if num else f"FOF-ACTION-{clean_id}"
            attempt_str = f" - {act_feat['action_attempt']}" if act_feat["action_attempt"] else ""
            title = f"Action Card #{num}{attempt_str}" if num else stem
            action_details = {
                "card_number": num,
                "commands": act_feat["commands"],
                "initiative": act_feat["initiative"],
                "action_attempt": act_feat["action_attempt"],
                "anti_tank": act_feat["anti_tank"],
                "random_number": act_feat["random_number"],
                "random_numbers": act_feat["random_numbers"],
                "attempt_icons": act_feat["attempt_icons"],
                "spot_concentrate_fire": act_feat["spot_concentrate_fire"],
                "infiltrate": act_feat["infiltrate"],
                "grenade": act_feat["grenade"],
                "call_for_fire": act_feat["call_for_fire"],
                "battalion_fire_mission": act_feat["battalion_fire_mission"],
                "call_for_fire_short": act_feat["call_for_fire_short"],
                "hq_event": act_feat["hq_event"],
                "jam": act_feat["jam"],
                "hit_effects": act_feat["hit_effects"],
                "combat_resolution": act_feat["combat_resolution"],
                "direction_arrow": None,
            }
            if num:
                cv_labels.append(f"card#:{num}")
            if act_feat["commands"]:
                cv_labels.append(f"cmd:{act_feat['commands']}")
            if act_feat["initiative"]:
                cv_labels.append(f"init:{act_feat['initiative']}")
            if act_feat["action_attempt"]:
                cv_labels.append(f"attempt:{act_feat['action_attempt']}")
            if act_feat["anti_tank"]:
                cv_labels.append(f"at:{act_feat['anti_tank']}")
            if act_feat["spot_concentrate_fire"]:
                cv_labels.append("icon:Spot")
            if act_feat["infiltrate"]:
                cv_labels.append("icon:Infil")
            if act_feat["grenade"]:
                cv_labels.append("icon:Grenade")
            if act_feat["call_for_fire"]:
                cv_labels.append("icon:CFF")
            if act_feat["battalion_fire_mission"]:
                cv_labels.append("icon:BnCFF")
            if act_feat["call_for_fire_short"]:
                cv_labels.append("icon:Short!")
            if act_feat["hq_event"]:
                cv_labels.append("icon:HQ")
            if act_feat["jam"]:
                cv_labels.append("icon:Jam!")
            if act_feat["random_number"]:
                cv_labels.append(f"rn:{act_feat['random_number']}")

    else:
        title = stem

    notes = f"Classified as {card_type} ({deck}); CV labels: {', '.join(cv_labels) if cv_labels else 'none'}"

    return {
        "id": card_id,
        "name": title,
        "card_type": card_type,
        "deck": deck,
        "expansion": expansion,
        "purpose": purpose,
        "image": {
            "filename": f"cards/{filename}",
            "width": w,
            "height": h,
            "format": fmt if fmt in ["png", "jpg", "jpeg", "webp"] else "png",
        },
        "terrain_details": terrain_details,
        "action_details": action_details,
        "classification": {
            "reviewed": False,
            "reviewer": None,
            "reviewed_at": None,
            "notes": notes,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Classify Fields of Fire cards via CV and OCR")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cards processed")
    parser.add_argument("--action-only", action="store_true", help="Reclassify A01-A50 and merge into the existing card catalog")
    parser.add_argument("--normandy-coverage-only", action="store_true", help="Reclassify N01-N55, merging only calibrated cover/capacity/draw values")
    parser.add_argument("--normandy-elevation-only", action="store_true", help="Read only top-right elevation badges on N01-N55")
    args = parser.parse_args()

    if args.normandy_coverage_only:
        # This calibrated pass reads the 55 card-number values directly from the
        # checked badge map; avoid rerunning unrelated OCR over all terrain regions.
        if not OUTPUT_JSON.exists():
            parser.error(f"Cannot update Normandy coverage; missing catalog: {OUTPUT_JSON}")
        with OUTPUT_JSON.open("r", encoding="utf-8") as f:
            catalog = json.load(f)
        updated = 0
        for record in catalog:
            if record.get("deck") != "Normandy Terrain" or record.get("card_type") != "terrain":
                continue
            image_name = Path((record.get("image") or {}).get("filename", "")).name
            match = re.match(r"^N(\d{2})\b", image_name, re.IGNORECASE)
            if not match:
                continue
            coverage = NORMANDY_COVERAGE.get(int(match.group(1)))
            if coverage is None:
                continue
            terrain = record.setdefault("terrain_details", {})
            (terrain["cover_high"], terrain["cover_low"],
             terrain["cover_potential"], terrain["cover_draw"]) = coverage
            updated += 1
        if updated != 55:
            parser.error(f"Expected 55 Normandy terrain records, updated {updated}")
        with OUTPUT_JSON.open("w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Updated calibrated coverage fields on {updated} Normandy Terrain cards; no OCR was run.")
        return

    if args.normandy_elevation_only:
        if not OUTPUT_JSON.exists():
            parser.error(f"Cannot update Normandy elevation; missing catalog: {OUTPUT_JSON}")
        with OUTPUT_JSON.open("r", encoding="utf-8") as f:
            catalog = json.load(f)
        updated = 0
        for record in catalog:
            if record.get("deck") != "Normandy Terrain" or record.get("card_type") != "terrain":
                continue
            filename = Path((record.get("image") or {}).get("filename", "")).name
            match = re.match(r"^N(\d{2})\b", filename, re.IGNORECASE)
            if not match:
                continue
            image_path = CARDS_DIR / filename
            image = cv2.imread(str(image_path))
            if image is None:
                continue
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            elevation = read_normandy_elevation(gray)
            # Only replace the catalog value when the signed badge was detected;
            # unmarked cards retain their existing terrain/default elevation.
            if elevation is not None:
                record.setdefault("terrain_details", {})["elevation"] = elevation
                updated += 1
        with OUTPUT_JSON.open("w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Updated {updated} Normandy elevations from top-right signed badges.")
        return

    files = sorted([f for f in CARDS_DIR.glob("*") if f.is_file()])
    if args.action_only:
        files = [f for f in files if re.fullmatch(r"A(?:0[1-9]|[1-4][0-9]|50)\.jpg", f.name, re.IGNORECASE)]
    if args.normandy_coverage_only:
        files = [f for f in files if re.match(r"^N(?:0[1-9]|[1-4][0-9]|5[0-5])\b", f.name, re.IGNORECASE)]
    if args.limit:
        files = files[:args.limit]

    print(f"Running Card Classifier across {len(files)} card images...")

    records = []
    for idx, path in enumerate(files):
        try:
            rec = classify_single_card(path)
            records.append(rec)
            if (idx + 1) % 50 == 0 or (idx + 1) == len(files):
                print(f"  Processed {idx + 1}/{len(files)} cards...")
        except Exception as exc:
            print(f"  [ERROR] {path.name}: {exc}")

    # All classifier runs update suggestions only. Keep other records and preserve
    # every explicitly verified field and review marker in the existing catalog.
    if OUTPUT_JSON.exists():
        with OUTPUT_JSON.open("r", encoding="utf-8") as f:
            existing_records = json.load(f)
        fresh_by_image = {
            (rec.get("image") or {}).get("filename"): rec
            for rec in records
            if (rec.get("image") or {}).get("filename")
        }
        merged_records = []
        matched_images = set()
        for existing in existing_records:
            image_name = (existing.get("image") or {}).get("filename")
            fresh = fresh_by_image.get(image_name)
            if not fresh:
                merged_records.append(existing)
                continue

            matched_images.add(image_name)
            refreshed = {**existing, **fresh}
            old_classification = existing.get("classification") or {}
            new_classification = fresh.get("classification") or {}
            refreshed["classification"] = {**new_classification, **old_classification}
            for section in ("terrain_details", "action_details"):
                old_details = existing.get(section) or {}
                new_details = fresh.get(section) or {}
                if not old_details and not new_details:
                    continue
                details = {**old_details, **new_details}
                verified = list(old_details.get("verified_fields", []))
                for field in verified:
                    if field in old_details:
                        details[field] = old_details[field]
                if verified:
                    details["verified_fields"] = verified
                refreshed[section] = details
            merged_records.append(refreshed)

        merged_records.extend(
            fresh for image_name, fresh in fresh_by_image.items()
            if image_name not in matched_images
        )
        records = merged_records

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Successfully wrote {len(records)} classified card records to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
