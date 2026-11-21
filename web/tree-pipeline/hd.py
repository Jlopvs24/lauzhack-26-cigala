"""Re-render the still chain at 2K, keeping every transition matched.

Each still is generated from an exact crop of its parent's 2K still (so it sits on a known
rectangle of the parent) and then colour-matched to that crop. Order: master, then its children,
then theirs. Usage (from this folder, scratch dir as cwd for outputs):

    ENVF=<.env.local> COSTLOG=costs.log IMG_SIZE=2K python hd.py <workdir> [still ...]

Crop boxes are normalised (x, y, w, h) in the parent still. The 16:9 aspect is kept at every level.
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).parent
WORK = Path(sys.argv[1])
ONLY = set(sys.argv[2:])
MODEL = "google/gemini-3.1-flash-image"
TREE = json.loads((HERE / "chain.json").read_text())  # {still: {parent, box}}


def match(src, ref):
    a = np.asarray(src, np.float32); r = np.asarray(ref.resize(src.size), np.float32)
    out = (a - a.mean((0, 1))) / (a.std((0, 1)) + 1e-6) * r.std((0, 1)) + r.mean((0, 1))
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def render(name):
    node = TREE[name]
    parent = Image.open(WORK / f"{node['parent']}.png").convert("RGB")
    W, H = parent.size
    x, y, w, h = node["box"]
    crop = parent.crop((round(x * W), round(y * H), round((x + w) * W), round((y + h) * H)))
    crop.resize((2048, 1152), Image.LANCZOS).save(WORK / f"crop_{name}.jpg", quality=92)
    raw = WORK / f"raw_{name}.png"
    if not raw.exists():
        subprocess.run([sys.executable, str(HERE / "gen.py"), MODEL, str(raw), str(HERE / "p_zoom.txt"),
                        str(WORK / f"crop_{name}.jpg"), "16:9"], check=True)
    out = match(Image.open(raw).convert("RGB"), crop)
    out.save(WORK / f"{name}.png")
    return name


levels = {}
for name, node in TREE.items():
    d, p = 0, node["parent"]
    while p != "master":
        d += 1; p = TREE[p]["parent"]
    levels.setdefault(d, []).append(name)
for d in sorted(levels):
    todo = [n for n in levels[d] if not ONLY or n in ONLY]
    with ThreadPoolExecutor(6) as ex:
        for n in ex.map(render, todo):
            print("done", n, flush=True)
