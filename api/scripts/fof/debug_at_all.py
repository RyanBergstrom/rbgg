import cv2
import numpy as np
import pytesseract
from pathlib import Path
pytesseract.pytesseract.tesseract_cmd=r"C:\Users\p211587\AppData\Local\Tesseract-OCR\tesseract.exe"
root=Path("api/img/fof/cards")
for n in range(1,51):
 fn=f"A{n:02d}.jpg"; img=cv2.imread(str(root/fn),0)
 if img is None: continue
 h,w=img.shape
 # tank/AT symbol at lower-right; inspect several increasingly tight crops around the printed AT badge
 boxes=[(.54,.96,.53,.75),(.58,.95,.56,.74),(.60,.94,.58,.72),(.65,.94,.60,.71)]
 outputs=[]
 for x1,x2,y1,y2 in boxes:
  c=img[int(h*y1):int(h*y2),int(w*x1):int(w*x2)]
  s=cv2.resize(c,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
  vals=[]
  for psm in [11,6,7,8,10,13]:
   t=pytesseract.image_to_string(s,config=f"--psm {psm} -c tessedit_char_whitelist=ATat0123456789O").strip()
   import re
   ms=re.findall(r"(?:AT|At|at|A7|A1|0|O)?\s*([0-9])",t)
   vals.extend([int(x) for x in ms if x.isdigit()])
   outputs.append((x1, x2, y1, y2, vals))
 print(fn, outputs)
