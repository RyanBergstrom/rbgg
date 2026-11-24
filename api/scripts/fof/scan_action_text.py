import cv2
import pytesseract
import re
from pathlib import Path

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\p211587\AppData\Local\Tesseract-OCR\tesseract.exe"
CARDS_DIR = Path("api/img/fof/cards")

a_files = sorted(list(CARDS_DIR.glob("A*.jpg")))

print(f"Scanning all {len(a_files)} action cards for text keywords...")

found = []
for p in a_files:
    img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    h, w = img.shape
    center = img[int(h * 0.18):int(h * 0.76), int(w * 0.35):int(w * 0.95)]
    txt = pytesseract.image_to_string(cv2.resize(center, (0, 0), fx=2, fy=2), config="--psm 11").strip()
    
    tags = []
    if re.search(r"\bHQ\b", txt, re.IGNORECASE):
        tags.append("HQ")
    if re.search(r"Short", txt, re.IGNORECASE):
        tags.append("Short")
    if re.search(r"Jam", txt, re.IGNORECASE):
        tags.append("Jam")
    if tags:
        found.append((p.name, tags, txt.replace("\n", " ")[:60]))

print(f"Found {len(found)} cards with text cues:")
for name, tags, sample in found:
    print(f"  {name:10s} -> {tags} (OCR: {repr(sample)})")
