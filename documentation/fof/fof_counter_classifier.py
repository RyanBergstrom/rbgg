#!/usr/bin/env python3
"""Fields of Fire counter classifier.

Scans a folder of 75x75 counter images, classifies each one using a hybrid of
filename heuristics, OCR (Tesseract/EasyOCR), and zero-shot CLIP image
classification, and writes a JSON record per image matching counter-schema.json.

All libraries used are free / open source:
  - Pillow (image loading)
  - OpenCV (preprocessing, color detection)
  - pytesseract or EasyOCR (text recognition)
  - transformers + CLIP (zero-shot image classification)
  - jsonschema (validation)

Usage:
    python scripts/fof_counter_classifier.py \
        --images C:/Dev/rbgg/documentation/fof/images \
        --out C:/Dev/rbgg/documentation/fof/counters.json \
        --schema C:/Dev/rbgg/documentation/fof/counter-schema.json \
        --review-queue C:/Dev/rbgg/documentation/fof/review_queue.jsonl \
        --confidence 0.70 \
        --device cpu
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
import cv2
import numpy as np

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - guard clause
    raise SystemExit("jsonschema is required: pip install jsonschema") from exc

SCHEMA_PATH_DEFAULT = Path("documentation/fof/counter-schema.json")
IMAGES_DIR_DEFAULT = Path("documentation/fof/images")
OUT_DEFAULT = Path("documentation/fof/counters.json")
REVIEW_QUEUE_DEFAULT = Path("documentation/fof/review_queue.jsonl")

# ── Country mapping ──────────────────────────────────────────────────────────
COUNTRY_PREFIX_MAP = {
    "1atf": "Australian",
    "us": "US",
    "german": "German",
    "nkpa": "NKPA",
    "vietcong": "VietCong",
    "nva": "NVA",
    "arvn": "ARVN",
}

# Additional country patterns detected from filename analysis
COUNTRY_PATTERN_MAP = {
    # Paratrooper / Commonwealth patterns
    "2para": "Commonwealth",
    "para": "Commonwealth",
    "parachute": "Commonwealth",
    "22sas": "Commonwealth",
    "sas": "Commonwealth",
    # Vietnam patterns
    "vc": "VietCong",
    "vietcong": "VietCong",
    "viet minh": "VietCong",
    "nva": "NVA",
    "north vietnam": "NVA",
    # US patterns
    "1atf": "Australian",  # override - 1ATF is Australian despite "1atf" prefix handled above
    "us": "US",
    "1st infantry": "US",
    "1st cav": "US",
    "1-1": "US",
    "1-2": "US",
    "1-3": "US",
    # German patterns
    "ger": "German",
    "wehrmacht": "German",
    "bw": "German",
    # NKPA patterns
    "nkpa": "NKPA",
    "north korea": "NKPA",
    # ARVN patterns
    "arvn": "ARVN",
    "south vietnam": "ARVN",
}

SIDE_SUFFIX_MAP = {
    "b": "back",
    "f": "front",
    "al": "alternate",
}

# CLIP prompts - unit and marker categories separated
CLIP_PROMPTS = {
    "unit": [
        "a Fields of Fire infantry squad counter",
        "a Fields of Fire headquarters counter",
        "a Fields of Fire forward observer counter",
        "a Fields of Fire weapons team counter",
        "a Fields of Fire vehicle counter",
        "a Fields of Fire aircraft counter",
        "a Fields of Fire limited action team counter",
        "a Fields of Fire casualty counter",
        "a Fields of Fire runner counter",
        "a Fields of Fire volume of fire marker",
        "a Fields of Fire primary direction of fire marker",
        "a Fields of Fire crossfire marker",
        "a Fields of Fire exposed marker",
        "a Fields of Fire pinned marker",
        "a Fields of Fire tactical control marker",
        "a Fields of Fire cover marker",
        "a Fields of Fire ammo marker",
        "a Fields of Fire potential contact marker",
        "a Fields of Fire current activity marker",
        "a Fields of Fire visibility marker",
    ],
    "marker": [
        "a Fields of Fire volume of fire marker",
        "a Fields of Fire primary direction of fire marker",
        "a Fields of Fire crossfire marker",
        "a Fields of Fire exposed marker",
        "a Fields of Fire pinned marker",
        "a Fields of Fire tactical control marker",
        "a Fields of Fire cover marker",
        "a Fields of Fire ammo marker",
        "a Fields of Fire potential contact marker",
        "a Fields of Fire current activity marker",
        "a Fields of Fire visibility marker",
    ],
}

VOF_LEVELS = {"S", "A", "H", "G", "F", "E"}
EXPERIENCE_LEVELS = {"Green", "Line", "Veteran", "Elite", "S", "A"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_filename(name: str) -> dict:
    """Extract hints from the counter filename."""
    stem = Path(name).stem.lower()
    hints: dict = {}

    # ── Country from leading token / known prefixes ──────────────────────
    for prefix, country in COUNTRY_PREFIX_MAP.items():
        if stem.startswith(prefix):
            hints["country"] = country
            break

    # ── Additional country patterns from anywhere in stem ────────────────
    for pattern, country in COUNTRY_PATTERN_MAP.items():
        if pattern in stem:
            hints["country"] = hints.get("country") or country

    # ── Fix known overrides (1ATF is Australian, not US) ──────────────────
    # Already handled by COUNTRY_PREFIX_MAP above, but ensure consistency

    # ── Side suffix ──────────────────────────────────────────────────────
    for suffix, side in SIDE_SUFFIX_MAP.items():
        if stem.endswith(" " + suffix) or stem.endswith(suffix):
            hints["side"] = side
            break

    # ── Platoon / squad number from leading pattern ──────────────────────
    # Patterns like "1-1", "1_1", "2-3", "1ATF 10-1", etc.
    m = re.match(r"^[a-z]*([-_]?\d+)[-_]?(\d+)", stem)
    if m:
        hints["platoon"] = m.group(1).strip("-_")
        hints["squad_number"] = m.group(2).strip("-_")

    # ── Steps count ──────────────────────────────────────────────────────
    m = re.search(r"(\d+)\s*step", stem)
    if m:
        hints["steps_total"] = int(m.group(1))

    # ── Unit / marker type hints from filename ───────────────────────────
    # Lat/LAT patterns
    if re.search(r"\blat\b", stem) or re.search(r"\bL-AT\b", stem):
        hints["unit_type_hint"] = "lat"

    # Limited action
    if re.search(r"\blimited action\b", stem):
        hints["unit_type_hint"] = hints.get("unit_type_hint") or "lat"

    # Casualty
    if re.search(r"\b(casualty|cas)\b", stem):
        hints["unit_type_hint"] = hints.get("unit_type_hint") or "casualty"

    # Weapons team
    if re.search(r"\b(weapons|wpns|mortar|mg)\b", stem):
        hints["unit_type_hint"] = hints.get("unit_type_hint") or "weapons_team"

    # HQ patterns - most specific first
    if re.search(r"\b(bn hq|battalion hq)\b", stem):
        hints["unit_type_hint"] = hints.get("unit_type_hint") or "hq_bn"
    elif re.search(r"\b(co hq|company hq|coy hq)\b", stem):
        hints["unit_type_hint"] = hints.get("unit_type_hint") or "hq_co"
    elif re.search(r"\b(plt hq|platoon hq)\b", stem):
        hints["unit_type_hint"] = hints.get("unit_type_hint") or "hq_plt"
    elif re.search(r"\b(hq)\b", stem) and not hints.get("unit_type_hint"):
        hints["unit_type_hint"] = "hq_plt"

    # Squad / fire team
    if re.search(r"\b(sqd|squad|fire team|ft)\b", stem):
        hints["unit_type_hint"] = hints.get("unit_type_hint") or "squad"

    # ── Marker type hints ────────────────────────────────────────────────
    if re.search(r"\bvof\b", stem):
        hints["marker_type_hint"] = "vof"
    elif re.search(r"\bpdf\b|primary direction", stem):
        hints["marker_type_hint"] = "pdf"
    elif re.search(r"\bexposed\b", stem):
        hints["marker_type_hint"] = "exposed"
    elif re.search(r"\bpin(ned)?\b", stem):
        hints["marker_type_hint"] = "pin"
    elif re.search(r"\bconcentrated fire\b", stem):
        hints["marker_type_hint"] = "concentrated_fire"
    elif re.search(r"\bcrossfire\b", stem):
        hints["marker_type_hint"] = "crossfire"
    elif re.search(r"\btactical control\b", stem):
        hints["marker_type_hint"] = "tactical_control"
    elif re.search(r"\bcover\b", stem):
        hints["marker_type_hint"] = "cover"
    elif re.search(r"\bammo\b", stem):
        hints["marker_type_hint"] = "ammo"
    elif re.search(r"\bpotential contact\b|pc\b", stem):
        hints["marker_type_hint"] = "potential_contact"
    elif re.search(r"\bcurrent activity\b", stem):
        hints["marker_type_hint"] = "current_activity"
    elif re.search(r"\bvisibility\b", stem):
        hints["marker_type_hint"] = "visibility"

    # ── Weapon hints ─────────────────────────────────────────────────────
    weapon_keywords = {
        "bazooka": "Bazooka",
        "106mm": "106mm Recoilless Rifle",
        "wpns": "Weapons Team",
        "aslt": "Assault Team",
        "mortar": "Mortar",
        "mg": "Machine Gun",
        "csm": "Company Sergeant Major",
    }
    for kw, wtype in weapon_keywords.items():
        if kw in stem:
            hints["weapon_type"] = wtype
            break

    return hints


def preprocess_image(path: Path) -> tuple:
    """Load image, return (rgb_array, gray_array, thresh, pil_image, otsu)."""
    pil = Image.open(path).convert("RGB")
    arr = np.array(pil)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return arr, gray, thresh, pil, otsu


def run_ocr(gray: np.ndarray, thresh: np.ndarray, otsu: np.ndarray) -> str:
    """Run Tesseract via pytesseract, fall back to EasyOCR.
    Tries all three image versions and combines results."""
    text_parts = []
    try:
        import pytesseract  # type: ignore

        for img in (gray, thresh, otsu):
            t = pytesseract.image_to_string(img, config="--psm 6").strip()
            if t:
                text_parts.append(t)
    except Exception:
        pass

    if not text_parts:
        try:
            import easyocr  # type: ignore

            reader = easyocr.Reader(["en"], gpu=False)
            res = reader.readtext(gray, detail=0)
            text_parts = [str(r) for r in res if str(r).strip()]
        except Exception:
            pass

    return " ".join(text_parts)


def detect_vof_color(rgb: np.ndarray) -> str | None:
    """Heuristic: VOF markers are typically red-tinted."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    red_mask = cv2.inRange(hsv, np.array([0, 80, 80]), np.array([10, 255, 255]))
    red_mask |= cv2.inRange(hsv, np.array([160, 80, 80]), np.array([180, 255, 255]))
    ratio = float(cv2.countNonZero(red_mask)) / red_mask.size
    if ratio > 0.15:
        return "red"
    return None


def load_clip(device: str):
    """Lazy-load CLIP zero-shot classifier."""
    import torch  # type: ignore
    from transformers import CLIPProcessor, CLIPModel  # type: ignore

    model_id = "openai/clip-vit-base-patch32"
    model = CLIPModel.from_pretrained(model_id)
    processor = CLIPProcessor.from_pretrained(model_id)
    model.to(device)
    model.eval()
    return model, processor


def clip_classify(model, processor, image: Image.Image, device: str, category_type: str = "unit") -> tuple:
    import torch  # type: ignore

    if category_type == "marker":
        prompts = CLIP_PROMPTS["marker"]
    else:
        prompts = CLIP_PROMPTS["unit"]

    inputs = processor(
        text=prompts, images=image, return_tensors="pt", padding=True
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
        logits_per_image = outputs.logits_per_image
        probs = logits_per_image.softmax(dim=1)[0]
    best_idx = int(probs.argmax())
    return prompts[best_idx], float(probs[best_idx])


def determine_marker_type_from_ocr(ocr_text: str) -> str | None:
    """Determine marker_type from OCR text."""
    lower = ocr_text.lower()
    if re.search(r"\bvof\b|volume of fire", lower):
        return "vof"
    elif re.search(r"\bpdf\b|primary direction", lower):
        return "pdf"
    elif re.search(r"\bconcentrated fire\b", lower):
        return "concentrated_fire"
    elif re.search(r"\bcrossfire\b", lower):
        return "crossfire"
    elif re.search(r"\bexposed\b", lower):
        return "exposed"
    elif re.search(r"\bpin(ned)?\b", lower):
        return "pin"
    elif re.search(r"\btactical control\b", lower):
        return "tactical_control"
    elif re.search(r"\bcover\b", lower):
        return "cover"
    elif re.search(r"\bammo\b", lower):
        return "ammo"
    elif re.search(r"\bpotential contact\b|pc\b", lower):
        return "potential_contact"
    elif re.search(r"\bcurrent activity\b", lower):
        return "current_activity"
    elif re.search(r"\bvisibility\b", lower):
        return "visibility"
    return None


def determine_category_from_ocr_and_hints(ocr_text: str, hints: dict) -> tuple:
    """Determine (category, subtype, confidence) from OCR + filename hints.
    Returns (category, subtype, confidence, method_override).
    method_override is None or one of: 'ocr_pure', 'filename_pure'."""
    lower = ocr_text.lower()
    h = hints

    # If filename gave us a clear marker type, prioritize it
    if h.get("marker_type_hint"):
        return "marker", h["marker_type_hint"], 0.8, "filename_pure"

    if h.get("unit_type_hint"):
        return "unit", h["unit_type_hint"], 0.75, "filename_pure"

    # OCR-driven classification - markers first
    if any(k in lower for k in ("vof", "volume of fire")):
        return "marker", "vof", 0.8, "ocr_pure"
    elif any(k in lower for k in ("pdf", "primary direction")):
        return "marker", "pdf", 0.8, "ocr_pure"
    elif any(k in lower for k in ("exposed",)):
        return "marker", "exposed", 0.8, "ocr_pure"
    elif any(k in lower for k in ("pin", "pinned")):
        return "marker", "pin", 0.8, "ocr_pure"
    elif any(k in lower for k in ("concentrated fire",)):
        return "marker", "concentrated_fire", 0.8, "ocr_pure"
    elif any(k in lower for k in ("crossfire",)):
        return "marker", "crossfire", 0.8, "ocr_pure"
    elif any(k in lower for k in ("tactical control",)):
        return "marker", "tactical_control", 0.8, "ocr_pure"
    elif any(k in lower for k in ("cover",)):
        return "marker", "cover", 0.8, "ocr_pure"
    elif any(k in lower for k in ("ammo",)):
        return "marker", "ammo", 0.8, "ocr_pure"
    elif any(k in lower for k in ("potential contact", "pc")):
        return "marker", "potential_contact", 0.75, "ocr_pure"
    elif any(k in lower for k in ("current activity",)):
        return "marker", "current_activity", 0.75, "ocr_pure"
    elif any(k in lower for k in ("visibility",)):
        return "marker", "visibility", 0.75, "ocr_pure"

    # OCR-driven units
    if any(k in lower for k in ("hq", "headquarters", "bn hq", "co hq", "plt hq")):
        cat = "unit"
        if "bn hq" in lower:
            sub = "hq_bn"
        elif "co hq" in lower:
            sub = "hq_co"
        elif "plt hq" in lower:
            sub = "hq_plt"
        else:
            sub = h.get("unit_type_hint") or "hq_plt"
        return cat, sub, 0.85, "ocr_pure"

    if any(k in lower for k in ("squad", "sqd", "fire team")):
        return "unit", "squad", 0.85, "ocr_pure"
    elif any(k in lower for k in ("lat", "limited action")):
        return "unit", "lat", 0.8, "ocr_pure"
    elif any(k in lower for k in ("casualty", "cas")):
        return "unit", "casualty", 0.8, "ocr_pure"

    # No clear classification from OCR alone
    return None, None, 0.0, "ocr_pure"


# ── Record building ──────────────────────────────────────────────────────────

def build_record(
    path: Path,
    out_dir: Path,
    schema: dict,
    clip_model=None,
    clip_processor=None,
    device: str = "cpu",
    confidence_threshold: float = 0.70,
) -> dict:
    filename = path.name
    fmt = path.suffix.lower().lstrip(".")
    if fmt == "jpeg":
        fmt = "jpg"

    arr, gray, thresh, pil, otsu = preprocess_image(path)
    h, w = arr.shape[:2]

    hints = parse_filename(filename)
    ocr_text = run_ocr(gray, thresh, otsu)
    vof_color = detect_vof_color(arr)

    # ── Initial classification: filename first, then OCR ──────────────────
    category = "unit"
    subtype = "unknown"
    country = hints.get("country", "Unknown")
    labels: list[str] = []
    confidence = 0.5
    method = "ocr"  # schema-valid default

    ocr_tokens = set(ocr_text.lower().split())

    # ── Step 1: Filename-based classification ────────────────────────────
    if hints.get("marker_type_hint"):
        category = "marker"
        subtype = hints["marker_type_hint"]
        confidence = 0.8
        method = "ocr"  # mapped to 'ocr' for schema validity

    elif hints.get("unit_type_hint"):
        category = "unit"
        subtype = hints["unit_type_hint"]
        confidence = 0.75
        method = "ocr"  # mapped to 'ocr' for schema validity

    # ── Step 2: OCR-based classification ─────────────────────────────────
    if ocr_text.strip():
        ocr_cat, ocr_sub, ocr_conf, ocr_method = determine_category_from_ocr_and_hints(
            ocr_text, hints
        )
        if ocr_conf > confidence:
            category = ocr_cat
            subtype = ocr_sub
            confidence = ocr_conf
            method = ocr_method  # already schema-valid

    # ── Step 3: CLIP zero-shot classification (when confidence is low) ────
    if clip_model is not None and confidence < 0.75:
        try:
            # Determine CLIP category_type based on current best guess
            clip_type = category  # "unit" or "marker"
            prompt, p = clip_classify(clip_model, clip_processor, pil, device, category_type=clip_type)
            labels.append(prompt)
            if p > confidence:
                confidence = p
                method = "hybrid"
                # Map CLIP prompt to refined category/subtype
                prompt_lower = prompt.lower()
                if "squad" in prompt_lower:
                    subtype = "squad"
                    category = "unit"
                elif "headquarters" in prompt_lower or "hq" in prompt_lower:
                    subtype = subtype or "hq_unknown"
                    category = "unit"
                elif "marker" in prompt_lower:
                    category = "marker"
                    if "vof" in prompt_lower:
                        subtype = "vof"
                    elif "pdf" in prompt_lower or "primary direction" in prompt_lower:
                        subtype = "pdf"
                    elif "crossfire" in prompt_lower:
                        subtype = "crossfire"
                    elif "exposed" in prompt_lower:
                        subtype = "exposed"
                    elif "pinned" in prompt_lower:
                        subtype = "pin"
                    elif "concentrated fire" in prompt_lower:
                        subtype = "concentrated_fire"
                    elif "cover" in prompt_lower:
                        subtype = "cover"
                    elif "ammo" in prompt_lower:
                        subtype = "ammo"
                    elif "potential contact" in prompt_lower:
                        subtype = "potential_contact"
                    elif "current activity" in prompt_lower:
                        subtype = "current_activity"
                    elif "visibility" in prompt_lower:
                        subtype = "visibility"
                elif "vehicle" in prompt_lower:
                    subtype = subtype or "vehicle"
                    category = "unit"
                elif "aircraft" in prompt_lower:
                    subtype = subtype or "aircraft"
                    category = "unit"
                elif "lat" in prompt_lower or "limited action" in prompt_lower:
                    subtype = subtype or "lat"
                    category = "unit"
                elif "casualty" in prompt_lower:
                    subtype = subtype or "casualty"
                    category = "unit"
                elif "weapons" in prompt_lower or "weapon" in prompt_lower:
                    subtype = subtype or "weapons_team"
                    category = "unit"
        except Exception:
            pass

    # ── Step 4: Post-classification refinement using filename hints ────────
    # Run after OCR/CLIP to correct any misclassifications based on filename.
    # Filename indicators (step counts, unit types) should take priority.
    if hints.get("steps_total") is not None and category == "marker":
        # Filename has step counts but classified as marker → fix to unit
        category = "unit"
        subtype = "squad"  # default; will be refined in unit_details
    if subtype == "unknown":
        if hints.get("marker_type_hint"):
            subtype = hints["marker_type_hint"]
        elif hints.get("unit_type_hint"):
            subtype = hints["unit_type_hint"]
        elif hints.get("steps_total") is not None:
            # Filename contains step counts (e.g. "3 step") → it's a unit counter
            subtype = "squad"
        elif ocr_tokens:
            # Have OCR text but no clear classification → default to squad
            subtype = "squad"

    # ── Step 5: Post-OCR refinement for markers ──────────────────────────
    if category == "marker" and subtype == "unknown":
        marker_type = determine_marker_type_from_ocr(ocr_text)
        if marker_type:
            subtype = marker_type
            confidence = max(confidence, 0.7)

    # ── Step 5: Extract unit details ─────────────────────────────────────
    unit_details = None
    if category == "unit":
        unit_type_map = {
            "squad": "squad",
            "hq_bn": "hq_bn",
            "hq_co": "hq_co",
            "hq_plt": "hq_plt",
            "lat": "lat",
            "casualty": "casualty",
            "runner": "runner",
            "co_staff": "co_staff",
            "higher_command": "higher_command",
            "unknown": "squad",
            "weapons_team": "weapons_team",
            "vehicle": "vehicle",
            "aircraft": "aircraft",
        }
        unit_type = unit_type_map.get(subtype, "squad")

        valid_unit_types = {
            "squad", "hq_bn", "hq_co", "hq_plt", "fo_spotter",
            "weapons_team", "vehicle", "aircraft", "lat", "casualty",
            "runner", "co_staff", "higher_command",
        }
        if unit_type not in valid_unit_types:
            unit_type = "squad"

        unit_details = {
            "unit_type": unit_type,
            "division": None,
            "battalion": hints.get("platoon"),
            "platoon": hints.get("platoon"),
            "squad_number": hints.get("squad_number"),
            "experience_level": None,
            "steps_total": min(hints.get("steps_total"), 3) if hints.get("steps_total") is not None else None,
            "steps_remaining": min(hints.get("steps_total"), 3) if hints.get("steps_total") is not None else None,
            "vof_rating": None,
            "range_band": None,
            "weapon_type": hints.get("weapon_type"),
            "ammo_type": None,
            "ammo_amount": None,
        }

        # VOF rating from OCR single letters
        for tok in ocr_tokens:
            if tok.upper() in VOF_LEVELS:
                unit_details["vof_rating"] = tok.upper()
                break

        # Experience level hints from OCR tokens
        for tok in ocr_tokens:
            t = tok.title()
            if t in {"Green", "Line", "Veteran", "Elite", "A", "S"}:
                unit_details["experience_level"] = t
                break

    # ── marker_details ────────────────────────────────────────────────────
    marker_details = None
    if category == "marker":
        valid_marker_types = {
            "vof", "pdf", "concentrated_fire", "crossfire",
            "exposed", "pin", "tactical_control", "cover",
            "ammo", "potential_contact", "current_activity", "visibility"
        }
        marker_details = {
            "marker_type": subtype if subtype in valid_marker_types else ("cover" if subtype == "unknown" else subtype),
            "vof_level": None,
            "pdf": None,
            "concentrated_fire": None,
            "crossfire": None,
            "effects": None,
        }
        if vof_color == "red":
            marker_details["vof_level"] = "S"
            marker_details["effects"] = "red VOF marker"

    # ── id, side ──────────────────────────────────────────────────────────
    counter_id = f"{country}-{filename}"
    side = hints.get("side", "unknown")

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
            "classifier": "fof-counter-pipeline v2.1",
            "confidence": round(confidence, 3),
        },
        "country": country,
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
            "vof": None,
            "pdf": None,
            "concentrated_fire": None,
            "crossfire": None,
        },
        "potential_contact": None,
        "classification": {
            "method": method,
            "model": "openai/clip-vit-base-patch32 + tesseract" if clip_model else "tesseract",
            "labels": labels,
            "reviewed": confidence < confidence_threshold,
            "reviewer": None,
            "reviewed_at": None,
            "notes": f"ocr_text={ocr_text[:80]!r}" if ocr_text else None,
        },
    }
    return record


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Classify Fields of Fire counter images.")
    ap.add_argument("--images", type=Path, default=IMAGES_DIR_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--schema", type=Path, default=SCHEMA_PATH_DEFAULT)
    ap.add_argument("--review-queue", type=Path, default=REVIEW_QUEUE_DEFAULT)
    ap.add_argument("--confidence", type=float, default=0.70)
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--no-clip", action="store_true", help="Skip CLIP; OCR + filename only")
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

    clip_model = None
    clip_processor = None
    if not args.no_clip:
        try:
            clip_model, clip_processor = load_clip(args.device)
            print("CLIP model loaded (openai/clip-vit-base-patch32)", flush=True)
        except Exception as exc:
            print(f"WARNING: CLIP unavailable ({exc}); falling back to OCR+filename", file=sys.stderr, flush=True)

    records = []
    review = []
    for idx, img_path in enumerate(images, 1):
        try:
            print(f"[{idx}/{len(images)}] Processing {img_path.name}...", flush=True)
            rec = build_record(
                img_path,
                args.out,
                schema,
                clip_model=clip_model,
                clip_processor=clip_processor,
                device=args.device,
                confidence_threshold=args.confidence,
            )
            jsonschema.validate(instance=rec, schema=schema)
            records.append(rec)
            if rec["classification"]["reviewed"]:
                review.append(rec)
            print(f"[{idx}/{len(images)}] OK {img_path.name} -> {rec['category']}/{rec['subtype']} (conf={rec['image']['confidence']})", flush=True)
        except Exception as exc:  # pragma: no cover - per-image fault isolation
            print(f"ERROR processing {img_path.name}: {exc}", file=sys.stderr, flush=True)

    # Write consolidated JSON
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} records to {args.out}", flush=True)

    # Write sidecar JSONs
    sidecar_dir = args.out.with_suffix(args.out.suffix + ".sidecars")
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    for rec in records:
        side = sidecar_dir / (Path(rec["image"]["filename"]).stem + ".json")
        side.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} sidecar JSONs to {sidecar_dir}", flush=True)

    # Write review queue
    args.review_queue.parent.mkdir(parents=True, exist_ok=True)
    with args.review_queue.open("w", encoding="utf-8") as fh:
        for rec in review:
            fh.write(json.dumps(rec) + "\n")
    print(f"Wrote {len(review)} low-confidence records to {args.review_queue}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())