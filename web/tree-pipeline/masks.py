"""Feathered per-branch masks for GPU greying (no per-pixel work in the browser).

For every still and every label code it contains (limb*10 + sub-branch), writes a small RGBA PNG whose
alpha is that branch's region, blurred so limb boundaries melt. The browser shows a CSS-greyscaled copy
of the still masked by the union of the codes to grey (mask-image layers add up).

usage: python masks.py ../public/tree          (reads *.lab.png and stills.json, writes masks/ and updates stills.json)
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

OUT = Path(sys.argv[1])
meta = json.loads((OUT / "stills.json").read_text(encoding="utf-8"))
(OUT / "masks").mkdir(exist_ok=True)
total = 0
for name, st in meta["stills"].items():
    lab = np.asarray(Image.open(OUT / st["lab"]))
    small = Image.fromarray(lab).resize((344, 192), Image.NEAREST)  # 1/8 of the 2K still
    arr = np.asarray(small)
    codes = sorted(int(c) for c in np.unique(arr) if c)
    st["masks"] = {}
    for c in codes:
        a = Image.fromarray(((arr == c) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
        rgba = Image.merge("RGBA", (Image.new("L", a.size, 255),) * 3 + (a,))
        path = f"masks/{name}_{c}.png"
        rgba.save(OUT / path, optimize=True)
        st["masks"][str(c)] = path
        total += (OUT / path).stat().st_size
(OUT / "stills.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
print(f"masks: {sum(len(s['masks']) for s in meta['stills'].values())} files, {total / 1024:.0f} KB")
