import json, sys
import numpy as np
from PIL import Image
OUT = sys.argv[1]
H = json.load(open('hot.json')); B2 = json.load(open('boxes2.json'))
L1 = {'c1': (200,100), 'c2': (408,20), 'c3': (740,110)}
sx, sy = 560/1376, 315/768
stills = {'master': ('master.png', [0,0,1376,768]), 'roots': ('m_roots.png', [408,450,560,315])}
for k,(x,y) in L1.items():
    stills[k] = (f'm_{k}.png', [x,y,560,315])
    for i in (1,2,3):
        b = B2[f'{k}_{i}']
        stills[f'{k}_{i}'] = (f'm_{k}_{i}.png', [x+b[0]*sx, y+b[1]*sy, 280, 157.5])
# limb skeletons (world coords) and child hotspots (world)
skel = {1: [(640,470),(520,380),(430,300),(330,250),(450,230)],
        2: [(690,460),(690,330),(680,200),(670,110)],
        3: [(740,460),(850,380),(950,280),(1000,230)]}
hot = {}
for li,k in enumerate(['c1','c2','c3'],1):
    x,y = L1[k]
    hot[li] = [(x+px*sx, y+py*sy) for px,py in H[k]]
def segdist(P, a, b):
    a=np.array(a,float); b=np.array(b,float); d=b-a
    t=np.clip(((P-a)@d)/(d@d),0,1)
    return np.linalg.norm(P-(a+t[...,None]*d),axis=-1)
meta = {}
for name,(fn,(wx,wy,ww,wh)) in stills.items():
    im = Image.open(fn).convert('RGB'); W,Hh = im.size
    a = np.asarray(im).astype(np.float32)/255
    r,g,b = a[...,0],a[...,1],a[...,2]
    mx,mn = a.max(-1),a.min(-1); sat=(mx-mn)/(mx+1e-6)
    tree = (mx < 0.55) | ((g > b+0.06) & (g >= r*0.95) & (sat > 0.18))
    ys,xs = np.mgrid[0:Hh,0:W]
    P = np.stack([wx+xs*ww/W, wy+ys*wh/Hh],-1)
    dl = np.stack([np.min(np.stack([segdist(P,s[j],s[j+1]) for j in range(len(s)-1)]),0) for s in skel.values()])
    limb = dl.argmin(0)+1
    sub = np.zeros_like(limb)
    for li in (1,2,3):
        dh = np.stack([np.linalg.norm(P-np.array(h),axis=-1) for h in hot[li]]); sub = np.where(limb==li, dh.argmin(0)+1, sub)
    lab = (limb*10+sub)*((P[...,1] < 470) & (dl.min(0) < 300))
    Image.fromarray(lab.astype(np.uint8)).save(f'{OUT}/img/{name}.lab.png', optimize=True)
    im.save(f'{OUT}/img/{name}.webp', quality=84, method=6)
    meta[name] = {'rect':[round(v,2) for v in (wx,wy,ww,wh)]}
    # debug overlay
    if name in ('master','c2'):
        pal = {11:(255,0,0),12:(255,120,0),13:(255,200,0),21:(0,0,255),22:(0,150,255),23:(0,255,255),31:(150,0,255),32:(255,0,255),33:(255,0,120)}
        col = np.asarray(im).copy()
        for v,c in pal.items(): col[lab==v] = (col[lab==v]*0.4+np.array(c)*0.6).astype(np.uint8)
        Image.fromarray(col).save(f'dbg_{name}.jpg', quality=70)
meta['hot'] = {str(k):[[round(x,1),round(y,1)] for x,y in v] for k,v in hot.items()}
json.dump(meta, open(f'{OUT}/img/stills.json','w'), indent=1)
print(json.dumps(meta)[:600])
