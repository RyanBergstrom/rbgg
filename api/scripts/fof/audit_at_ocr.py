import cv2
import pytesseract
import re
from pathlib import Path
pytesseract.pytesseract.tesseract_cmd=r"C:\Users\p211587\AppData\Local\Tesseract-OCR\tesseract.exe"
root=Path('api/img/fof/cards')
for n in range(1,51):
 fn=f"A{n:02d}.jpg"; img=cv2.imread(str(root/fn),0)
 if img is None: continue
 h,w=img.shape; c=img[int(h*.58):int(h*.72),int(w*.62):int(w*.95)]; s=cv2.resize(c,None,fx=5,fy=5,interpolation=cv2.INTER_CUBIC)
 outs=[]
 for psm in [6,7,11,8]:
  t=pytesseract.image_to_string(s,config=f"--psm {psm} -c tessedit_char_whitelist=ATat0123456789Oo").strip().replace('\n',' ')
  m=re.search(r"A[T7I1]\s*([0-9O])",t,re.I)
  if m: outs.append((psm,m.group(1).replace('O','0')))
 print(f"{n:02d}: {outs}")
