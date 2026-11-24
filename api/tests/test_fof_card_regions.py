import json
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]
REGION_PATH = ROOT / "api" / "configs" / "fof" / "card_regions.json"
CARDS_DIR = ROOT / "api" / "img" / "fof" / "cards"


def test_card_region_map_has_normalized_valid_boxes():
    regions = json.loads(REGION_PATH.read_text(encoding="utf-8"))

    def check_box(box):
        assert 0 <= box["x"] < 1
        assert 0 <= box["y"] < 1
        assert 0 < box["width"] <= 1
        assert 0 < box["height"] <= 1
        assert box["x"] + box["width"] <= 1
        assert box["y"] + box["height"] <= 1

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"crop", "hotspot"}:
                    check_box(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(regions)
    normandy_elevation = regions["terrain"]["Normandy Terrain"]["elevation"]["crop"]
    default_elevation = regions["terrain"]["default"]["elevation"]["crop"]
    assert normandy_elevation["y"] < 0.25 and normandy_elevation["x"] > 0.5
    assert default_elevation["y"] > 0.7


def test_classifier_shared_region_crop_handles_native_image_sizes():
    import sys

    sys.path.insert(0, str(ROOT / "api" / "scripts" / "fof"))
    from fof_card_classifier import CARD_REGIONS, _crop_region

    for filename, region in (
        ("N01 Hill.jpg", CARD_REGIONS["terrain"]["Normandy Terrain"]["elevation"]["crop"]),
        ("001.png", CARD_REGIONS["terrain"]["default"]["cover"]["crop"]),
        ("A01.jpg", CARD_REGIONS["action"]["anti_tank"]["crop"]),
    ):
        image = cv2.imread(str(CARDS_DIR / filename))
        assert image is not None, filename
        crop = _crop_region(image, region)
        assert crop.size > 0
        assert crop.shape[0] < image.shape[0]
        assert crop.shape[1] < image.shape[1]
