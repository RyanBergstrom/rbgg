#!/usr/bin/env python3
"""Fields of Fire counter classifier (Compound Ratings & Weapon Parsing).

Scans 75x75 counter images, isolates functional counter regions (Header,
Middle Label, Left/Right Stats, Bottom Status Strip), and extracts structured metadata using:
  - Inverse Otsu thresholding & Cubic upscaling for OCR readability
  - HSV Color/Contour detection for yellow text, step dots, and VOF markers
  - Full compliance with fof-counter.v1.json schema across all Unit Types A-J

Dependencies:
  pip install pillow opencv-python pytesseract imagehash jsonschema
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

try:
    import jsonschema
except ImportError as exc:
    raise SystemExit("jsonschema is required: pip install jsonschema") from exc

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r'C:\Users\p211587\AppData\Local\Tesseract-OCR\tesseract.exe'
except ImportError as exc:
    raise SystemExit("pytesseract is required: pip install pytesseract") from exc

SCHEMA_PATH_DEFAULT = Path("documentation/fof/counter-schema.json")
#IMAGES_DIR_DEFAULT = Path("api/img/fof/ocr-test") if Path("api/img/fof/ocr-test").is_dir() else Path("documentation/fof/test-images")
IMAGES_DIR_DEFAULT = Path("api/img/fof/counters") if Path("api/img/fof/counters").is_dir() else Path("documentation/fof/test-images")
OUT_DEFAULT = Path("api/configs/fof/counters.json")
REVIEW_QUEUE_DEFAULT = Path("documentation/fof/review_queue.jsonl")

# ── Mappings & Constants ─────────────────────────────────────────────────────

COUNTRY_PREFIX_MAP = {
    "us": "US",
    "katusa": "US",
    "1atf": "Australian",
    "ge": "German",
    "ger": "German",
    "pzg": "German",
    "vg": "German",
    "ija": "Japanese",
    "ja": "Japanese",
    "nkpa": "NKPA",
    "ccf": "Chinese",
    "chin": "Chinese",
    "vietcong": "VietCong",
    "vc": "VietCong",
    "nva": "NVA",
    "arvn": "ARVN",
    "german": "German",
    "wehrmacht": "German",
}

COUNTRY_PATTERN_MAP = {
    "katusa": "US",
    "japanese": "Japanese",
    "ija": "Japanese",
    "chinese": "Chinese",
    "ccf": "Chinese",
    "nkpa": "NKPA",
    "vietcong": "VietCong",
    "vc": "VietCong",
    "nva": "NVA",
    "german": "German",
    "tiger": "German",
    "panzer": "German",
    "pzg": "German",
    "wehrmacht": "German",
    "us": "US",
    "2para": "Commonwealth",
    "para": "Commonwealth",
    "parachute": "Commonwealth",
    "22sas": "Commonwealth",
    "sas": "Commonwealth",
    "viet minh": "VietCong",
    "north vietnam": "NVA",
    "1atf": "Australian",
    "1st infantry": "US",
    "1st cav": "US",
    "1-1": "US",
    "1-2": "US",
    "1-3": "US",
    "1_1": "US",
    "1_2": "US",
    "1_3": "US",
    "bw": "German",
    "north korea": "NKPA",
    "arvn": "ARVN",
    "south vietnam": "ARVN",
}

SIDE_SUFFIX_MAP = {
    "b": "back",
    "f": "front",
    "al": "alternate",
    "brk": "broken",
    "red": "reduced",
}

EXPERIENCE_RATING_MAP = {
    "G": "Green",
    "L": "Line",
    "V": "Veteran",
    "E": "Elite",
    "S": "S_rated",
    "A": "A_rated",
}

# Valid range band enum values per FoF rules (mortars have minimum Close range: C-L, C-V)
RANGE_BAND_ENUM = {"P", "C", "L", "V", "C-L", "C-V"}


LAT_TYPES_ENUM = {
    "Fire Team",
    "Assault Team",
    "Litter Team",
    "Paralyzed Team",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_filename(name: str) -> dict:
    """Extract structural hints from the counter filename based on Units A-J."""
    stem = Path(name).stem.lower()
    hints: dict = {}

    for prefix, country in COUNTRY_PREFIX_MAP.items():
        if stem.startswith(prefix):
            hints["country"] = country
            break

    for pattern, country in COUNTRY_PATTERN_MAP.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(pattern) + r"(?![a-z0-9])", stem):
            hints["country"] = hints.get("country") or country
            break

    for suffix, side in SIDE_SUFFIX_MAP.items():
        if re.search(r"(?:[_\s-]|(?<=\d))" + re.escape(suffix) + r"$", stem):
            hints["side"] = side
            break

    # Strip faction prefixes before searching for squad/platoon numbers
    clean_stem = re.sub(r"^(?:1atf|2para|22sas|katusa|us|ger?|ija|nkpa|ccf|vc|nva|arvn)[-_\s]*", "", stem)
    m = re.search(r"(?<!\d)(\d+)[-_/](\d+)(?!\d)", clean_stem)
    if m:
        hints["squad_number"] = m.group(1)
        hints["platoon"] = m.group(2)
    else:
        m_single = re.match(r"^(\d+)[-_ ]", clean_stem)
        if m_single:
            hints["squad_number"] = m_single.group(1)

    m = re.search(r"(\d+)\s*step", stem)
    if m:
        hints["steps_total"] = int(m.group(1))

    # Priority 1: Potential Contact markers (e.g. PC C)
    m_pc = re.search(r"\bpc\s+([a-z0-9]+)\b", stem)
    if m_pc:
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "potential_contact"
        hints["subtype_hint"] = "potential_contact"
        hints["pc_id"] = m_pc.group(1).upper()
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints

    # Priority 2: Tactical Control & Commands Complete markers (Control_*, Commands * complete, FPF, Route Point, Target)
    if re.search(r"\bcontrol[_\s]|(?<![a-z0-9])commands?\b|(?<![a-z0-9])complete\b|\broute\s*point\b|\bfpf\b|\btarget\s+[a-z0-9]+", stem):
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "tactical_control"
        hints["subtype_hint"] = "tactical_control"
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints

    # Priority 3: Ammo & Fire Mission Token Parsing
    if re.search(r"\b(ammo|50cal|hmg\s*ammo|mg\s*ammo|arty\s*fm|hvy\s*mtr\s*fm|hv\s*mtr\s*fm|fire\s*mission)\b", stem) or stem.startswith("ammo"):
        hints["category_hint"] = "marker"
        if "fire" in stem and "mission" in stem:
            hints["marker_type_hint"] = "fire_mission"
            hints["ammo_type_hint"] = "Fire Mission"
            hints["is_fire_mission"] = True
        elif "arty" in stem and "fm" in stem:
            hints["marker_type_hint"] = "fire_mission"
            hints["ammo_type_hint"] = "ARTY FM"
            hints["is_fire_mission"] = True
        elif ("hvy" in stem or "hv" in stem) and "mtr" in stem and "fm" in stem:
            hints["marker_type_hint"] = "fire_mission"
            hints["ammo_type_hint"] = "HV MTR FM"
            hints["is_fire_mission"] = True
        elif "50cal" in stem or ".50" in stem:
            hints["marker_type_hint"] = "ammo"
            hints["ammo_type_hint"] = ".50 Cal AMMO"
            hints["is_fire_mission"] = False
        elif "hmg" in stem:
            hints["marker_type_hint"] = "ammo"
            hints["ammo_type_hint"] = "HMG AMMO"
            hints["is_fire_mission"] = False
        elif re.search(r"\b(mg|lmg|mmg)\b", stem):
            hints["marker_type_hint"] = "ammo"
            hints["ammo_type_hint"] = "MG AMMO"
            hints["is_fire_mission"] = False
        else:
            hints["marker_type_hint"] = "ammo"
            hints["ammo_type_hint"] = "AMMO"
            hints["is_fire_mission"] = False
        idx_match = re.search(r"(\d+)\s*(?:\.png|\.jpg)?$", stem)
        if idx_match:
            hints["ammo_index"] = int(idx_match.group(1))
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints

    # Priority 4: Assets & Visibility / Smoke
    if re.search(r"\b(assets?|smoke|wp)\b", stem) or stem.startswith("marker -"):
        if re.search(r"\bassets?\b", stem):
            hints["category_hint"] = "asset"
            hints["subtype_hint"] = "asset"
            hints["asset_type"] = "Smoke - Screening" if "smoke" in stem or "screening" in stem else "Asset"
        else:
            hints["category_hint"] = "marker"
            hints["marker_type_hint"] = "visibility"
            hints["subtype_hint"] = "visibility"
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints

    # Priority 5: Combat & Status Markers
    if re.search(r"\bvof\b", stem):
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "vof"
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints
    elif re.search(r"\bpdf\b|primary direction", stem):
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "pdf"
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints
    elif re.search(r"\bexposed\b", stem):
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "exposed"
        hints["subtype_hint"] = "exposed"
        hints["cover_type_hint"] = "standard"
        hints["cover_modifier"] = -2
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints
    elif re.search(r"\bpin(ned)?\b", stem):
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "pin"
        hints["subtype_hint"] = "pin"
        hints["cover_type_hint"] = "standard"
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints
    elif re.search(r"\bactivity[_\s]", stem) or "current activity" in stem:
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "current_activity"
        hints["subtype_hint"] = "current_activity"
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints
    elif re.search(r"\b(deep\s*bunker|bunker|pillbox|foxhole|foxholes|trench|cellar|church|upper\s*story|rooftop|cave|wreck|unspotted|unaware|cover)\b", stem):
        hints["category_hint"] = "marker"
        if "unspotted" in stem:
            hints["marker_type_hint"] = "unspotted"
            hints["cover_type_hint"] = "unspotted"
        elif "unaware" in stem:
            hints["marker_type_hint"] = "unaware"
            hints["cover_type_hint"] = "unaware"
        elif "deep bunker" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "deep_bunker"
        elif "bunker" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "bunker"
        elif "pillbox" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "pillbox"
        elif "foxhole" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "foxholes"
        elif "trench" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "trench"
        elif "cellar" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "cellar"
        elif "church" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "church_tower"
        elif "upper story" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "upper_story"
        elif "rooftop" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "rooftop"
        elif "cave" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "cave"
        elif "wreck" in stem:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "burning_wreck" if "burning" in stem else "wreck"
        else:
            hints["marker_type_hint"] = "cover"
            hints["cover_type_hint"] = "standard"
        print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
        return hints

    # Priority 6: Unit Types Mapping (A - J)
    if re.search(r"\b(sqd|squad)\b", stem):
        hints["unit_type_hint"] = "squad"
    elif re.search(r"(?:^|[_\s])(lat|litter|assault(?:\s*team)?|as+lt(?:\s*team)?|fire\s*team|paralyzed)(?:[_\s]|$)", stem):
        hints["unit_type_hint"] = "lat"
        if re.search(r"as+lt|fire\s*team", stem):
            hints["lat_subtype"] = "Fire Team"
        elif "litter" in stem:
            hints["lat_subtype"] = "Litter Team"
        elif "paralyzed" in stem:
            hints["lat_subtype"] = "Paralyzed Team"
    elif re.search(r"\b(mtr|mortar|60mm|81mm|4\.2|82mm|120mm)\b", stem):
        hints["unit_type_hint"] = "weapons_team"
        hints["weapon_type_hint"] = "Mortar"
    elif re.search(r"\b(engineer|engineers|engr|eng|sapper)\b", stem):
        hints["unit_type_hint"] = "weapons_team"
        hints["weapon_type_hint"] = "Engineers"
    elif re.search(r"\b(fo|spotter|observer)\b", stem):
        hints["unit_type_hint"] = "fo_spotter"
    elif re.search(r"(?:^|[_\s-])runner(?:[_\s-]|$)", stem):
        hints["unit_type_hint"] = "runner"
    elif re.search(r"\b(xo)\b", stem):
        hints["unit_type_hint"] = "co_xo"
    elif re.search(r"\b(1st\s*sgt|1sgt|1-sgt)\b", stem):
        hints["unit_type_hint"] = "co_1sgt"
    elif re.search(r"\b(co\s*hq|company\s*hq|coy\s*hq)\b", stem):
        hints["unit_type_hint"] = "hq_co"
    elif re.search(r"\b(s3|s-3|staff)\b", stem):
        hints["unit_type_hint"] = "co_staff"
    elif re.search(r"\b(casualty|cas)\b", stem):
        hints["unit_type_hint"] = "casualty"
    elif re.search(r"(?<![a-z0-9])(weapons|hmg|lmg|mmg|mg|bazooka|rpg|recoilless|rocket|machine gun|88mm|75mm|76mm|57mm|atg)(?![a-z0-9])|(?<![a-z0-9])wpns\w*", stem):
        hints["unit_type_hint"] = "weapons_team"
    elif re.search(r"\b(tiger|panzer|panther|stug|sherman|t-?34|tank|apc|vehicle|truck|aircraft|chopper|helo)\b", stem):
        hints["unit_type_hint"] = "vehicle" if not re.search(r"\b(aircraft|chopper|helo)\b", stem) else "aircraft"
        if re.search(r"\b(tiger|panzer|panther|stug)\b", stem):
            hints["country"] = hints.get("country") or "German"
    elif re.search(r"\b(bn hq|battalion hq)\b", stem):
        hints["unit_type_hint"] = "hq_bn"
    elif re.search(r"\b(plt hq|platoon hq)\b", stem):
        hints["unit_type_hint"] = "hq_plt"
    elif re.search(r"\b(hq)\b", stem):
        hints["unit_type_hint"] = "hq_plt"
    elif re.search(r"\b(sqd|squad)\b", stem):
        hints["unit_type_hint"] = "squad"
    elif not hints.get("unit_type_hint") and not hints.get("category_hint") and (hints.get("steps_total") or (hints.get("squad_number") and hints.get("platoon"))):
        hints["unit_type_hint"] = "squad"
        hints["category_hint"] = "unit"

    # Weapon type hint detection (only if non-Assault/Fire Team)
    if hints.get("unit_type_hint") != "lat" and not hints.get("weapon_type_hint"):
        if re.search(r"(?<![a-z0-9])hmg(?![a-z0-9])|(?<![a-z0-9])lmg(?![a-z0-9])|(?<![a-z0-9])mmg(?![a-z0-9])|(?<![a-z0-9])mg(?![a-z0-9])|machine gun", stem):
            hints["weapon_type_hint"] = "Machine Gun"
        elif re.search(r"bazooka|rpg|recoilless|rocket", stem):
            hints["weapon_type_hint"] = "Bazooka"
        elif re.search(r"88mm|75mm|76mm|57mm|\batg\b|anti.?tank", stem):
            hints["weapon_type_hint"] = "Anti-Tank Gun"
        elif re.search(r"flame|flamethrower|\bft\b", stem):
            hints["weapon_type_hint"] = "Flame Thrower"
        elif re.search(r"\bweapons\b|\bwpns\w*", stem):
            hints["weapon_type_hint"] = "Weapon"

    print(f"  [DEBUG - Filename Parse] Input Stem: '{stem}' -> Hints: {hints}", flush=True)
    return hints


# ── Specialized Regional Extractors ──────────────────────────────────────────

def extract_header_ocr(img_bgr: np.ndarray) -> str:
    """Crop top 28%, handle both light-on-dark and dark-on-light text, and strip noise artifacts."""
    h, w, _ = img_bgr.shape
    crop_height = int(h * 0.28)
    top_crop = img_bgr[0:crop_height, 0:w]
    gray = cv2.cvtColor(top_crop, cv2.COLOR_BGR2GRAY)

    # 1. Upscale 5x for Tesseract clarity
    scaled_gray = cv2.resize(gray, (w * 5, crop_height * 5), interpolation=cv2.INTER_CUBIC)

    # 2. Otsu thresholding (automatically separates text from background)
    _, thresh_otsu = cv2.threshold(scaled_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # If background is lighter than text (e.g. German counters), invert so text is always white-on-black
    if np.mean(thresh_otsu) > 127:
        thresh_otsu = cv2.bitwise_not(thresh_otsu)

    # 3. Contour Cleaning: Remove tiny background speckles/texture that cause 'eVveaulwy'
    contours, _ = cv2.findContours(thresh_otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    clean_mask = np.zeros_like(thresh_otsu)
    for c in contours:
        # Keep contours that match letter/number pixel dimensions (area >= 15 pixels)
        if cv2.contourArea(c) >= 15:
            cv2.drawContours(clean_mask, [c], -1, 255, -1)

    custom_config = r"--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/- "

    try:
        raw_text = pytesseract.image_to_string(clean_mask, config=custom_config).strip()
        clean_text = " ".join(raw_text.split())

        # Post-processing Regex: Strip stray lowercase noise prefix (e.g., 'eVveaulwy 3/1 PLT' -> '3/1 PLT')
        sanitized = re.sub(r"^[a-z]{3,}\s*", "", clean_text)

        print(f"  [DEBUG - Header OCR Raw] Text: '{raw_text}' -> Cleaned: '{sanitized}'", flush=True)
        return sanitized
    except Exception as exc:
        print(f"  [DEBUG - Header OCR Error] Exception: {exc}", flush=True)
        return ""


def extract_middle_text(img_bgr: np.ndarray, hints: dict | None = None) -> str:
    """Crop middle region and extract text like 'Fire Team' or 'Litter Team'."""
    h, w, _ = img_bgr.shape
    mid_crop = img_bgr[int(h * 0.30):int(h * 0.68), 0:w]

    # Fast pre-check: only units with side in ('back', 'reduced'), or unit_type_hint == 'lat', or yellow pixels need middle OCR
    hsv = cv2.cvtColor(mid_crop, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([10, 50, 110])
    upper_yellow = np.array([40, 255, 255])
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    yellow_pixels = cv2.countNonZero(yellow_mask)

    hints = hints or {}
    needs_middle = (
        hints.get("side") in {"back", "reduced"} or
        hints.get("unit_type_hint") in {"lat", "casualty"} or
        yellow_pixels > 15
    )
    if not needs_middle:
        return ""

    custom_config = r"--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "

    try:
        # Pass 1: Yellow mask text (if yellow pixels present)
        if yellow_pixels > 15:
            scaled_mask = cv2.resize(yellow_mask, (w * 5, mid_crop.shape[0] * 5), interpolation=cv2.INTER_CUBIC)
            kernel = np.ones((2, 2), np.uint8)
            processed = cv2.dilate(scaled_mask, kernel, iterations=1)
            raw_text = pytesseract.image_to_string(processed, config=custom_config).strip()
            clean_text = " ".join(raw_text.split())
            if clean_text and re.search(r"\b(fire\s*team|fire|team|aslt|assault|litter|paralyzed|casualty)\b", clean_text, re.IGNORECASE):
                print(f"  [DEBUG - Middle OCR] Matched keyword: '{clean_text}'", flush=True)
                return clean_text

        # Pass 2: Grayscale threshold 160 (normal then inverted) with immediate exit
        gray = cv2.cvtColor(mid_crop, cv2.COLOR_BGR2GRAY)
        scaled_gray = cv2.resize(gray, (w * 5, mid_crop.shape[0] * 5), interpolation=cv2.INTER_CUBIC)
        _, gray_thresh = cv2.threshold(scaled_gray, 160, 255, cv2.THRESH_BINARY)
        for test_img in [gray_thresh, cv2.bitwise_not(gray_thresh)]:
            fallback_text = pytesseract.image_to_string(test_img, config=custom_config).strip()
            fallback_text = " ".join(fallback_text.split())
            if fallback_text and re.search(r"\b(fire\s*team|fireteam|fire|team|as+lt|assault|litter|paralyzed|casualty)\b", fallback_text, re.IGNORECASE):
                print(f"  [DEBUG - Middle OCR Fallback] Text: '{fallback_text}'", flush=True)
                return fallback_text

        return ""
    except Exception as exc:
        print(f"  [DEBUG - Middle OCR Error] Exception: {exc}", flush=True)
        return ""


def extract_bottom_side_letters(img_bgr: np.ndarray) -> tuple[str, str]:
    """Extract left (VOF) and right (Range) ratings on bottom strip (e.g., 'A/S' left, 'C' right)."""
    h, w, _ = img_bgr.shape
    bottom_y1, bottom_y2 = int(h * 0.70), int(h * 0.98)

    left_crop = img_bgr[bottom_y1:bottom_y2, 0:int(w * 0.40)]
    right_crop = img_bgr[bottom_y1:bottom_y2, int(w * 0.65):int(w * 0.98)]

    left_char, right_char = "", ""

    # Left Side: VOF rating (early exit on match)
    try:
        left_gray = cv2.cvtColor(left_crop, cv2.COLOR_BGR2GRAY)
        left_scaled = cv2.resize(left_gray, (0, 0), fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        _, left_thresh = cv2.threshold(left_scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        for thresh in [left_thresh, cv2.bitwise_not(left_thresh)]:
            for psm in [7, 10]:
                cfg = f"--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-!"
                res = pytesseract.image_to_string(thresh, config=cfg).strip()
                norm = res.replace("6!", "G!").replace(" ", "")
                clean = re.sub(r"[^A-Z!/]", "", norm)
                # Check for composite basic + special superscript e.g. SG!, SF!, SD!, AG!
                if re.search(r"^(A/S|[ASH])([GFDS]!)$", clean):
                    left_char = clean
                    break
                if "/" in clean:
                    left_char = clean
                    break
                if clean in {"A", "S", "H", "G", "F", "E", "C", "A!", "S!", "G!", "F!", "D!"}:
                    left_char = clean
                    break
                if clean and clean[-1] in {"A", "S", "H", "G", "F", "E", "C"}:
                    left_char = clean[-1]
                    break
            if left_char:
                break
    except Exception as exc:
        print(f"  [DEBUG - Left Side OCR Error] Exception: {exc}", flush=True)

    # Right Side: Range band (early exit on match)
    try:
        right_gray = cv2.cvtColor(right_crop, cv2.COLOR_BGR2GRAY)
        right_scaled = cv2.resize(right_gray, (0, 0), fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        _, right_thresh = cv2.threshold(right_scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        for thresh in [right_thresh, cv2.bitwise_not(right_thresh)]:
            for psm in [10, 7]:
                cfg = f"--psm {psm} -c tessedit_char_whitelist=PCLVE!-"
                res = pytesseract.image_to_string(thresh, config=cfg).strip()
                clean = re.sub(r"[^A-Z-]", "", res.upper())
                if clean in {"CL", "C_L"}:
                    clean = "C-L"
                elif clean in {"CV", "C_V"}:
                    clean = "C-V"
                if "P" in clean and clean in {"P", "PL"}:
                    right_char = "P"
                    break
                if clean in RANGE_BAND_ENUM:
                    right_char = clean
                    break
            if right_char:
                break
    except Exception as exc:
        print(f"  [DEBUG - Right Side OCR Error] Exception: {exc}", flush=True)

    print(f"  [DEBUG - Bottom Side OCR] Left Rating (VOF): '{left_char}' | Right Rating (Range): '{right_char}'", flush=True)
    return left_char, right_char


def detect_yellow_steps(img_bgr: np.ndarray) -> int:
    """Cropping bottom 28% region and counting yellow step dots using HSV color masking."""
    h, w, _ = img_bgr.shape
    crop_start = int(h * 0.72)
    bottom_crop = img_bgr[crop_start:h, 0:w]
    hsv = cv2.cvtColor(bottom_crop, cv2.COLOR_BGR2HSV)

    lower_yellow = np.array([18, 140, 140])
    upper_yellow = np.array([32, 255, 255])
    mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_dots = [c for c in contours if cv2.contourArea(c) >= 2]

    print(f"  [DEBUG - Yellow Step Detection] Contours Found: {len(contours)} | Valid Dots: {len(valid_dots)}", flush=True)
    return len(valid_dots)


def detect_vof_red(img_bgr: np.ndarray) -> bool:
    """Check if the counter is predominantly red (used for VOF markers, NOT red bottom strips)."""
    h, w, _ = img_bgr.shape
    # Check top 60% of the counter to avoid false positives on Chinese red bottom strips
    top_crop = img_bgr[0:int(h * 0.60), 0:w]
    hsv = cv2.cvtColor(top_crop, cv2.COLOR_BGR2HSV)

    mask1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
    mask2 = cv2.inRange(hsv, np.array([160, 100, 100]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(mask1, mask2)

    total_pixels = top_crop.shape[0] * top_crop.shape[1]
    red_pixels = cv2.countNonZero(red_mask)
    ratio = float(red_pixels) / total_pixels
    is_red = ratio > 0.45  # Require >45% red in top crop

    print(f"  [DEBUG - VOF Red Detection] Top Red Ratio: {ratio:.4f} | Is Red Marker: {is_red}", flush=True)
    return is_red


def detect_tripod_mount_arrow(img_bgr: np.ndarray) -> bool:
    """Detect the yellow tripod mount symbol (arrow with crossbars) above the left VOF rating."""
    h, w, _ = img_bgr.shape

    # Region above left VOF letter: 55% to 70% height, 0 to 45% width (avoid step dots at bottom 72%+)
    crop_y1, crop_y2 = int(h * 0.55), int(h * 0.70)
    crop_x1, crop_x2 = 0, int(w * 0.45)
    roi = img_bgr[crop_y1:crop_y2, crop_x1:crop_x2]

    # Convert ROI to HSV and mask yellow pixels
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([15, 120, 120])
    upper_yellow = np.array([35, 255, 255])
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

    # Find contours in the mask
    contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for c in contours:
        area = cv2.contourArea(c)
        if area < 15:  # Skip tiny noise
            continue

        bx, by, bw, bh = cv2.boundingRect(c)
        aspect_ratio = float(bw) / float(bh) if bh > 0 else 0
        extent = float(area) / float(bw * bh) if bw * bh > 0 else 0

        # Solidity: area / convex hull area. Solid bands/dots ≈ 1.0.
        # Tripod arrow ->++ with crossbar gaps has lower solidity because the
        # convex hull fills the empty space between crossbars.
        hull = cv2.convexHull(c)
        hull_area = cv2.contourArea(hull)
        solidity = float(area) / float(hull_area) if hull_area > 0 else 1.0

        # Tripod arrows are clearly wide horizontal markers (aspect > 2.0, width ≥ 20, short height ≤ 15)
        # with substantial fill (extent ≥ 0.68) and moderate-to-low solidity (< 0.92) due to crossbar gaps.
        # Step dots / solid bands are solid circles/rectangles (solidity ~0.95+, aspect ~1.0).
        # Partial artwork blobs have low extent (< 0.68).
        if aspect_ratio >= 2.0 and bw >= 20 and bh <= 15 and extent >= 0.68 and solidity < 0.92:
            print(f"  [DEBUG - Tripod Detection] FOUND! Arrow bbox: ({bw}x{bh}), Aspect Ratio: {aspect_ratio:.2f}, Extent: {extent:.2f}, Solidity: {solidity:.2f}", flush=True)
            return True

    print("  [DEBUG - Tripod Detection] No tripod arrow detected.", flush=True)
    return False


def extract_cover_modifiers(img_bgr: np.ndarray, stem: str) -> tuple[int | None, int | None, bool]:
    """Extract cover or status modifier (-2, +1, +5), secondary bracketed rating, and NO FIRE flag."""
    h, w, _ = img_bgr.shape

    # Check for yellow "NO FIRE" badge on right side
    roi_right = img_bgr[int(h * 0.15):int(h * 0.85), int(w * 0.65):w]
    hsv_right = cv2.cvtColor(roi_right, cv2.COLOR_BGR2HSV)
    yellow_mask = cv2.inRange(hsv_right, np.array([15, 120, 120]), np.array([35, 255, 255]))
    has_no_fire = "no fire" in stem.lower() or cv2.countNonZero(yellow_mask) > 150

    # Parse primary modifier from filename or stem (supports both +N and -N, e.g. -2 for Exposed)
    mod_match = re.search(r"([+-]?\d+)", stem)
    primary_mod = int(mod_match.group(1)) if mod_match else None

    # Parse secondary rating if present in stem or brackets
    sec_match = re.search(r"\[(\d+)\]|\((\d+)\)", stem)
    secondary_mod = int(sec_match.group(1) or sec_match.group(2)) if sec_match else None

    return primary_mod, secondary_mod, has_no_fire


def detect_lat_subtype(img_bgr: np.ndarray, stem: str, ocr_middle: str) -> tuple[str, str | None]:
    """Identify LAT category and specific subtype (casualty, litter, paralyzed, fire_team).

    Returns (subtype, lat_type) where subtype is "lat" or "unit", and lat_type is
    one of "Casualty", "Litter Team", "Paralyzed Team", "Fire Team" or None.
    """
    h, w, _ = img_bgr.shape
    roi = img_bgr[int(h * 0.18):int(h * 0.75), 0:w]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    roi_pixels = roi.shape[0] * roi.shape[1]

    combined_text = f"{stem} {ocr_middle}".lower()

    # Text-based checks first (treat '_' as word boundary)
    if re.search(r"\b(casualty|cas)\b", combined_text):
        print("  [DEBUG - LAT Detection] Text Match: CASUALTY", flush=True)
        return "casualty", None
    if re.search(r"\blitter\b", combined_text):
        print("  [DEBUG - LAT Detection] Text Match: LITTER TEAM", flush=True)
        return "lat", "Litter Team"
    if re.search(r"\b(paralyzed|paralysed)\b", combined_text):
        print("  [DEBUG - LAT Detection] Text Match: PARALYZED TEAM", flush=True)
        return "lat", "Paralyzed Team"
    if "fire team" in combined_text or re.search(r"\bfire\s*team\b", combined_text):
        print("  [DEBUG - LAT Detection] Text Match: FIRE TEAM", flush=True)
        return "lat", "Fire Team"
    if re.search(r"(?:^|[_\s])(as+lt|assault)(?:\s*team)?(?:[_\s]|$)", combined_text) and not re.search(r"\b(squad|sqd)\b", combined_text):
        print("  [DEBUG - LAT Detection] Text Match: ASSAULT TEAM", flush=True)
        return "lat", "Assault Team"

    # 1. Red Cross Detection (Casualty) - check red pixels only if not already an assault/fire team
    mask_red1 = cv2.inRange(hsv, np.array([0, 120, 100]), np.array([10, 255, 255]))
    mask_red2 = cv2.inRange(hsv, np.array([165, 120, 100]), np.array([180, 255, 255]))
    # Only flag as casualty if there's a strong red cross presence and white background circle/square
    red_mask = cv2.bitwise_or(mask_red1, mask_red2)
    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    has_cross_shape = False
    for c in contours:
        area = cv2.contourArea(c)
        if area > 25:
            bx, by, bw, bh = cv2.boundingRect(c)
            # A cross has roughly square bounding box (aspect 0.7 - 1.4) and low fill (<0.65)
            aspect = float(bw) / float(bh) if bh > 0 else 0
            fill = float(area) / float(bw * bh) if bw * bh > 0 else 0
            if 0.65 <= aspect <= 1.45 and 0.25 <= fill <= 0.65:
                has_cross_shape = True
                break

    if has_cross_shape and cv2.countNonZero(red_mask) > (roi_pixels * 0.08):
        print("  [DEBUG - LAT Detection] Visual Match: CASUALTY (Red Cross Shape)", flush=True)
        return "casualty", None

    return "unit", None


def detect_country_by_color(img_bgr: np.ndarray) -> str:
    """Sample top and bottom halves of counter background to determine country color scheme."""
    h, w, _ = img_bgr.shape
    top_sample = img_bgr[int(h * 0.05):int(h * 0.25), int(w * 0.1):int(w * 0.9)]
    bottom_sample = img_bgr[int(h * 0.75):int(h * 0.95), int(w * 0.1):int(w * 0.9)]

    hsv_top = cv2.cvtColor(top_sample, cv2.COLOR_BGR2HSV)
    hsv_bottom = cv2.cvtColor(bottom_sample, cv2.COLOR_BGR2HSV)

    avg_h_top, avg_s_top, avg_v_top = np.mean(hsv_top, axis=(0, 1))
    avg_h_bot, avg_s_bot, avg_v_bot = np.mean(hsv_bottom, axis=(0, 1))

    # NKPA: Red Top (Hue near 0/180)
    if (avg_h_top < 12 or avg_h_top > 165) and avg_s_top > 100:
        return "NKPA"

    # CCF (Chinese): Tan Top + Red Bottom
    if (avg_h_bot < 12 or avg_h_bot > 165) and avg_s_bot > 100:
        return "Chinese"

    # IJA (Japanese): Khaki Top + Dark Olive-Green Bottom
    if 20 <= avg_h_top <= 42 and avg_s_top < 110 and 45 <= avg_h_bot <= 85:
        return "Japanese"

    # German: Light Grey / Low Saturation Top
    if avg_s_top < 40 and avg_v_top > 140:
        return "German"

    # NVA / VC: Brown / Dark Orange Top
    if 10 <= avg_h_top <= 25 and avg_s_top > 80:
        return "VietCong"

    # Default US / Commonwealth (Olive Green)
    return "US"


def parse_non_squad_subtypes(ocr_header: str, ocr_middle: str, stem: str) -> tuple[str, str | None, str | None]:
    """Identify non-squad command, staff, runner, and observer counter subtypes.

    Returns (subtype, lat_subtype, weapon_type).
    """
    # Correct common OCR misreads in headers (e.g., C01S6T -> CO 1SGT, ARTYF6 -> ARTY FO)
    header_clean = ocr_header.upper().replace("C0", "CO").replace("S6T", "SGT").replace("ARTYF6", "ARTY FO").replace("F0", "FO")
    combined = f"{header_clean} {ocr_middle} {stem}".upper()

    # 1. Forward Observers / Spotters (preserve specific type as weapon_type)
    if re.search(r"\b(BN\s*MTR\s*FO|BN\s*MORTAR\s*FO)\b", combined):
        return "fo_spotter", None, "Battalion Mortar FO"
    if re.search(r"\b(MTR\s*FO|MORTAR\s*FO)\b", combined):
        return "fo_spotter", None, "Mortar FO"
    if re.search(r"\b(ARTY\s*FO|ARTILLERY\s*FO)\b", combined):
        return "fo_spotter", None, "Artillery FO"
    if re.search(r"\b(FAC|AIR\s*OBSERVER|AIR\s*SPOTTER)\b", combined):
        return "fo_spotter", None, "Air Observer"
    if re.search(r"\b(SPOTTER|OBSERVER|FO)\b", combined):
        return "fo_spotter", None, "Forward Observer"

    # 2. Command Runners
    if re.search(r"(?:^|[_\s-])(RUNNER|MSG|MESSENGER)(?:[_\s-]|$)", combined):
        return "runner", None, None

    # 3. Higher Command (Regiment / Brigade)
    if re.search(r"\b(RGT|BDE|BRIGADE|REGIMENT)\b", combined):
        return "higher_command", None, None

    # 4. Battalion HQ
    if re.search(r"\b(BN\s*HQ|BN\s*CMDR|BATTALION)\b", combined):
        return "hq_bn", None, None

    # 5. Distinct Company Command & Staff Roles
    if re.search(r"\b(CO\s*XO|XO)\b", combined):
        return "co_xo", None, None
    if re.search(r"\b(1ST\s*SGT|1SGT|1-SGT|CO\s*1SGT)\b", combined):
        return "co_1sgt", None, None
    if re.search(r"\b(CO\s*HQ|CO\s*CMDR|COMPANY\s*HQ)\b", combined):
        return "hq_co", None, None
    if re.search(r"\b(STAFF|S3|S-3)\b", combined):
        return "co_staff", None, None

    # 6. Platoon HQ
    if re.search(r"\b(PLT\s*HQ|PLATOON\s*HQ)\b", combined):
        return "hq_plt", None, None

    return "squad", None, None


# ── Record Building ──────────────────────────────────────────────────────────

def build_record(
    path: Path,
    out_dir: Path,
    schema: dict,
    confidence_threshold: float = 0.70,
) -> dict:
    filename = path.name
    print(f"\n==================================================", flush=True)
    print(f"[DEBUG] Processing Counter: {filename}", flush=True)
    print(f"==================================================", flush=True)

    fmt = path.suffix.lower().lstrip(".")
    if fmt == "jpeg":
        fmt = "jpg"

    img_bgr = cv2.imread(str(path))
    if img_bgr is None:
        raise ValueError(f"Could not load image: {path}")
    if img_bgr.shape[0] != 75 or img_bgr.shape[1] != 75:
        img_bgr = cv2.resize(img_bgr, (75, 75), interpolation=cv2.INTER_CUBIC)
    h, w, _ = img_bgr.shape

    hints = parse_filename(filename)
    stem = Path(filename).stem.lower()
    category = hints.get("category_hint", "unit")
    subtype = hints.get("subtype_hint") or hints.get("unit_type_hint", "squad")
    weapon_type = hints.get("weapon_type_hint")  # Pre-initialize weapon_type from hints
    country = hints.get("country", "US")

    # Fast-path for markers and assets: skip heavy unit OCR and CV pipelines
    if category in {"marker", "asset"}:
        ocr_header = ""
        ocr_middle = ""
        left_char, right_char = "", ""
        detected_steps = 0
        has_tripod_mount = False
        visual_subtype, visual_lat_type = "unit", None
        is_red_marker = (hints.get("marker_type_hint") == "vof")
        stem_for_cover = stem
        cover_primary_mod, cover_secondary_mod, cover_no_fire = extract_cover_modifiers(img_bgr, stem_for_cover)
    else:
        ocr_header = extract_header_ocr(img_bgr)
        ocr_middle = extract_middle_text(img_bgr, hints)
        left_char, right_char = extract_bottom_side_letters(img_bgr)
        detected_steps = detect_yellow_steps(img_bgr)
        has_tripod_mount = detect_tripod_mount_arrow(img_bgr)
        visual_country = detect_country_by_color(img_bgr)
        stem_for_cover = stem
        cover_primary_mod, cover_secondary_mod, cover_no_fire = None, None, False
        if country == "US" and visual_country != "US":
            country = visual_country
            print(f"  [DEBUG - Country Visual] Filename hints gave US, visual color suggests: {visual_country}", flush=True)

        is_red_marker = False
        visual_subtype, visual_lat_type = detect_lat_subtype(img_bgr, stem, ocr_middle)

    method = "ocr"

    if hints.get("marker_type_hint") or is_red_marker:
        category = "marker"
        subtype = hints.get("marker_type_hint", "vof" if is_red_marker else "cover")

    # Non-factional markers default to "Other" unless filename has explicit nationality prefix
    if category in {"marker", "asset"}:
        if not any(stem.startswith(prefix) for prefix in COUNTRY_PREFIX_MAP):
            country = "Other"

    platoon = hints.get("platoon")
    squad_num = hints.get("squad_number")

    if ocr_header:
        m_num = re.search(r"(\d+)\s*/\s*(\d+)", ocr_header)
        m_word = re.search(r"(\d+)\s*/\s*([A-Za-z]+)", ocr_header)

        if m_num:
            squad_num = squad_num or m_num.group(1)
            platoon = platoon or m_num.group(2)
            print(f"  [DEBUG - OCR Header Num Match] Squad: {squad_num}, Platoon: {platoon}", flush=True)
        elif m_word:
            squad_num = squad_num or m_word.group(1)
            header_word = m_word.group(2)
            print(f"  [DEBUG - OCR Header Word Match] Squad: {squad_num}, Designation Word: {header_word}", flush=True)

    # Subtype precedence using explicit OCR text
    full_ocr = f"{ocr_header} {ocr_middle}".lower()
    filename_subtype = hints.get("unit_type_hint", "squad")

    if category == "marker":
        pass
    # LAT / Fire Team Detection
    elif re.search(r"\b(fire\s*team|fireteam)\b", full_ocr) or (hints.get("side") in {"back", "reduced"} and re.search(r"\b(fire|team)\b", full_ocr)):
        subtype = "lat"
        lat_type = "Fire Team"
        weapon_type = None
    # Casualty is its own subtype, not a LAT - visual detection takes precedence
    elif visual_subtype == "casualty":
        subtype = "casualty"
        lat_type = None
        weapon_type = None
    elif filename_subtype in ("co_xo", "co_1sgt", "co_staff", "hq_co", "fo_spotter", "runner", "higher_command", "hq_bn", "hq_plt") and hints.get("side") not in {"back", "reduced"}:
        ns_subtype, _, ns_weapon_type = parse_non_squad_subtypes(ocr_header, ocr_middle, filename)
        subtype = ns_subtype if ns_subtype != "squad" else filename_subtype
        weapon_type = ns_weapon_type if ns_weapon_type else hints.get("weapon_type_hint")
    elif filename_subtype == "lat":
        subtype = "lat"
        # OCR-based lat_type determination as secondary check
        if re.search(r"\bparalyzed\b", full_ocr):
            lat_type = "Paralyzed Team"
        elif re.search(r"\blitter\b", full_ocr):
            lat_type = "Litter Team"
        elif re.search(r"\b(fire\s*team|fire|team|aslt|assault)\b", full_ocr):
            lat_type = "Fire Team"
        elif visual_lat_type:
            lat_type = visual_lat_type
        else:
            lat_type = hints.get("lat_subtype")
        weapon_type = None
    elif visual_subtype == "lat" and hints.get("side") in {"back", "reduced"}:
        subtype = "lat"
        lat_type = visual_lat_type or hints.get("lat_subtype") or "Fire Team"
        weapon_type = None  # Clear heavy weapon defaults for LATs
    elif filename_subtype == "squad":
        subtype = "squad"
        weapon_type = None
    # Non-squad command/staff/runner/observer detection (takes precedence over weapons team)
    elif filename_subtype in (None, "weapons_team"):
        ns_subtype, _, ns_weapon_type = parse_non_squad_subtypes(ocr_header, ocr_middle, filename)
        if ns_subtype != "squad":
            subtype = ns_subtype
            weapon_type = ns_weapon_type if ns_weapon_type else None
    elif "mtr" in full_ocr or "mortar" in full_ocr:
        subtype = "weapons_team"
        weapon_type = "Mortar"
    elif re.search(r"\bhm[g6b]\b", full_ocr):
        subtype = "weapons_team"
        weapon_type = "Heavy Machine Gun"
    elif re.search(r"\b(lm[g6b]|mm[g6b]|m[g6])\b", full_ocr):
        subtype = "weapons_team"
        weapon_type = "Machine Gun"
    elif "engineer" in full_ocr or "eng" in full_ocr:
        subtype = "weapons_team"
        weapon_type = "Engineers"

    # Compound rating sanitization (e.g. AJS -> A/S)
    if left_char == "AJS":
        left_char = "A/S"

    special_vof = None
    if left_char:
        # Check for composite basic + special superscript e.g. SG!, SF!, SD!, AG!, A/SG!
        m_comp = re.search(r"^(A/S|[ASH])([GFDS]!)$", left_char)
        if m_comp:
            vof_rating = m_comp.group(1)
            special_vof = m_comp.group(2)
        else:
            # Clean VOF ratings like "1A" -> "A" (OCR picks up step dot edge as leading digit)
            if len(left_char) > 1 and left_char[-1] in {"A", "S", "H", "G", "F", "E"}:
                left_char = left_char[-1]
            vof_rating = left_char
    else:
        vof_rating = None

    if subtype in ("casualty", "fo_spotter"):
        vof_rating = None
        special_vof = None

    # Suppress VOF rating on non-combat markers (e.g. Unspotted, Cover, Pin, Exposed)
    if category == "marker" and subtype in {"cover", "unspotted", "unaware", "pin", "exposed"}:
        vof_rating = None
        special_vof = None

    # Sanitize known range letter OCR artifacts
    if right_char:
        clean_rc = re.sub(r"[^PCGLV-]", "", right_char.upper())
        if clean_rc in {"CL", "C_L"}:
            clean_rc = "C-L"
        elif clean_rc in {"CV", "C_V"}:
            clean_rc = "C-V"
        if clean_rc in RANGE_BAND_ENUM:
            right_char = clean_rc
        elif any(c in RANGE_BAND_ENUM for c in clean_rc):
            for c in reversed(clean_rc):
                if c in RANGE_BAND_ENUM:
                    right_char = c
                    break
        else:
            right_char = ""

    # Range band: one of P, C, L, V, C-L, C-V
    range_band = None if subtype in ("casualty", "fo_spotter", "potential_contact", "tactical_control", "visibility", "asset") else (right_char if right_char in RANGE_BAND_ENUM else None)

    # Experience level: do NOT map from bottom-right range band!
    experience_level = None
    if subtype == "higher_command":
        experience_level = "Line"
    elif category == "unit" and subtype not in ("casualty", "fo_spotter", "lat"):
        combined_text = f"{ocr_header} {ocr_middle} {stem}".lower()
        if re.search(r"\b(veteran|vet)\b", combined_text):
            experience_level = "Veteran"
        elif re.search(r"\bgreen\b", combined_text):
            experience_level = "Green"
        elif re.search(r"\belite\b", combined_text):
            experience_level = "Elite"
        elif re.search(r"\bline\b", combined_text):
            experience_level = "Line"
        elif subtype == "squad":
            experience_level = "Line"

    # Fallback weapon type detection if not already defined
    if subtype != "lat" and not weapon_type:
        text = (ocr_header + " " + ocr_middle + " " + filename).lower()
        if re.search(r"(?<![a-z0-9])hm[g6b](?![a-z0-9])", text):
            weapon_type = "Heavy Machine Gun"
        elif re.search(r"(?<![a-z0-9])lm[g6b](?![a-z0-9])|(?<![a-z0-9])mm[g6b](?![a-z0-9])|(?<![a-z0-9])m[g6](?![a-z0-9])|machine gun", text):
            weapon_type = "Machine Gun"
        elif re.search(r"bazooka|rpg|recoilless|rocket", text):
            weapon_type = "Bazooka"
        elif re.search(r"\bmtr\b|\bmortar\b|60mm|81mm|4\.2|82mm|120mm", text):
            weapon_type = "Mortar"
        elif re.search(r"88mm|75mm|76mm|57mm|\batg\b|anti.?tank", text):
            weapon_type = "Anti-Tank Gun"
        elif re.search(r"\bengineer\b|engineers|\bengr\b|\beng\b|\bsapper\b", text):
            weapon_type = "Engineers"
        elif re.search(r"flame|flamethrower|\bft\b", text):
            weapon_type = "Flame Thrower"
        elif re.search(r"\bweapons\b|\bwpns\b", text):
            weapon_type = "Weapon"

    unit_details = None
    if category == "unit":
        valid_unit_types = {
            "squad", "hq_bn", "hq_co", "hq_plt", "fo_spotter", "weapons_team",
            "vehicle", "aircraft", "lat", "casualty", "runner", "co_staff",
            "co_xo", "co_1sgt", "higher_command"
        }

        # Casualty LAT: steps = detected yellow step dots (casualty count at that location)
        if subtype == "lat" and lat_type == "Casualty":
            steps_count = detected_steps if detected_steps > 0 else 1
            default_steps = steps_count
        elif subtype in {"hq_bn", "hq_co", "hq_plt", "fo_spotter", "lat", "casualty",
                        "co_staff", "co_xo", "co_1sgt", "higher_command", "runner", "weapons_team"}:
            default_steps = 1
        else:
            default_steps = 2

        steps_total = hints.get("steps_total") or (detected_steps if detected_steps > 0 else default_steps)

        unit_details = {
            "unit_type": subtype if subtype in valid_unit_types else "squad",
            "division": None,
            "battalion": None,
            "platoon": platoon,
            "squad_number": squad_num,
            "experience_level": experience_level,
            "steps_total": min(steps_total, 3),
            "steps_remaining": min(detected_steps if detected_steps > 0 else steps_total, 3),
            "vof_rating": vof_rating,
            "special_vof": special_vof,
            "range_band": range_band,
            "weapon_type": weapon_type,
            "mount_type": "Tripod" if has_tripod_mount and subtype == "weapons_team" else None,
            "lat_subtype": lat_type if subtype == "lat" else None,
            "ammo_type": None,
            "ammo_amount": None,
        }

    marker_details = None
    if category == "marker":
        valid_marker_types = {
            "vof", "pdf", "concentrated_fire", "crossfire", "exposed", "pin",
            "tactical_control", "cover", "ammo", "potential_contact", "current_activity",
            "visibility", "unaware", "unspotted", "fire_mission"
        }
        cover_type = hints.get("cover_type_hint", "standard")
        if hints.get("marker_type_hint") == "potential_contact":
            pc_id = hints.get("pc_id", "A")
            marker_details = {
                "marker_type": "potential_contact",
                "ammo_type": None,
                "ammo_index": None,
                "is_fire_mission": False,
                "cover_type": None,
                "cover_modifier": None,
                "secondary_modifier": None,
                "no_fire": False,
                "no_pdf": False,
                "vof_level": None,
                "effects": f"Potential Contact {pc_id}",
            }
        elif hints.get("marker_type_hint") == "tactical_control":
            marker_details = {
                "marker_type": "tactical_control",
                "ammo_type": None,
                "ammo_index": None,
                "is_fire_mission": False,
                "cover_type": None,
                "cover_modifier": None,
                "secondary_modifier": None,
                "no_fire": False,
                "no_pdf": False,
                "vof_level": None,
                "effects": stem.replace("_", " ").title(),
            }
        elif hints.get("marker_type_hint") == "visibility":
            marker_details = {
                "marker_type": "visibility",
                "ammo_type": None,
                "ammo_index": None,
                "is_fire_mission": False,
                "cover_type": None,
                "cover_modifier": None,
                "secondary_modifier": None,
                "no_fire": False,
                "no_pdf": False,
                "vof_level": None,
                "effects": "Smoke / WP Visibility",
            }
        elif hints.get("ammo_type_hint"):
            ammo_type = hints.get("ammo_type_hint")
            ammo_idx = hints.get("ammo_index")
            is_fm = hints.get("is_fire_mission", False)
            marker_details = {
                "marker_type": "fire_mission" if is_fm else "ammo",
                "ammo_type": ammo_type,
                "ammo_index": ammo_idx,
                "is_fire_mission": is_fm,
                "cover_type": None,
                "cover_modifier": None,
                "secondary_modifier": None,
                "no_fire": False,
                "no_pdf": False,
                "vof_level": None,
                "effects": f"{ammo_type} #{ammo_idx}" if ammo_idx else ammo_type,
            }
        elif subtype in {"exposed", "pin"}:
            cov_mod = -2 if subtype == "exposed" else cover_primary_mod
            marker_details = {
                "marker_type": subtype,
                "ammo_type": None,
                "ammo_index": None,
                "is_fire_mission": False,
                "cover_type": None,
                "cover_modifier": cov_mod,
                "secondary_modifier": None,
                "no_fire": False,
                "no_pdf": False,
                "vof_level": None,
                "effects": f"{subtype.title()} -2" if subtype == "exposed" else (f"{subtype.title()} {cov_mod}" if cov_mod is not None else subtype.title()),
            }
        elif subtype == "current_activity":
            clean_activity = re.sub(r"^activity[_\s]*", "", stem).strip().title()
            marker_details = {
                "marker_type": "current_activity",
                "ammo_type": None,
                "ammo_index": None,
                "is_fire_mission": False,
                "cover_type": None,
                "cover_modifier": None,
                "secondary_modifier": None,
                "no_fire": False,
                "no_pdf": False,
                "vof_level": None,
                "effects": f"Activity: {clean_activity}",
            }
        else:
            marker_details = {
                "marker_type": subtype if subtype in valid_marker_types else "cover",
                "ammo_type": None,
                "ammo_index": None,
                "is_fire_mission": False,
                "cover_type": cover_type,
                "cover_modifier": cover_primary_mod,
                "secondary_modifier": cover_secondary_mod,
                "no_fire": cover_no_fire,
                "no_pdf": "no pdf" in stem_for_cover.lower() or "unaware" in stem_for_cover.lower(),
                "vof_level": "S" if is_red_marker else None,
                "effects": f"Cover {cover_primary_mod:+d}" if cover_primary_mod is not None else None,
            }

    valid_sides = {"front", "back", "broken", "reduced", "alternate", "unknown"}
    raw_side = hints.get("side", "front")
    side = raw_side if raw_side in valid_sides else "front"

    # Specific ID generation for Company & Command Roles
    clean_stem_slug = re.sub(r"[^a-zA-Z0-9]+", "-", Path(filename).stem).strip("-").upper()
    if category == "marker":
        if hints.get("marker_type_hint") == "potential_contact":
            counter_id = f"MARKER-PC-{hints.get('pc_id', 'A')}"
        elif hints.get("marker_type_hint") == "tactical_control":
            counter_id = f"MARKER-CONTROL-{clean_stem_slug.replace('CONTROL-', '')}"
        elif hints.get("marker_type_hint") == "visibility":
            counter_id = f"MARKER-VISIBILITY-{clean_stem_slug}"
        elif hints.get("ammo_type_hint"):
            ammo_type = hints.get("ammo_type_hint")
            ammo_idx = hints.get("ammo_index")
            clean_type = (ammo_type or "AMMO").replace(" ", "-").replace(".", "").upper()
            counter_id = f"MARKER-{clean_type}-{ammo_idx}" if ammo_idx else f"MARKER-{clean_type}"
        elif subtype in {"exposed", "pin"}:
            counter_id = f"MARKER-{subtype.upper()}"
        elif hints.get("marker_type_hint") == "current_activity" or subtype == "current_activity":
            counter_id = f"MARKER-ACTIVITY-{clean_stem_slug.replace('ACTIVITY-', '')}"
        else:
            marker_name = hints.get("cover_type_hint") or subtype
            counter_id = f"MARKER-{marker_name.upper().replace(' ', '_')}"
    elif category == "asset":
        counter_id = f"ASSET-{clean_stem_slug}"
    elif subtype == "hq_co":
        counter_id = f"{country}-CO-HQ"
    elif subtype == "co_xo":
        counter_id = f"{country}-CO-XO"
    elif subtype == "co_1sgt":
        counter_id = f"{country}-CO-1SGT"
    elif subtype == "hq_bn":
        counter_id = f"{country}-BN-HQ"
    elif subtype == "co_staff":
        counter_id = f"{country}-CO-STAFF"
    elif subtype == "higher_command":
        counter_id = f"{country}-HIGHER-CMD"
    elif subtype == "runner":
        counter_id = f"{country}-{squad_num or '1'}-RUNNER"
    elif subtype == "fo_spotter":
        if weapon_type == "Artillery FO":
            counter_id = f"{country}-ARTY-FO"
        elif weapon_type == "Battalion Mortar FO":
            counter_id = f"{country}-BN-MTR-FO"
        elif weapon_type == "Mortar FO":
            counter_id = f"{country}-MTR-FO"
        elif weapon_type == "Air Observer":
            counter_id = f"{country}-FAC"
        else:
            counter_id = f"{country}-FO-SPOTTER"
    elif subtype == "lat" and lat_type in {"Fire Team", "Assault Team"}:
        suffix = "AT" if lat_type == "Assault Team" else "FT"
        if "xo" in stem:
            counter_id = f"{country}-CO-XO-{suffix}"
        elif "1sgt" in stem:
            counter_id = f"{country}-CO-1SGT-{suffix}"
        elif "co" in stem:
            counter_id = f"{country}-CO-HQ-{suffix}"
        elif squad_num and platoon:
            counter_id = f"{country}-{squad_num}-{platoon}-{suffix}"
        elif squad_num:
            clean_role = re.sub(r"[^A-Z0-9]+", "-", stem.upper()).replace("CCF-", "").replace("-B", "")
            counter_id = f"{country}-{clean_role}-FT"
        else:
            counter_id = f"{country}-{clean_stem_slug}"
    elif subtype == "vehicle":
        veh_match = re.search(r"(\d+)", stem)
        num_str = squad_num or (veh_match.group(1) if veh_match else "1")
        counter_id = f"{country}-VEHICLE-{num_str}"
    elif squad_num and platoon:
        counter_id = f"{country}-{squad_num}-{platoon}-{subtype.upper()}"
    elif squad_num:
        clean_role = re.sub(r"[^A-Z0-9]+", "-", stem.upper()).replace(f"{country.upper()}-", "").replace("-B", "")
        counter_id = f"{country}-{clean_role}-{subtype.upper()}"
    else:
        counter_id = f"{country}-{clean_stem_slug}"

    print(f"  [DEBUG - Final Schema Output] ID: '{counter_id}' | Subtype: '{subtype}' | VOF (Left): '{vof_rating}' | Range (Right): '{range_band}'", flush=True)

    # Dynamic Confidence Calculation
    confidence = 0.90
    if category == "unit":
        if squad_num is None and platoon is None and subtype not in {"vehicle", "aircraft", "casualty"}:
            confidence -= 0.15
        if vof_rating is None and range_band is None and subtype not in {"casualty", "fo_spotter"}:
            confidence -= 0.10
    elif category == "marker":
        if subtype == "cover" and cover_primary_mod is None:
            confidence -= 0.15
    if not ocr_header and not ocr_middle:
        confidence -= 0.05
    confidence = max(0.20, min(0.95, confidence))

    potential_contact_obj = None
    if subtype == "potential_contact" or hints.get("marker_type_hint") == "potential_contact":
        potential_contact_obj = {
            "id": hints.get("pc_id"),
            "weather": None,
            "type": None,
            "amount": None,
        }

    assets_obj = {"type": None, "amount": None}
    if category == "asset":
        assets_obj = {
            "type": hints.get("asset_type", "Asset"),
            "amount": 1,
        }

    record = {
        "id": counter_id,
        "path": str(path),
        "source": "fof-images-folder",
        "image": {
            "filename": filename,
            "width": w,
            "height": h,
            "format": fmt,
            "side": side,
            "hash_sha256": sha256_file(path),
            "classified_at": datetime.now(timezone.utc).isoformat(),
            "classifier": "fof-counter-pipeline v3.8-middle-ocr",
            "confidence": round(confidence, 3),
        },
        "country": country if country in {"US", "German", "NKPA", "Australian", "Commonwealth", "VietCong", "NVA", "ARVN", "Chinese", "Japanese", "Other"} else "Unknown",
        "category": category,
        "subtype": subtype,
        "unit_details": unit_details,
        "marker_details": marker_details,
        "status": {
            "exposed": None,
            "pinned": None,
            "cover": None,
            "ammo_state": None,
        },
        "assets": assets_obj,
        "combat": {
            "vof": vof_rating if category == "unit" else None,
            "pdf": None,
            "concentrated_fire": None,
            "crossfire": None,
        },
        "potential_contact": potential_contact_obj,
        "classification": {
            "method": method,
            "model": "tesseract-whitelist + opencv-hsv",
            "labels": [
                f"header_ocr:{ocr_header}",
                f"middle_ocr:{ocr_middle}",
                f"yellow_dots:{detected_steps}",
                f"bottom_left_vof:{left_char}",
                f"bottom_right_range:{right_char}"
            ],
            "reviewed": False,
            "reviewer": None,
            "reviewed_at": None,
            "notes": f"Header OCR: '{ocr_header}', Middle OCR: '{ocr_middle}', Yellow Dots: {detected_steps}, VOF (Left): {left_char}, Range (Right): {right_char}",
        },
    }
    return record


# ── Main Entrypoint ──────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Classify Fields of Fire counter images against fof-counter.v1.json schema.")
    ap.add_argument("--images", type=Path, default=IMAGES_DIR_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--schema", type=Path, default=SCHEMA_PATH_DEFAULT)
    ap.add_argument("--review-queue", type=Path, default=REVIEW_QUEUE_DEFAULT)
    ap.add_argument("--confidence", type=float, default=0.70)
    args = ap.parse_args()

    if not args.images.is_dir():
        print(f"ERROR: images dir not found: {args.images}", file=sys.stderr)
        return 1

    schema = json.loads(args.schema.read_text(encoding="utf-8"))

    images = sorted(
        p for p in args.images.iterdir()
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )
    print(f"Found {len(images)} images in {args.images}", flush=True)

    filtered_images = []
    for p in images:
        try:
            with Image.open(p) as im:
                w, h = im.size
                if 70 <= w <= 80 and 70 <= h <= 80:
                    filtered_images.append(p)
                else:
                    print(f"SKIPPING {p.name}: size {im.size} (not ~75x75)", flush=True)
        except Exception as e:
            print(f"SKIPPING {p.name}: cannot open ({e})", flush=True)
    images = filtered_images
    print(f"Processing {len(images)} images of size ~75x75", flush=True)

    records = []
    review = []
    for idx, img_path in enumerate(images, 1):
        try:
            rec = build_record(
                img_path,
                args.out,
                schema,
                confidence_threshold=args.confidence,
            )
            jsonschema.validate(instance=rec, schema=schema)
            records.append(rec)
            if rec["image"]["confidence"] < args.confidence:
                review.append(rec)
            print(f"[{idx}/{len(images)}] OK {img_path.name} -> {rec['category']}/{rec['subtype']} (conf={rec['image']['confidence']})", flush=True)
        except Exception as exc:
            print(f"ERROR processing {img_path.name}: {exc}", file=sys.stderr, flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} records to {args.out.resolve()}", flush=True)

    sidecar_dir = args.out.with_suffix(args.out.suffix + ".sidecars")
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    for rec in records:
        side = sidecar_dir / (Path(rec["image"]["filename"]).stem + ".json")
        side.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} sidecar JSONs to {sidecar_dir.resolve()}", flush=True)

    args.review_queue.parent.mkdir(parents=True, exist_ok=True)
    with args.review_queue.open("w", encoding="utf-8") as fh:
        for rec in review:
            fh.write(json.dumps(rec) + "\n")
    print(f"Wrote {len(review)} low-confidence records to {args.review_queue.resolve()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())