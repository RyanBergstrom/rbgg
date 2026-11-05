import cv2
import numpy as np
from PIL import Image
from pathlib import Path

# Test OCR on 1_1 3 step.png
path = Path(r"C:\Dev\rbgg\documentation\fof\test-images\1_1 3 step.png")
pil = Image.open(path).convert("RGB")
arr = np.array(pil)
gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
blur = cv2.GaussianBlur(gray, (3, 3), 0)
thresh = cv2.adaptiveThreshold(
    blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
)
_, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

# Run tesseract on each
import pytesseract
for i, img in enumerate((gray, thresh, otsu)):
    t = pytesseract.image_to_string(img, config="--psm 6").strip()
    print(f"  OCR img[{i}] (mode {'gray','thresh','otsu'}[i]): '{t}'")
EOF