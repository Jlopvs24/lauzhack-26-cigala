"""Generate the 3 character proposals (3 health states x 2 poses each) as SVG.

v3: simple friendly bubble characters (the tree already lives on the page).
Original designs: round body, small floating hands, minimal face.

Run:  python web/assets/character/proposals/build.py [thread_preview.html]
Writes <name>-<health>-<pose>.svg next to this file and index.html (comparison page).

Every SVG uses the same group ids so the final version can be animated with CSS:
  #character  #shadow  #float  #body  #face  #eyes  #mouth  #hand-left  #hand-right  #extras
(#float wraps everything that bobs up and down; #shadow stays on the ground.)
"""
import base64
import sys
from pathlib import Path

OUT = Path(__file__).parent
FACE_INK = "#2B2620"

# body colours per health: (light, base, dark/outline)
HEALTH_COLORS = {
    "fair": ("#F6F0C8", "#D9CC6A", "#9C8F35"),
    "weak": ("#ECE6DC", "#C4B6A2", "#86786A"),
}
HEALTHS = ["healthy", "fair", "weak"]
POSES = ["idle", "explaining"]
# squash (sx, sy) anchored at the bottom of the body, and how much it sinks
SHAPE = {"healthy": (1.0, 1.0, 0), "fair": (1.03, 0.95, 4), "weak": (1.1, 0.86, 10)}


def svg(inner, title, defs):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" width="200" height="240" '
            f'role="img" aria-label="{title}">\n<title>{title}</title>\n<defs>{defs}</defs>\n'
            f'<g id="character" stroke-linecap="round" stroke-linejoin="round">\n{inner}\n</g>\n</svg>\n')


def gradient(gid, light, base):
    return (f'<radialGradient id="{gid}" cx="38%" cy="30%" r="75%">'
            f'<stop offset="0" stop-color="{light}"/><stop offset=".55" stop-color="{base}"/>'
            f'<stop offset="1" stop-color="{base}"/></radialGradient>')


def eyes(lx, rx, y, health, pose):
    out = ['<g id="eyes">']
    ry = 8.5 if health != "weak" else 6.5
    for x in (lx, rx):
        out.append(f'<ellipse cx="{x}" cy="{y}" rx="6" ry="{ry}" fill="{FACE_INK}"/>')
        out.append(f'<circle cx="{x + 2}" cy="{y - 3}" r="2.2" fill="#fff"/>')
    if health == "weak":
        for x, s in ((lx, 1), (rx, -1)):
            out.append(f'<path d="M{x - 8 * s},{y - 10} L{x + 5 * s},{y - 14}" fill="none" stroke="{FACE_INK}" stroke-width="3"/>')
    elif pose == "explaining":
        for x in (lx, rx):
            out.append(f'<path d="M{x - 6},{y - 15} Q{x},{y - 19} {x + 6},{y - 15}" fill="none" stroke="{FACE_INK}" stroke-width="3"/>')
    out.append('</g>')
    return "".join(out)


def mouth(cx, y, health, pose):
    if pose == "explaining":
        h = {"healthy": 12, "fair": 9, "weak": 6}[health]
        return (f'<path id="mouth" d="M{cx - 8},{y - 2} Q{cx},{y - 2 + h * 1.5} {cx + 8},{y - 2} Z" '
                f'fill="#7A3030" stroke="{FACE_INK}" stroke-width="3"/>')
    d = {"healthy": f"M{cx - 9},{y - 2} Q{cx},{y + 8} {cx + 9},{y - 2}",
         "fair": f"M{cx - 7},{y + 1} Q{cx},{y + 4} {cx + 7},{y + 1}",
         "weak": f"M{cx - 7},{y + 4} Q{cx},{y - 2} {cx + 7},{y + 4}"}[health]
    return f'<path id="mouth" d="{d}" fill="none" stroke="{FACE_INK}" stroke-width="3"/>'


def face(cx, ey, health, pose, gap=15):
    cheek = {"healthy": "#F49A9A", "fair": "#EFAE9E", "weak": "#E3BDB2"}[health]
    return (f'<g id="face">'
            f'<ellipse cx="{cx - gap - 10}" cy="{ey + 14}" rx="7" ry="4.5" fill="{cheek}" opacity=".8"/>'
            f'<ellipse cx="{cx + gap + 10}" cy="{ey + 14}" rx="7" ry="4.5" fill="{cheek}" opacity=".8"/>'
            f'{eyes(cx - gap, cx + gap, ey, health, pose)}{mouth(cx, ey + 18, health, pose)}</g>')


def hand(x, y, fill, stroke, point=False, ang=0):
    """A small floating mitten. With point=True it has a little pointing finger."""
    finger = (f'<path d="M4,-3 C12,-6 18,-4 18,0 C18,3 12,4 5,3 Z" fill="{fill}" stroke="{stroke}" stroke-width="3"/>'
              if point else "")
    return (f'<g transform="translate({x},{y}) rotate({ang})">{finger}'
            f'<ellipse cx="0" cy="0" rx="9" ry="8" fill="{fill}" stroke="{stroke}" stroke-width="3.5"/></g>')


def sparkle(x, y, color, s=1.0):
    return (f'<path transform="translate({x},{y}) scale({s})" d="M0,-8 Q1,-1 8,0 Q1,1 0,8 Q-1,1 -8,0 Q-1,-1 0,-8 Z" '
            f'fill="{color}"/>')


def figure(key, c, health, pose):
    light, base, dark = c["colors"] if health == "healthy" else HEALTH_COLORS[health]
    sx, sy, sink = SHAPE[health]
    gid = f"{key}-{health}-grad"
    defs = gradient(gid, light, base)
    bottom = c["bottom"]
    tilt = 6 if pose == "explaining" else 0
    body = (f'<g id="body" transform="translate(0 {sink}) rotate({tilt} 100 {bottom}) '
            f'translate(100 {bottom}) scale({sx} {sy}) translate(-100 -{bottom})">'
            f'{c["back"](health, dark) if "back" in c else ""}'
            f'<path d="{c["path"]}" fill="url(#{gid})" stroke="{dark}" stroke-width="4.5"/>'
            f'<ellipse cx="{c["shine"][0]}" cy="{c["shine"][1]}" rx="13" ry="8" transform="rotate(-30 {c["shine"][0]} {c["shine"][1]})" fill="#fff" opacity=".75"/>'
            f'<circle cx="{c["shine"][0] + 15}" cy="{c["shine"][1] - 9}" r="3.5" fill="#fff" opacity=".75"/>'
            f'{face(100, c["eyes_y"], health, pose)}</g>')
    hy = c["hands_y"] + sink
    left = f'<g id="hand-left">{hand(c["hands_x"][0], hy, base, dark)}</g>'
    if pose == "explaining":
        right = f'<g id="hand-right">{hand(c["hands_x"][1] - 6, hy - 52, base, dark, point=True, ang=-35)}</g>'
    else:
        right = f'<g id="hand-right">{hand(c["hands_x"][1], hy, base, dark)}</g>'
    extras = ""
    if health == "healthy":
        extras = sparkle(40, 60, "#F2B33D") + sparkle(160, 52, "#F2B33D", .7)
    if health == "weak":
        extras = (f'<path d="M148,{88 + sink} C152,96 154,100 150,104 C146,108 140,104 142,98 Z" '
                  f'fill="#BFE3F5" stroke="#6FA8C8" stroke-width="2.5"/>')
    shadow_rx = {"healthy": 40, "fair": 46, "weak": 54}[health]
    shadow = f'<ellipse id="shadow" cx="100" cy="226" rx="{shadow_rx}" ry="7" fill="{FACE_INK}" opacity=".13"/>'
    inner = shadow + f'<g id="float">{body}{left}{right}<g id="extras">{extras}</g></g>'
    return inner, defs


# ---------- A: Bo, a glossy bubble ----------
BO = {
    "name": "Bo",
    "line": "A light, bouncy bubble: floats next to your tree, explains what each branch means, and never tells you which one to pick.",
    "note": "Pure circle with a glossy shine. The simplest silhouette: easy to animate (bounce, squash, glide).",
    "colors": ("#C9F3EC", "#5CCFC0", "#2A8F83"),
    "path": "M100,62 C138,62 166,90 166,130 C166,170 138,198 100,198 C62,198 34,170 34,130 C34,90 62,62 100,62 Z",
    "bottom": 198, "shine": (66, 92), "eyes_y": 124, "hands_x": (26, 174), "hands_y": 160,
}


# ---------- B: Lumi, a bubble with a small leaf on top (ties it to the tree) ----------
def lumi_leaf(health, dark):
    leaf = {"healthy": ("#6CCB5F", "#3E944A"), "fair": ("#B9C24F", "#8C9632"), "weak": ("#C9A26B", "#94703F")}[health]
    droop = {"healthy": 0, "fair": 25, "weak": 60}[health]
    small = ("M0,0 C-3,-9 -13,-12 -18,-8 C-15,-1 -6,2 0,0 Z", "M0,0 C3,-10 14,-13 19,-8 C16,-1 6,2 0,0 Z")
    return (f'<path d="M100,72 Q98,62 100,54" fill="none" stroke="{dark}" stroke-width="3.5"/>'
            f'<g transform="translate(100 55) rotate({-droop})"><path d="{small[0]}" fill="{leaf[0]}" stroke="{leaf[1]}" stroke-width="2.5"/></g>'
            f'<g transform="translate(100 55) rotate({droop})"><path d="{small[1]}" fill="{leaf[0]}" stroke="{leaf[1]}" stroke-width="2.5"/></g>')


LUMI = {
    "name": "Lumi",
    "line": "A soft little blob with a tiny sprout on top: curious, patient, and happy to show you every path before you choose.",
    "note": "Gumdrop-shaped blob with a tiny two-leaf sprout that droops when health drops. Links the character to the tree without being a tree.",
    "colors": ("#E2F7D6", "#8DD67A", "#3E944A"),
    "path": "M100,72 C142,72 168,106 170,150 C171,182 158,196 138,196 L62,196 C42,196 29,182 30,150 C32,106 58,72 100,72 Z",
    "bottom": 196, "shine": (66, 104), "eyes_y": 136, "hands_x": (22, 178), "hands_y": 162,
    "back": lumi_leaf,
}


# ---------- C: Dew, a water drop that keeps the tree alive ----------
DEW = {
    "name": "Dew",
    "line": "A friendly drop of water: it keeps your tree growing by helping you understand it, one branch at a time.",
    "note": "Drop shape (soft point on top). Metaphor: water for the tree. Squashes like a puddle when health is weak.",
    "colors": ("#D6ECFF", "#6BB3EC", "#2F78B5"),
    "path": "M100,48 C116,78 162,104 162,144 C162,178 134,200 100,200 C66,200 38,178 38,144 C38,104 84,78 100,48 Z",
    "bottom": 200, "shine": (70, 118), "eyes_y": 140, "hands_x": (28, 172), "hands_y": 168,
}

CHARACTERS = {"bo": BO, "lumi": LUMI, "dew": DEW}


def main():
    for f in OUT.glob("*.svg"):
        f.unlink()
    for key, c in CHARACTERS.items():
        for health in HEALTHS:
            for pose in POSES:
                inner, defs = figure(key, c, health, pose)
                (OUT / f"{key}-{health}-{pose}.svg").write_text(
                    svg(inner, f"{c['name']}, {health}, {pose}", defs), encoding="utf-8")
    write_index(sys.argv[1] if len(sys.argv) > 1 else None)


def src(name):
    return "data:image/svg+xml;base64," + base64.b64encode((OUT / name).read_bytes()).decode()


def write_index(thread_path=None):
    cards = []
    for key, c in CHARACTERS.items():
        cells = "".join(
            f'<figure><img src="{src(f"{key}-{hl}-{p}.svg")}" alt="{c["name"]} {hl} {p}"><figcaption>{hl} · {p}</figcaption></figure>'
            for p in POSES for hl in HEALTHS)
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
.bob{animation:bob 2.4s ease-in-out infinite}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@media (prefers-reduced-motion:reduce){.bob{animation:none}}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
figure{margin:0;text-align:center;background:#F4F7EF;border-radius:10px;padding:6px 2px}
figure img{width:100%;max-width:110px;height:auto}figcaption{font-size:11px;color:var(--muted)}
.legend{margin-top:20px;font-size:13px;color:var(--muted)}
</style></head><body>
<h1>Character: 3 proposals (v3, bubbles)</h1>
<p class="sub">The tree already lives on the page, so the guide is a simple, friendly bubble. Each proposal in 3 health states (healthy · fair · weak) and 2 poses (idle · explaining). Health shows in colour, shape (it deflates) and expression.</p>
<div class="wrap">
{{CARDS}}
</div>
<p class="legend">Row 1: idle · Row 2: explaining (leans and points right with a floating hand, mouth open). The final version will be animated (float, blink, squash, glide to the leaf it explains).</p>
</body></html>
"""

if __name__ == "__main__":
    main()
