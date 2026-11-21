"""Encode the 2K stills (AVIF) and build their label maps + manifest.

usage: python build.py <workdir with master.png, c1.png, ...> <out img dir>
World = the master's frame, 1376 x 768 units. Each still's rectangle in the world follows from the
chain of normalised crop boxes (chain.json). Label map value = limb*10 + sub-branch, 0 = never greyed.
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).parent
WORK, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
CHAIN = json.loads((HERE / "chain.json").read_text())
HOT = json.loads((HERE / "hot.json").read_text())  # child hotspots in each limb still, 1376x768 px
W, H = 1376, 768

def rect(name):
    if name == "master":
        return [0.0, 0.0, W, H]
    px, py, pw, ph = rect(CHAIN[name]["parent"])
    x, y, w, h = CHAIN[name]["box"]
    return [px + x * pw, py + y * ph, w * pw, h * ph]

skel = {1: [(640, 470), (520, 380), (430, 300), (330, 250), (450, 230)],
        2: [(690, 460), (690, 330), (680, 200), (670, 110)],
        3: [(740, 460), (850, 380), (950, 280), (1000, 230)]}
hot = {}
for li, k in enumerate(["c1", "c2", "c3"], 1):
    x, y, w, h = rect(k)
    hot[li] = [(x + px / 1376 * w, y + py / 768 * h) for px, py in HOT[k]]

def segdist(P, a, b):
    a = np.array(a, float); b = np.array(b, float); d = b - a
    t = np.clip(((P - a) @ d) / (d @ d), 0, 1)
    return np.linalg.norm(P - (a + t[..., None] * d), axis=-1)

# node id -> still name; deeper levels get slots (null) and fall back to the deepest ancestor still
node = {"0": "master"}
for k in (1, 2, 3):
    node[str(k)] = f"c{k}"
    for i in (1, 2, 3):
        node[f"{k}.{i}"] = f"c{k}_{i}"
        for j in (1, 2, 3):
            node[f"{k}.{i}.{j}"] = f"c{k}_{i}_{j}" if f"c{k}_{i}_{j}" in CHAIN else None  # level-3 close-ups where rendered
            for l in (1, 2, 3):
                node[f"{k}.{i}.{j}.{l}"] = None

manifest = {"world": [W, H], "stills": {}, "nodes": node, "hot": {str(k): [[round(a, 1), round(b, 1)] for a, b in v] for k, v in hot.items()}}
for name in ["master", "roots"] + [k for k in CHAIN if k != "roots"]:
    im = Image.open(WORK / f"{name}.png").convert("RGB")
    wx, wy, ww, wh = rect(name)
    im.save(OUT / f"{name}.avif", quality=62, speed=4)
    # label map at half resolution (the client scales it to the still)
    lw, lh = im.width // 2, im.height // 2
    ys, xs = np.mgrid[0:lh, 0:lw]
    P = np.stack([wx + (xs + 0.5) * ww / lw, wy + (ys + 0.5) * wh / lh], -1)
    dl = np.stack([np.min(np.stack([segdist(P, s[j], s[j + 1]) for j in range(len(s) - 1)]), 0) for s in skel.values()])
    limb = dl.argmin(0) + 1
    sub = np.zeros_like(limb)
    for li in (1, 2, 3):
        dh = np.stack([np.linalg.norm(P - np.array(h), axis=-1) for h in hot[li]])
        sub = np.where(limb == li, dh.argmin(0) + 1, sub)
    lab = (limb * 10 + sub) * ((P[..., 1] < 470) & (dl.min(0) < 300))
    Image.fromarray(lab.astype(np.uint8)).save(OUT / f"{name}.lab.png", optimize=True)
    manifest["stills"][name] = {"rect": [round(v, 3) for v in (wx, wy, ww, wh)], "parent": CHAIN.get(name, {}).get("parent"),
                                "src": f"{name}.avif", "lab": f"{name}.lab.png", "px": [im.width, im.height]}
    print(name, [round(v, 1) for v in (wx, wy, ww, wh)], flush=True)
(OUT / "stills.json").write_text(json.dumps(manifest, indent=1))
