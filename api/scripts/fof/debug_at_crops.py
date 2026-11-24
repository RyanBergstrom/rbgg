import cv2
import pytesseract
from pathlib import Path
pytesseract.pytesseract.tesseract_cmd=r"C:\Users\p211587\AppData\Local\Tesseract-OCR\tesseract.exe"
root=Path('api/img/fof/cards')
for fn in ['A01.jpg','A05.jpg','A10.jpg','A20.jpg','A25.jpg','A30.jpg','A40.jpg','A50.jpg']:
 img=cv2.imread(str(root/fn),0); h,w=img.shape
 print('\n'+fn)
 for box in [(.62,.95,.58,.72),(.68,.94,.59,.70),(.70,.92,.60,.69),(.64,.94,.55,.72),(.72,.93,.58,.68)]:
  x1,x2,y1,y2=box; c=img[int(h*y1):int(h*y2),int(w*x1):int(w*x2)]
  s=cv2.resize(c,None,fx=5,fy=5,interpolation=cv2.INTER_CUBIC)
  out=[]
  for psm in [6,7,8,11]:
   t=pytesseract.image_to_string(s,config=f'--psm {psm} -c tessedit_char_whitelist=ATat0123456789Oo').strip().replace('\n',' ')
   out.append(t)
  print(box,out)
