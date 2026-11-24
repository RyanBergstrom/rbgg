"""Random Number Section reader for Fields of Fire Action Cards.

Templates come from user-verified cards:
- Cards #48 and #50 show every value: column N holds N (2-12).
- Cards #1-#4 hold all 1s; Card #5 holds 1s with column 12 = 2.

Single digits (ink width < 10 px) match against single-digit templates.
Two-digit values 10, 11, 12 always start with "1": the leading component is
dropped and the remaining glyph is matched against 0 / 1 / 2 templates, which
come from the second digit of cells 10-12 on Cards #48 and #50.
Values never decrease left to right.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

CARDS_DIR = Path(__file__).resolve().parents[3] / "api" / "img" / "fof" / "cards"
COLUMNS = list(range(2, 13))
GLYPH_W, GLYPH_H = 16, 24
TWO_DIGIT_MIN_WIDTH = 10


def random_number_strip(gray: np.ndarray, region: dict | None = None) -> np.ndarray:
    if region is not None:
        h, w = gray.shape
        x1 = max(0, min(w, round(float(region["x"]) * w)))
        y1 = max(0, min(h, round(float(region["y"]) * h)))
        x2 = max(x1 + 1, min(w, round((float(region["x"]) + float(region["width"])) * w)))
        y2 = max(y1 + 1, min(h, round((float(region["y"]) + float(region["height"])) * h)))
        strip = gray[y1:y2, x1:x2]
        # Value digits occupy the lower half of the 2-row strip.
        return strip[int(strip.shape[0] * 0.45):, :]
    h, w = gray.shape
    strip = gray[int(h * 0.885):int(h * 0.975), int(w * 0.05):int(w * 0.95)]
    return strip[int(strip.shape[0] * 0.45):, :]


def _components(cell: np.ndarray):
    inset = 3
    c = cell[inset:-inset, inset:-inset]
    blur = cv2.GaussianBlur(c, (3, 3), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ch, cw = binary.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary)
    comps = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 8 or bw > cw * 0.8 or bh > ch * 0.95:
            continue
        comps.append((int(x), i))
    comps.sort()
    return labels, stats, comps


def _normalize(mask: np.ndarray) -> np.ndarray | None:
    ys, xs = np.where(mask)
    if ys.size == 0:
        return None
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255
    return cv2.resize(crop, (GLYPH_W, GLYPH_H), interpolation=cv2.INTER_AREA).astype(np.float32)


def _cell_parts(cell: np.ndarray):
    """Return (ink width, whole-cell glyph, glyph without the leading component)."""
    labels, stats, comps = _components(cell)
    if not comps:
        return 0, None, None
    ids = [i for _, i in comps]
    xs = [stats[i, cv2.CC_STAT_LEFT] for i in ids]
    width = int(max(stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH] for i in ids) - min(xs))
    whole = _normalize(np.isin(labels, ids))
    tail = _normalize(np.isin(labels, ids[1:])) if len(ids) > 1 else None
    return width, whole, tail


def _card_cells(card: int):
    img = cv2.imread(str(CARDS_DIR / f"A{card:02d}.jpg"))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    val = random_number_strip(gray)
    cw = val.shape[1] / 11.0
    return {col: _cell_parts(val[:, int((col - 2) * cw):int((col - 1) * cw)]) for col in COLUMNS}


def build_templates(exclude: tuple[int, ...] = ()):
    singles: dict[int, list[np.ndarray]] = {}
    tails: dict[int, list[np.ndarray]] = {}

    for card in (1, 2, 3, 4, 5):
        for col, (width, whole, _) in _card_cells(card).items():
            value = 2 if (card == 5 and col == 12) else 1
            if whole is not None and width < TWO_DIGIT_MIN_WIDTH:
                singles.setdefault(value, []).append(whole)

    for card in (48, 50):
        if card in exclude:
            continue
        for col, (width, whole, tail) in _card_cells(card).items():
            if col <= 9 and whole is not None:
                singles.setdefault(col, []).append(whole)
            elif col >= 10 and tail is not None:
                tails.setdefault(col - 10, []).append(tail)

    mean = lambda d: {k: np.mean(v, axis=0) for k, v in d.items()}  # noqa: E731
    return mean(singles), mean(tails)


@lru_cache(maxsize=1)
def _default_templates():
    return build_templates()


def _best_label(img: np.ndarray, templates: dict[int, np.ndarray]) -> int:
    scores = {v: float(cv2.matchTemplate(img, t, cv2.TM_CCOEFF_NORMED)[0][0]) for v, t in templates.items()}
    return max(scores, key=scores.get)


def read_random_number_row(gray: np.ndarray, templates=None, region: dict | None = None) -> dict[str, int]:
    singles, tails = templates or _default_templates()
    strip = random_number_strip(gray, region)
    cw = strip.shape[1] / 11.0
    result: dict[str, int] = {}
    running = 1
    for i, col in enumerate(COLUMNS):
        width, whole, tail = _cell_parts(strip[:, int(i * cw):int((i + 1) * cw)])
        if whole is None:
            value = running
        elif width >= TWO_DIGIT_MIN_WIDTH and tail is not None:
            value = 10 + _best_label(tail, tails)
        else:
            value = _best_label(whole, singles)
        value = max(value, running)  # never decreases left to right
        running = value
        result[str(col)] = value
    return result
