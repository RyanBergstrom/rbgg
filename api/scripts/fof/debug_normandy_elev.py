from pathlib import Path
import cv2
root=Path(__file__).resolve().parents[3]/'api'/'img'/'fof'/'cards'
out=Path(__file__).resolve().parents[3]/'api'/'img'/'fof'/'normandy_elev_debug'
out.mkdir(parents=True,exist_ok=True)
for n in [1,5,6,7,8,9,10,20,22,25,26,34,35,36,37,41,45,46,49,53,54,55]:
 p=next(iter(root.glob(f'N{n:02d} *')),None)
 im=cv2.imread(str(p));h,w=im.shape[:2]
 c=im[int(h*.08):int(h*.23),int(w*.68):int(w*.90)]
 cv2.imwrite(str(out/f'N{n:02d}.png'),cv2.resize(c,None,fx=8,fy=8,interpolation=cv2.INTER_CUBIC))
print(out)
