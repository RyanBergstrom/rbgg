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
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except ImportError as exc:
    raise SystemExit("pytesseract is required: pip install pytesseract") from exc

SCHEMA_PATH_DEFAULT = Path("documentation/fof/counter-schema.json")
IMAGES_DIR_DEFAULT = Path("documentation/fof/images")
OUT_DEFAULT = Path("documentation/fof/counters.json")
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

# Valid range band enum values per FoF rules
RANGE_BAND_ENUM = {"P", "C", "L", "V"}


LAT_TYPES_ENUM = {
    "Fire Team",
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
        if pattern in stem:
            hints["country"] = hints.get("country") or country

    for suffix, side in SIDE_SUFFIX_MAP.items():
        if stem.endswith(" " + suffix) or stem.endswith("_" + suffix):
            hints["side"] = side
            break

    m = re.match(r"^[a-z]*([-_]?\d+)[-_]?(\d+)", stem)
    if m:
        hints["squad_number"] = m.group(1).strip("-_")
        hints["platoon"] = m.group(2).strip("-_")
    else:
        m_single = re.match(r"^(\d+)[-_ ]", stem)
        if m_single:
            hints["squad_number"] = m_single.group(1)

    m = re.search(r"(\d+)\s*step", stem)
    if m:
        hints["steps_total"] = int(m.group(1))

    # Unit Types Mapping (A - J) with Fire Team / LAT precedence
    # Use (?:^|[_\s])...(?:[_\s]|$) so '_' is treated as a word boundary too
    if re.search(r"(?:^|[_\s])(lat|litter|assault team|fire team|aslt|paralyzed)(?:[_\s]|$)", stem):
        hints["unit_type_hint"] = "lat"
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
    elif re.search(r"\b(tank|apc|vehicle|truck|aircraft|chopper|helo)\b", stem):
        hints["unit_type_hint"] = "vehicle" if not re.search(r"\b(aircraft|chopper|helo)\b", stem) else "aircraft"
    elif re.search(r"\b(bn hq|battalion hq)\b", stem):
        hints["unit_type_hint"] = "hq_bn"
    elif re.search(r"\b(plt hq|platoon hq)\b", stem):
        hints["unit_type_hint"] = "hq_plt"
    elif re.search(r"\b(hq)\b", stem):
        hints["unit_type_hint"] = "hq_plt"
    elif re.search(r"\b(sqd|squad)\b", stem):
        hints["unit_type_hint"] = "squad"

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

    if re.search(r"\b(radio|phone|wire|pyro|asset)\b", stem):
        hints["category_hint"] = "asset"
        hints["subtype_hint"] = "asset"
    elif re.search(r"\bvof\b", stem):
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "vof"
    elif re.search(r"\bpdf\b|primary direction", stem):
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "pdf"
    elif re.search(r"\bexposed\b", stem):
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "exposed"
        hints["cover_type_hint"] = "standard"
    elif re.search(r"\bpin(ned)?\b", stem):
        hints["category_hint"] = "marker"
        hints["marker_type_hint"] = "pin"
        hints["cover_type_hint"] = "standard"
    # Cover & Visibility Token Parsing - specific cover types (checked before generic cover)
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
    # Ammo & Fire Mission Token Parsing
    elif re.search(r"\b(ammo|50cal|hmg|arty\s*fm|hvy\s*mtr\s*fm|hv\s*mtr\s*fm)\b", stem):
        hints["category_hint"] = "marker"
        if "arty" in stem and "fm" in stem:
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
        # Extract sequence index number (e.g. Ammo 50cal 1.png -> 1)
        idx_match = re.search(r"(\d+)\s*(?:\.png|\.jpg)?$", stem)
        if idx_match:
            hints["ammo_index"] = int(idx_match.group(1))

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


def extract_middle_text(img_bgr: np.ndarray) -> str:
    """Crop middle region and extract text like 'Fire Team' or 'Litter Team'."""
    h, w, _ = img_bgr.shape
    mid_crop = img_bgr[int(h * 0.30):int(h * 0.68), 0:w]

    # HSV Yellow Mask adjusted for anti-aliased text over tan backgrounds
    hsv = cv2.cvtColor(mid_crop, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([10, 50, 110])
    upper_yellow = np.array([40, 255, 255])
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

    # Upscale 5x for Tesseract clarity
    scaled_mask = cv2.resize(yellow_mask, (w * 5, mid_crop.shape[0] * 5), interpolation=cv2.INTER_CUBIC)

    # Morphological dilation to reconnect thin font strokes
    kernel = np.ones((2, 2), np.uint8)
    processed = cv2.dilate(scaled_mask, kernel, iterations=1)

    custom_config = r"--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "

    try:
        raw_text = pytesseract.image_to_string(processed, config=custom_config).strip()
        clean_text = " ".join(raw_text.split())
        print(f"  [DEBUG - Middle OCR] Text: '{raw_text}' -> Cleaned: '{clean_text}'", flush=True)

        # Strict keyword filter: discard garbage OCR (e.g., tripod legs read as letters)
        if clean_text and not re.search(r"\b(fire\s*team|fire|team|aslt|assault|litter|paralyzed|casualty)\b", clean_text, re.IGNORECASE):
            print(f"  [DEBUG - Middle OCR] Discarded non-keyword noise: '{clean_text}'", flush=True)
            clean_text = ""

        # Fallback to simple upscaled grayscale if color masking yields nothing
        if len(clean_text) < 3:
            gray = cv2.cvtColor(mid_crop, cv2.COLOR_BGR2GRAY)
            scaled_gray = cv2.resize(gray, (w * 5, mid_crop.shape[0] * 5), interpolation=cv2.INTER_CUBIC)
            _, gray_thresh = cv2.threshold(scaled_gray, 160, 255, cv2.THRESH_BINARY)
            fallback_text = pytesseract.image_to_string(gray_thresh, config=custom_config).strip()
            fallback_text = " ".join(fallback_text.split())

            # Apply same keyword filter to fallback
            if fallback_text and not re.search(r"\b(fire\s*team|fire|team|aslt|assault|litter|paralyzed|casualty)\b", fallback_text, re.IGNORECASE):
                print(f"  [DEBUG - Middle OCR Fallback] Discarded non-keyword noise: '{fallback_text}'", flush=True)
                fallback_text = ""

            if len(fallback_text) >= 3:
                print(f"  [DEBUG - Middle OCR Fallback] Text: '{fallback_text}'", flush=True)
                return fallback_text

        return clean_text
    except Exception as exc:
        print(f"  [DEBUG - Middle OCR Error] Exception: {exc}", flush=True)
        return ""


def extract_bottom_side_letters(img_bgr: np.ndarray) -> tuple[str, str]:
    """Extract left (VOF) and right (Range) ratings on bottom strip (e.g., 'A/S' left, 'C' right)."""
    h, w, _ = img_bgr.shape
    bottom_y1, bottom_y2 = int(h * 0.70), int(h * 0.98)

    # Left crop widened to 40% width to capture multi-character ratings like 'A/S'
    left_crop = img_bgr[bottom_y1:bottom_y2, 0:int(w * 0.40)]
    # Right crop tightened to 65%-98% width to exclude step dot artifacts
    right_crop = img_bgr[bottom_y1:bottom_y2, int(w * 0.65):int(w * 0.98)]

    # Whitelist explicitly allowing slash '/' for compound ratings (A/S, G/S, S/S)
    config_left = r"--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-!"
    config_right = r"--psm 10 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!-"

    left_char, right_char = "", ""

    try:
        left_gray = cv2.cvtColor(left_crop, cv2.COLOR_BGR2GRAY)
        left_scaled = cv2.resize(left_gray, (0, 0), fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        _, left_thresh = cv2.threshold(left_scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        left_char = pytesseract.image_to_string(left_thresh, config=config_left).strip()
    except Exception:
        pass

    try:
        right_gray = cv2.cvtColor(right_crop, cv2.COLOR_BGR2GRAY)
        right_scaled = cv2.resize(right_gray, (0, 0), fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        _, right_thresh = cv2.threshold(right_scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        right_char = pytesseract.image_to_string(right_thresh, config=config_right).strip()

        # Clean up known single-character OCR misreadings
        if right_char == "PL":
            right_char = "L"
    except Exception:
        pass

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
    red_mask = mask1 | mask2

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
    if "casualty" in combined_text or "cas" in combined_text:
        print("  [DEBUG - LAT Detection] Text Match: CASUALTY", flush=True)
        return "casualty", None
    if "litter" in combined_text:
        print("  [DEBUG - LAT Detection] Text Match: LITTER TEAM", flush=True)
        return "lat", "Litter Team"
    if "paralyzed" in combined_text or "paralysed" in combined_text:
        print("  [DEBUG - LAT Detection] Text Match: PARALYZED TEAM", flush=True)
        return "lat", "Paralyzed Team"
    if "fire team" in combined_text or re.search(r"(?:^|[_\s])(aslt|assault)(?:[_\s]|$)", combined_text):
        print("  [DEBUG - LAT Detection] Text Match: FIRE TEAM", flush=True)
        return "lat", "Fire Team"

    # 1. Red Cross Detection (Casualty) - most distinctive visual
    mask_red1 = cv2.inRange(hsv, np.array([0, 120, 100]), np.array([10, 255, 255]))
    mask_red2 = cv2.inRange(hsv, np.array([165, 120, 100]), np.array([180, 255, 255]))
    if cv2.countNonZero(cv2.bitwise_or(mask_red1, mask_red2)) > (roi_pixels * 0.10):
        print("  [DEBUG - LAT Detection] Visual Match: CASUALTY (Red Cross)", flush=True)
        return "casualty", None

    # 2. Yellow Arrow Detection (Paralyzed)
    lower_yellow = np.array([15, 120, 120])
    upper_yellow = np.array([35, 255, 255])
    if cv2.countNonZero(cv2.inRange(hsv, lower_yellow, upper_yellow)) > (roi_pixels * 0.08):
        print("  [DEBUG - LAT Detection] Visual Match: PARALYZED (Yellow Arrow)", flush=True)
        return "lat", "Paralyzed Team"

    # 3. Stretcher Detection (Litter) - long thin contour
    lower_stretcher = np.array([35, 30, 40])
    upper_stretcher = np.array([85, 255, 200])
    stretcher_mask = cv2.inRange(hsv, lower_stretcher, upper_stretcher)
    contours, _ = cv2.findContours(stretcher_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        if cv2.contourArea(c) > 35:
            rect = cv2.minAreaRect(c)
            width, height = rect[1]
            if height > 0 and (max(width, height) / min(width, height)) > 2.0:
                print("  [DEBUG - LAT Detection] Visual Match: LITTER TEAM (Stretcher)", flush=True)
                return "lat", "Litter Team"

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
    h, w, _ = img_bgr.shape

    hints = parse_filename(filename)
    ocr_header = extract_header_ocr(img_bgr)
    ocr_middle = extract_middle_text(img_bgr)
    left_char, right_char = extract_bottom_side_letters(img_bgr)
    detected_steps = detect_yellow_steps(img_bgr)
    # Ensure Exposed, Pinned, Cover, Unaware, Unspotted markers do not get forced into VOF red markers
    if hints.get("marker_type_hint") in {"exposed", "pin", "cover", "unaware", "unspotted"}:
        is_red_marker = False
    else:
        is_red_marker = detect_vof_red(img_bgr)
    has_tripod_mount = detect_tripod_mount_arrow(img_bgr)
    visual_country = detect_country_by_color(img_bgr)
    stem_for_cover = Path(filename).stem.lower()
    cover_primary_mod, cover_secondary_mod, cover_no_fire = extract_cover_modifiers(img_bgr, stem_for_cover)
    stem = Path(filename).stem.lower()
    category = hints.get("category_hint", "unit")
    subtype = hints.get("unit_type_hint", "squad")
    weapon_type = hints.get("weapon_type_hint")  # Pre-initialize weapon_type from hints
    country = hints.get("country", "US")
    # Fallback to visual color detection when filename hints give only default US
    if country == "US" and visual_country != "US":
        country = visual_country
        print(f"  [DEBUG - Country Visual] Filename hints gave US, visual color suggests: {visual_country}", flush=True)
    confidence = 0.85
    method = "ocr"

    # Visual LAT detection should ONLY run on unit category counters, never on markers
    if category == "unit":
        visual_subtype, visual_lat_type = detect_lat_subtype(img_bgr, stem, ocr_middle)
    else:
        visual_subtype, visual_lat_type = "unit", None
    if hints.get("marker_type_hint") or is_red_marker:
        category = "marker"
        subtype = hints.get("marker_type_hint", "vof" if is_red_marker else "cover")

    # Non-factional markers default to "Other" unless filename has explicit nationality prefix
    if category == "marker":
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

    # LAT / Fire Team Detection
    filename_subtype = hints.get("unit_type_hint", "squad")

    # If Middle OCR detects "Fire Team" (e.g. back side of XO/1SGT/Squad), enforce LAT Fire Team
    if re.search(r"\b(fire\s*team|fireteam)\b", full_ocr):
        subtype = "lat"
        lat_type = "Fire Team"
        weapon_type = None
    # Casualty is its own subtype, not a LAT - visual detection takes precedence
    elif visual_subtype == "casualty":
        subtype = "casualty"
        lat_type = None
        weapon_type = None
    elif visual_subtype == "lat" and filename_subtype == "lat":
        subtype = "lat"
        lat_type = visual_lat_type
        weapon_type = None  # Clear heavy weapon defaults for LATs
    elif filename_subtype == "lat":
        # OCR-based lat_type determination as secondary check
        if re.search(r"\bparalyzed\b", full_ocr):
            lat_type = "Paralyzed Team"
        elif re.search(r"\blitter\b", full_ocr):
            lat_type = "Litter Team"
        elif re.search(r"\b(fire\s*team|fire|team|aslt|assault)\b", full_ocr):
            lat_type = "Fire Team"
        elif visual_lat_type:
            lat_type = visual_lat_type
        weapon_type = None
    # Non-squad command/staff/runner/observer detection (takes precedence over weapons team)
    elif filename_subtype in ("squad", None, "weapons_team", "co_xo", "co_1sgt", "co_staff", "hq_co", "fo_spotter"):
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

    # Clean VOF ratings like "1A" -> "A" (OCR picks up step dot edge as leading digit)
    if left_char and len(left_char) > 1 and left_char[-1] in {"A", "S", "H", "G", "F", "E"}:
        left_char = left_char[-1]

    vof_rating = None if subtype in ("casualty", "fo_spotter") else (left_char if left_char in {"S", "A", "H", "G", "F", "E", "G!", "A!", "S!"} or "G" in left_char else left_char or None)

    # Suppress VOF rating on non-combat markers (e.g. Unspotted, Cover, Pin, Exposed)
    if category == "marker" and subtype in {"cover", "unspotted", "unaware", "pin", "exposed"}:
        vof_rating = None

    # Sanitize known range letter OCR artifacts
    if right_char in {"PL", "P", "1L", "|L"}:
        right_char = "L"
    # Range band: strictly one of P, C, L, V (Point Blank, Close, Long, Very Long)
    range_band = None if subtype in ("casualty", "fo_spotter") else (right_char if right_char in RANGE_BAND_ENUM else None)

    if subtype == "higher_command":
        experience_level = "Line"
    elif subtype in ("casualty", "fo_spotter"):
        experience_level = None
    else:
        experience_level = EXPERIENCE_RATING_MAP.get(right_char, "Line" if right_char == "L" or "L" in right_char else None)

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
            "range_band": range_band,
            "weapon_type": weapon_type,
            "mount_type": "Tripod" if has_tripod_mount else None,
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
        if hints.get("ammo_type_hint"):
            ammo_type = hints.get("ammo_type_hint")
            ammo_idx = hints.get("ammo_index")
            marker_details = {
                "marker_type": hints.get("marker_type_hint", "ammo"),
                "ammo_type": ammo_type,
                "ammo_index": ammo_idx,
                "is_fire_mission": hints.get("is_fire_mission", False),
                "cover_type": None,
                "cover_modifier": None,
                "secondary_modifier": None,
                "no_fire": False,
                "no_pdf": False,
                "vof_level": None,
                "effects": f"{ammo_type} #{ammo_idx}" if ammo_idx else ammo_type,
            }
        elif subtype in {"exposed", "pin"}:
            marker_details = {
                "marker_type": subtype,
                "cover_type": None,
                "cover_modifier": cover_primary_mod if cover_primary_mod is not None else (-2 if subtype == "exposed" else None),
                "secondary_modifier": None,
                "no_fire": False,
                "no_pdf": False,
                "vof_level": None,
                "effects": f"{subtype.title()} {cover_primary_mod}" if cover_primary_mod is not None else f"{subtype.title()}",
            }
        else:
            marker_details = {
                "marker_type": subtype if subtype in valid_marker_types else "cover",
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
    # Counter ID Generation
    if category == "marker":
        if hints.get("ammo_type_hint"):
            ammo_type = hints.get("ammo_type_hint")
            ammo_idx = hints.get("ammo_index")
            clean_type = ammo_type.replace(" ", "-").replace(".", "").upper()
            counter_id = f"MARKER-{clean_type}-{ammo_idx}" if ammo_idx else f"MARKER-{clean_type}"
        elif subtype in {"exposed", "pin"}:
            counter_id = f"MARKER-{subtype.upper()}"
        else:
            marker_name = hints.get("cover_type_hint") or subtype
            counter_id = f"MARKER-{marker_name.upper().replace(' ', '_')}"
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
    elif subtype == "lat" and lat_type == "Fire Team":
        if "xo" in stem:
            counter_id = f"{country}-CO-XO-FT"
        elif "1sgt" in stem:
            counter_id = f"{country}-CO-1SGT-FT"
        elif "co" in stem:
            counter_id = f"{country}-CO-HQ-FT"
        else:
            counter_id = f"{country}-{squad_num or '1'}-{platoon or '1'}-FT"
    else:
        counter_id = f"{country}-{squad_num or '1'}-{platoon or '1'}-{subtype.upper()}"

    print(f"  [DEBUG - Final Schema Output] ID: '{counter_id}' | Subtype: '{subtype}' | VOF (Left): '{vof_rating}' | Range (Right): '{range_band}'", flush=True)

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
        "assets": {"type": None, "amount": None},
        "combat": {
            "vof": vof_rating,
            "pdf": None,
            "concentrated_fire": None,
            "crossfire": None,
        },
        "potential_contact": None,
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
            "reviewed": confidence < confidence_threshold,
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
                if im.size == (75, 75):
                    filtered_images.append(p)
                else:
                    print(f"SKIPPING {p.name}: size {im.size} (not 75x75)", flush=True)
        except Exception as e:
            print(f"SKIPPING {p.name}: cannot open ({e})", flush=True)
    images = filtered_images
    print(f"Processing {len(images)} images of size 75x75", flush=True)

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
            if rec["classification"]["reviewed"]:
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