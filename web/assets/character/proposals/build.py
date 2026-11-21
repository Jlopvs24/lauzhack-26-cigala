"""Generate the 3 character proposals (3 health states x 2 poses each) as SVG.

v2: humanoid little trees (bark body, branch arms, root feet, leaves on the head).
Original designs: own faces, silhouettes, palettes and names.

Run:  python web/assets/character/proposals/build.py [thread_preview.html]
Writes <name>-<health>-<pose>.svg next to this file and index.html (comparison page).

Every SVG uses the same group ids so the final version can be animated with CSS:
  #character  #legs  #arm-left  #arm-right  #body  #head  #leaves  #face  #eyes  #mouth  #extras
"""
import base64
import sys
from pathlib import Path

OUT = Path(__file__).parent
INK = "#2B2620"   # outline colour, shared by tree and characters
SW = 4

HEALTH = {
    "healthy":    {"leaf": "#5DBB63", "leaf2": "#3E8E4A", "droop": 0,  "tilt": 0},
    "fair": {"leaf": "#B9C24F", "leaf2": "#8C9632", "droop": 20, "tilt": 3},
    "weak":   {"leaf": "#C9A26B", "leaf2": "#94703F", "droop": 50, "tilt": 8},
}
POSES = ["idle", "explaining"]


def svg(inner, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" width="200" height="240" '
            f'role="img" aria-label="{title}">\n<title>{title}</title>\n'
            f'<g id="character" stroke="{INK}" stroke-width="{SW}" stroke-linecap="round" '
            f'stroke-linejoin="round">\n{inner}\n</g>\n</svg>\n')


def branch(x1, y1, x2, y2, fill, w=9, bend=6):
    """A limb: thick ink stroke with a bark stroke on top (gives a clean outline)."""
    mx = (x1 + x2) / 2 + (bend if x2 > x1 else -bend)
    my = (y1 + y2) / 2 + 4
    d = f"M{x1},{y1} Q{mx},{my} {x2},{y2}"
    return (f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{w + 7}"/>'
            f'<path d="{d}" fill="none" stroke="{fill}" stroke-width="{w}"/>')


def fingers(x, y, ang, fill):
    """Three twig fingers fanning out at angle `ang` (degrees, 0 = right)."""
    out = [f'<g transform="translate({x},{y}) rotate({ang})">']
    for a in (-35, 0, 35):
        out.append(f'<g transform="rotate({a})">'
                   f'<path d="M0,0 L11,0" fill="none" stroke="{INK}" stroke-width="8"/>'
                   f'<path d="M0,0 L11,0" fill="none" stroke="{fill}" stroke-width="3.5"/></g>')
    out.append('</g>')
    return "".join(out)


def roots(x, y, fill, flip=1):
    """Root foot: three short splayed roots."""
    return "".join(branch(x, y, x + dx * flip, y + dy, fill, w=5, bend=0) for dx, dy in ((-12, 8), (0, 10), (12, 8)))


def leaf_shape(x, y, ang, size, health, vein=True):
    h = HEALTH[health]
    s = size
    v = (f'<path d="M2,0 L{s * 0.8},0" fill="none" stroke="{h["leaf2"]}" stroke-width="2"/>' if vein else "")
    return (f'<g transform="translate({x},{y}) rotate({ang})">'
            f'<path d="M0,0 C{s * 0.25},{-s * 0.45} {s * 0.8},{-s * 0.45} {s},0 C{s * 0.8},{s * 0.45} {s * 0.25},{s * 0.45} 0,0 Z" '
            f'fill="{h["leaf"]}" stroke-width="3"/>{v}</g>')


def fallen(x, y, health, rot):
    return leaf_shape(x, y, rot, 18, health, vein=False)


def grain(paths, color):
    return "".join(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.5"/>' for d in paths)


def eyes(lx, rx, y, health, pose, style, iris):
    out = ['<g id="eyes">']
    if style == "big":       # big round eyes, two highlights
        rxx, ryy = 8, 10
    elif style == "oval":    # calm oval eyes
        rxx, ryy = 6, 8
    else:                    # small bright dots
        rxx, ryy = 5, 6
    if health == "weak":
        ryy = ryy * 0.75
    for x in (lx, rx):
        out.append(f'<ellipse cx="{x}" cy="{y}" rx="{rxx}" ry="{ryy}" fill="{iris}" stroke-width="2.5"/>')
        out.append(f'<circle cx="{x + rxx * 0.3}" cy="{y - ryy * 0.4}" r="{max(2, rxx * 0.32)}" fill="#fff" stroke="none"/>')
        if style == "big":
            out.append(f'<circle cx="{x - rxx * 0.35}" cy="{y + ryy * 0.4}" r="1.4" fill="#fff" stroke="none"/>')
        if health == "weak":  # heavy eyelid
            out.append(f'<path d="M{x - rxx - 1},{y - ryy * 0.3} Q{x},{y - ryy * 0.9} {x + rxx + 1},{y - ryy * 0.3}" fill="none" stroke-width="3"/>')
    out.append('</g>')
    return "".join(out)


def brows(lx, rx, y, health, pose, color, heavy=False):
    w = 5 if heavy else 3
    if health == "weak":
        return (f'<path d="M{lx - 9},{y + 2} L{lx + 5},{y - 3}" fill="none" stroke="{color}" stroke-width="{w}"/>'
                f'<path d="M{rx + 9},{y + 2} L{rx - 5},{y - 3}" fill="none" stroke="{color}" stroke-width="{w}"/>')
    lift = 4 if pose == "explaining" else 0
    return (f'<path d="M{lx - 9},{y - lift} Q{lx},{y - 6 - lift} {lx + 8},{y - lift}" fill="none" stroke="{color}" stroke-width="{w}"/>'
            f'<path d="M{rx - 8},{y - lift} Q{rx},{y - 6 - lift} {rx + 9},{y - lift}" fill="none" stroke="{color}" stroke-width="{w}"/>')


def mouth(cx, y, health, pose, wide=10):
    if pose == "explaining":
        h = {"healthy": 11, "fair": 9, "weak": 6}[health]
        return (f'<path id="mouth" d="M{cx - wide * 0.8},{y - 2} Q{cx},{y + h * 1.5} {cx + wide * 0.8},{y - 2} Z" '
                f'fill="#6E2F2A" stroke-width="3"/>')
    d = {"healthy": f"M{cx - wide},{y - 2} Q{cx},{y + 9} {cx + wide},{y - 2}",
         "fair": f"M{cx - wide * 0.7},{y + 1} Q{cx},{y + 4} {cx + wide * 0.7},{y + 1}",
         "weak": f"M{cx - wide * 0.7},{y + 4} Q{cx},{y - 2} {cx + wide * 0.7},{y + 4}"}[health]
    return f'<path id="mouth" d="{d}" fill="none" stroke-width="3"/>'


def cheeks(lx, rx, y, color):
    return (f'<ellipse cx="{lx}" cy="{y}" rx="6.5" ry="4" fill="{color}" stroke="none" opacity=".75"/>'
            f'<ellipse cx="{rx}" cy="{y}" rx="6.5" ry="4" fill="{color}" stroke="none" opacity=".75"/>')


def figure(health, pose, c):
    """Assemble a humanoid tree from a design config `c`."""
    h = HEALTH[health]
    k = c["name"].lower()
    bark = c["bark"][health]
    dark = c["bark_dark"][health]
    legs = (f'<g id="legs">{branch(88, 186, 84, 210, bark, w=12, bend=0)}{branch(112, 186, 116, 210, bark, w=12, bend=0)}'
            f'{roots(84, 210, bark)}{roots(116, 210, bark)}</g>')
    sl, sr = c["shoulders"]
    left = f'<g id="arm-left">{branch(*sl, sl[0] - 20, sl[1] + 38, bark)}{fingers(sl[0] - 20, sl[1] + 38, 115, bark)}</g>'
    if pose == "explaining":
        ex, ey = sr[0] + 36, sr[1] - 34
        right = (f'<g id="arm-right">{branch(*sr, ex, ey, bark)}{fingers(ex, ey, -45, bark)}'
                 f'{leaf_shape(ex + 9, ey - 13, -70, 14, health, vein=False)}</g>')
    else:
        right = f'<g id="arm-right">{branch(*sr, sr[0] + 20, sr[1] + 38, bark)}{fingers(sr[0] + 20, sr[1] + 38, 65, bark)}</g>'
    body = (f'<g id="body"><path d="{c["torso"]}" fill="{bark}"/>'
            f'<clipPath id="{k}-torso-clip"><path d="{c["torso"]}"/></clipPath>'
            f'<g clip-path="url(#{k}-torso-clip)">{c["torso_marks"](dark, health)}</g></g>')
    hx, hy = c["head_pivot"]
    head = [f'<g id="head" transform="rotate({h["tilt"]} {hx} {hy})">',
            c["back_foliage"](health) if "back_foliage" in c else "",
            f'<path d="{c["head"]}" fill="{bark}"/>',
            f'<clipPath id="{k}-head-clip"><path d="{c["head"]}"/></clipPath>',
            f'<g clip-path="url(#{k}-head-clip)">{c["head_marks"](dark, health)}</g>',
            f'<g id="leaves">{c["foliage"](health)}</g>',
            f'<g id="face">{c["face"](health, pose, dark)}</g>',
            '</g>']
    extras = ""
    if health == "fair":
        extras = fallen(146, 222, health, -15)
    if health == "weak":
        extras = fallen(140, 224, health, -20) + fallen(40, 220, health, 20) + fallen(158, 196, health, 50)
    return legs + left + right + body + "".join(head) + f'<g id="extras">{extras}</g>'


# ---------- A: Sprig: baby sapling, big round head, sprout on top ----------

def sprig_foliage(health):
    d = HEALTH[health]["droop"]
    out = f'<path d="M100,44 Q98,32 101,22" fill="none" stroke-width="5"/>'
    out += f'<g transform="rotate({-d} 100 26)">{leaf_shape(100, 26, 200, 30, health)}</g>'
    out += f'<g transform="rotate({d} 100 24)">{leaf_shape(101, 24, -25, 32, health)}</g>'
    if health != "weak":
        out += leaf_shape(138, 58, -50, 18, health, vein=False)   # little side leaf
    return out


SPRIG = {
    "name": "Sprig",
    "line": "A freshly sprouted little tree, curious and cheerful: shows you what happens on every branch, but the choice is always yours.",
    "note": "Baby tree: big round head, two-leaf sprout, big dark eyes. Warm bark with soft grain.",
    "bark": {"healthy": "#B07A4E", "fair": "#A87C58", "weak": "#9A8572"},
    "bark_dark": {"healthy": "#7E5233", "fair": "#7A573D", "weak": "#6F5E50"},
    "shoulders": ((84, 136), (116, 136)),
    "torso": "M84,124 C80,146 78,170 82,192 L118,192 C122,170 120,146 116,124 Z",
    "torso_marks": lambda dk, h: grain(["M92,126 Q89,156 93,190", "M108,126 Q111,156 107,190"], dk)
        + f'<ellipse cx="100" cy="160" rx="5" ry="7" fill="none" stroke="{dk}" stroke-width="2.5"/>',
    "head": "M100,42 C138,42 152,66 150,92 C148,118 128,130 100,130 C72,130 52,118 50,92 C48,66 62,42 100,42 Z",
    "head_pivot": (100, 128),
    "head_marks": lambda dk, h: grain(["M60,72 Q56,90 62,108", "M140,72 Q144,90 138,108", "M92,48 Q100,52 108,48"], dk),
    "foliage": sprig_foliage,
    "face": lambda h, p, dk: (cheeks(70, 130, 106, "#E89A7F") + brows(82, 118, 74, h, p, dk)
                              + eyes(82, 118, 90, h, p, "big", "#3A2418") + mouth(100, 110, h, p)),
}


# ---------- B: Maple: young tree with a bushy leaf crown, moss on the shoulder ----------

CROWN = [(100, 38, 26), (74, 48, 20), (126, 48, 20), (86, 27, 17), (114, 27, 17), (58, 56, 13), (142, 56, 13)]


def maple_crown(health):
    circles = CROWN if health == "healthy" else CROWN[:5] if health == "fair" else CROWN[:3]
    h = HEALTH[health]
    out = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{INK}" stroke-width="{SW * 2}"/>' for x, y, r in circles)
    out += "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{h["leaf"]}" stroke="none"/>' for x, y, r in circles)
    out = branch(92, 60, 84, 40, "#8C5E3C", w=5, bend=0) + branch(108, 60, 116, 40, "#8C5E3C", w=5, bend=0) + out
    out += f'<path d="M80,40 Q90,32 100,40 M106,36 Q116,28 126,38" fill="none" stroke="{h["leaf2"]}" stroke-width="3"/>'
    if health == "healthy":
        out += "".join(f'<circle cx="{x}" cy="{y}" r="4.5" fill="#F2B33D" stroke-width="2.5"/>' for x, y in ((70, 44), (132, 52), (104, 22)))
    return out


MAPLE = {
    "name": "Maple",
    "line": "A calm young tree who speaks slowly: puts your numbers in order and tells you what could happen, without pushing you anywhere.",
    "note": "Young tree: leafy canopy on top of the head (thins out as health drops), moss on the shoulder, bark brows, golden fruits = savings.",
    "bark": {"healthy": "#8C5E3C", "fair": "#8A6448", "weak": "#857262"},
    "bark_dark": {"healthy": "#5E3C24", "fair": "#5E4230", "weak": "#5C4E42"},
    "shoulders": ((82, 138), (118, 138)),
    "torso": "M80,124 C76,150 76,172 80,192 L120,192 C124,172 124,150 120,124 Z",
    "torso_marks": lambda dk, h: grain(["M88,126 Q84,150 88,190", "M100,126 Q103,158 99,190", "M112,126 Q116,150 112,190"], dk)
        + (f'<path d="M80,124 Q92,132 104,126 Q98,138 86,136 Z" fill="#7FA650" stroke="none"/>' if h != "weak" else ""),
    "head": "M100,52 C132,52 144,74 142,96 C140,118 124,130 100,130 C76,130 60,118 58,96 C56,74 68,52 100,52 Z",
    "head_pivot": (100, 128),
    "head_marks": lambda dk, h: grain(["M66,84 Q62,98 68,112", "M134,84 Q138,98 132,112"], dk),
    "back_foliage": maple_crown,
    "foliage": lambda h: "",
    "face": lambda h, p, dk: (cheeks(74, 126, 108, "#D98C72") + brows(84, 116, 80, h, p, dk, heavy=True)
                              + eyes(84, 116, 94, h, p, "oval", "#2E1C12") + mouth(100, 112, h, p, wide=12)),
}


# ---------- C: Bea: slender birch kid, pale bark, branch "antlers" with small leaves ----------

def bea_foliage(health):
    d = HEALTH[health]["droop"]
    n = {"healthy": 3, "fair": 2, "weak": 1}[health]
    out = ""
    for side, (bx, by, tx, ty) in ((-1, (88, 50, 70, 24)), (1, (112, 50, 130, 24))):
        out += f'<g transform="rotate({side * d * 0.5} {bx} {by})">{branch(bx, by, tx, ty, "#EDE6D8", w=5, bend=0)}'
        spots = [(tx, ty, -90 + side * 30), ((bx + tx) / 2, (by + ty) / 2, -90 + side * 80), (tx + side * 2, ty + 10, side * 20 if side > 0 else 160)]
        for x, y, a in spots[:n]:
            out += leaf_shape(x, y, a + side * d, 16, health, vein=False)
        out += '</g>'
    return out


BEA = {
    "name": "Bea",
    "line": "A small, bright birch with pale bark: loves asking why and walks you through every path calmly, with the data.",
    "note": "Birch: white bark with dark horizontal marks, slender body, two little branches on the head. The most distinctive silhouette.",
    "bark": {"healthy": "#EDE6D8", "fair": "#E6DFCF", "weak": "#D8D2C6"},
    "bark_dark": {"healthy": "#4A403A", "fair": "#4A403A", "weak": "#5A524C"},
    "shoulders": ((86, 134), (114, 134)),
    "torso": "M86,120 C83,146 82,170 85,192 L115,192 C118,170 117,146 114,120 Z",
    "torso_marks": lambda dk, h: "".join(f'<path d="M{x},{y} l{w},0" fill="none" stroke="{dk}" stroke-width="3"/>'
                                         for x, y, w in ((84, 140, 10), (104, 152, 12), (88, 172, 9), (106, 182, 10))),
    "head": "M100,46 C130,46 142,68 140,92 C138,114 122,124 100,124 C78,124 62,114 60,92 C58,68 70,46 100,46 Z",
    "head_pivot": (100, 122),
    "head_marks": lambda dk, h: "".join(f'<path d="M{x},{y} l{w},0" fill="none" stroke="{dk}" stroke-width="3"/>'
                                        for x, y, w in ((60, 70, 12), (126, 64, 14), (128, 106, 12))),
    "foliage": bea_foliage,
    "face": lambda h, p, dk: (cheeks(76, 124, 102, "#F0A0A0") + brows(86, 114, 74, h, p, dk)
                              + eyes(86, 114, 88, h, p, "dot", "#2B2620") + mouth(100, 104, h, p, wide=8)),
}

CHARACTERS = {"sprig": SPRIG, "maple": MAPLE, "bea": BEA}


def main():
    for f in OUT.glob("*.svg"):
        f.unlink()
    for key, c in CHARACTERS.items():
        for health in HEALTH:
            for pose in POSES:
                (OUT / f"{key}-{health}-{pose}.svg").write_text(
                    svg(figure(health, pose, c), f"{c['name']} — {health}, {pose}"), encoding="utf-8")
    write_index(sys.argv[1] if len(sys.argv) > 1 else None)


def src(name):
    return "data:image/svg+xml;base64," + base64.b64encode((OUT / name).read_bytes()).decode()


def write_index(thread_path=None):
    cards = []
    for key, c in CHARACTERS.items():
        cells = "".join(
            f'<figure><img src="{src(f"{key}-{hl}-{p}.svg")}" alt="{c["name"]} {hl} {p}"><figcaption>{hl} · {p}</figcaption></figure>'
            for p in POSES for hl in HEALTH)
        cards.append(
            f'<section class="card"><header><h2>{c["name"]}</h2><p class="line">“{c["line"]}”</p>'
            f'<p class="note">{c["note"]}</p></header>'
            f'<div class="hero"><img class="bob" src="{src(f"{key}-healthy-idle.svg")}" alt="{c["name"]}"></div>'
            f'<div class="grid">{cells}</div></section>')
    html = INDEX.replace("{{CARDS}}", "\n".join(cards))
    (OUT / "index.html").write_text(html, encoding="utf-8")
    if thread_path:  # variant without page background, for inline previews
        t = (html.replace("background:var(--bg);color:var(--ink);", "").replace("padding:24px 16px", "padding:0")
             .replace("minmax(340px,1fr)", "minmax(220px,1fr)")
             .replace("</style>", ".card{color:#2B2620}.hero img{width:120px;height:144px}</style>"))
        Path(thread_path).write_text(t, encoding="utf-8")


INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Character proposals</title>
<style>
:root{--bg:#F6F3EA;--card:#FFFDF7;--ink:#2B2620;--muted:#6B766F;--line:#E4DFD0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 20px;max-width:900px}
.wrap{display:grid;gap:20px;grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}
h2{margin:0;font-size:20px}.line{margin:6px 0;font-style:italic}.note{margin:0;color:var(--muted);font-size:13px}
.hero{display:flex;justify-content:center;padding:10px 0 4px}.hero img{width:150px;height:180px}
.bob{animation:bob 2.4s ease-in-out infinite;transform-origin:50% 100%}
@keyframes bob{0%,100%{transform:translateY(0) scaleY(1)}50%{transform:translateY(-4px) scaleY(1.02)}}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
figure{margin:0;text-align:center;background:#F4F7EF;border-radius:10px;padding:6px 2px}
figure img{width:100%;max-width:110px;height:auto}figcaption{font-size:11px;color:var(--muted)}
.legend{margin-top:20px;font-size:13px;color:var(--muted)}
</style></head><body>
<h1>Character: 3 proposals (v2, little humanoid trees)</h1>
<p class="sub">Each in 3 health states (healthy · fair · weak) and 2 poses (idle · explaining). Bark body, branch arms with twig fingers, root feet and leaves on the head; each with its own face, silhouette, palette and name.</p>
<div class="wrap">
{{CARDS}}
</div>
<p class="legend">Row 1: idle · Row 2: explaining (arm pointing right holding a leaf, mouth open). The final version will be animated (blink, swaying leaves, walking).</p>
</body></html>
"""

if __name__ == "__main__":
    main()
