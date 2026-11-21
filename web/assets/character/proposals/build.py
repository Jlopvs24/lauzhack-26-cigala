"""Generate the 3 character proposals (3 health states x 2 poses each) as SVG.

Run:  python web/assets/character/proposals/build.py
Writes <name>-<health>-<pose>.svg next to this file and index.html (comparison page).

Every SVG uses the same group ids so the final version can be animated with CSS:
  #character  #leaves  #body  #face  #eyes  #mouth  #arm-left  #arm-right  #feet  #extras
"""
import base64
import sys
from pathlib import Path

OUT = Path(__file__).parent
INK = "#2B3A33"          # outline colour, shared by tree and characters
SW = 4                   # outline width at viewBox scale

HEALTH = {
    # leaf fill, leaf vein/shadow, cheek, droop angle (deg), body tint factor
    "sano":    {"leaf": "#5DBB63", "leaf2": "#3E8E4A", "cheek": "#F4A39A", "droop": 0},
    "regular": {"leaf": "#B9C24F", "leaf2": "#8C9632", "cheek": "#EDB7A8", "droop": 22},
    "debil":   {"leaf": "#C9A26B", "leaf2": "#94703F", "cheek": "#E6C8BE", "droop": 55},
}
POSES = ["reposo", "explicando"]


def svg(inner: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" '
        f'width="200" height="240" role="img" aria-label="{title}">\n'
        f'<title>{title}</title>\n'
        f'<g id="character" stroke="{INK}" stroke-width="{SW}" '
        f'stroke-linecap="round" stroke-linejoin="round">\n{inner}\n</g>\n</svg>\n'
    )


# ---------- shared face parts ----------

def eyes(lx, rx, y, health, pose):
    out = [f'<g id="eyes">']
    ry = 7 if health != "debil" else 6
    for x in (lx, rx):
        out.append(f'<ellipse cx="{x}" cy="{y}" rx="5" ry="{ry}" fill="{INK}" stroke="none"/>')
        out.append(f'<circle cx="{x + 1.8}" cy="{y - 2.5}" r="1.8" fill="#fff" stroke="none"/>')
    if health == "debil":  # worried brows
        out.append(f'<path d="M{lx - 7},{y - 11} L{lx + 4},{y - 14}" fill="none" stroke-width="3"/>')
        out.append(f'<path d="M{rx + 7},{y - 11} L{rx - 4},{y - 14}" fill="none" stroke-width="3"/>')
    elif pose == "explicando":  # raised, engaged brows
        out.append(f'<path d="M{lx - 6},{y - 13} Q{lx},{y - 17} {lx + 6},{y - 13}" fill="none" stroke-width="3"/>')
        out.append(f'<path d="M{rx - 6},{y - 13} Q{rx},{y - 17} {rx + 6},{y - 13}" fill="none" stroke-width="3"/>')
    out.append('</g>')
    return "\n".join(out)


def mouth(cx, y, health, pose):
    if pose == "explicando":
        h = {"sano": 12, "regular": 9, "debil": 7}[health]
        d = f'M{cx - 9},{y - 2} Q{cx},{y - 2 + h * 1.6} {cx + 9},{y - 2} Z'
        return f'<path id="mouth" d="{d}" fill="#8E3B3B" stroke-width="3"/>'
    d = {
        "sano":    f'M{cx - 10},{y - 2} Q{cx},{y + 9} {cx + 10},{y - 2}',
        "regular": f'M{cx - 8},{y + 1} Q{cx},{y + 4} {cx + 8},{y + 1}',
        "debil":   f'M{cx - 8},{y + 4} Q{cx},{y - 2} {cx + 8},{y + 4}',
    }[health]
    return f'<path id="mouth" d="{d}" fill="none" stroke-width="3"/>'


def cheeks(lx, rx, y, health):
    c = HEALTH[health]["cheek"]
    return (f'<ellipse cx="{lx}" cy="{y}" rx="7" ry="4.5" fill="{c}" stroke="none" opacity=".9"/>'
            f'<ellipse cx="{rx}" cy="{y}" rx="7" ry="4.5" fill="{c}" stroke="none" opacity=".9"/>')


def leaf(path, health, vein=None):
    h = HEALTH[health]
    v = f'<path d="{vein}" fill="none" stroke="{h["leaf2"]}" stroke-width="2.5"/>' if vein else ""
    return f'<path d="{path}" fill="{h["leaf"]}"/>{v}'


def arm(x1, y1, x2, y2, hand=None, color=INK):
    out = f'<path d="M{x1},{y1} Q{(x1 + x2) / 2 + (6 if x2 > x1 else -6)},{(y1 + y2) / 2 + 4} {x2},{y2}" fill="none" stroke="{color}" stroke-width="6"/>'
    if hand:
        out += f'<circle cx="{x2}" cy="{y2}" r="5.5" fill="{hand}" stroke-width="3"/>'
    return out


def fallen_leaf(x, y, health, rot=-30):
    h = HEALTH[health]
    return (f'<g transform="translate({x},{y}) rotate({rot})">'
            f'<path d="M0,0 C6,-9 18,-9 22,0 C16,7 6,7 0,0 Z" fill="{h["leaf"]}" stroke-width="2.5"/></g>')


# ---------- A: Pip, a seed with two leaves ----------

def pip(health, pose):
    h = HEALTH[health]
    body_fill = {"sano": "#F3D9A4", "regular": "#EBD3A3", "debil": "#E2D2B6"}[health]
    belly = {"sano": "#FBEBC8", "regular": "#F6E6C6", "debil": "#EFE5D3"}[health]
    d = h["droop"]
    leaves = (
        f'<g id="leaves">'
        f'<path d="M100,84 Q98,70 100,60" fill="none" stroke-width="5"/>'
        f'<g transform="rotate({-d} 100 62)">'
        + leaf("M100,62 C86,36 62,32 52,44 C62,64 86,70 100,62 Z", health, "M98,61 Q78,50 60,45")
        + '</g>'
        f'<g transform="rotate({d * 0.8} 100 60)">'
        + leaf("M100,60 C110,30 138,24 150,34 C144,58 116,68 100,60 Z", health, "M102,59 Q124,46 144,36")
        + '</g></g>'
    )
    body = (
        f'<g id="body">'
        f'<path d="M100,80 C142,80 160,130 160,160 C160,194 133,214 100,214 C67,214 40,194 40,160 C40,130 58,80 100,80 Z" fill="{body_fill}"/>'
        f'<ellipse cx="100" cy="178" rx="34" ry="26" fill="{belly}" stroke="none"/>'
        f'</g>'
    )
    feet = (f'<g id="feet"><ellipse cx="80" cy="216" rx="15" ry="7" fill="{body_fill}"/>'
            f'<ellipse cx="120" cy="216" rx="15" ry="7" fill="{body_fill}"/></g>')
    left = f'<g id="arm-left">{arm(46, 166, 28, 190, body_fill)}</g>'
    if pose == "explicando":
        right = f'<g id="arm-right">{arm(154, 156, 184, 124, body_fill)}</g>'
    else:
        right = f'<g id="arm-right">{arm(154, 166, 172, 190, body_fill)}</g>'
    face = f'<g id="face">{cheeks(74, 126, 156, health)}{eyes(86, 114, 140, health, pose)}{mouth(100, 158, health, pose)}</g>'
    extras = f'<g id="extras">{fallen_leaf(140, 226, health) if health == "debil" else ""}</g>'
    return feet + left + right + body + leaves + face + extras


# ---------- B: Mossa, a round bush that walks ----------

CANOPY = [(100, 112, 54), (60, 124, 32), (140, 124, 32), (74, 84, 30), (126, 84, 30), (100, 68, 30), (100, 142, 40)]


def mossa(health, pose):
    h = HEALTH[health]
    circles = CANOPY if health != "debil" else [c for i, c in enumerate(CANOPY) if i != 4]
    scale = {"sano": 1.0, "regular": 0.97, "debil": 0.92}[health]
    trunk = "#A9764E" if health != "debil" else "#9C7E64"
    outline = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{INK}" stroke-width="{SW * 2}"/>' for x, y, r in circles)
    fill = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{h["leaf"]}" stroke="none"/>' for x, y, r in circles)
    # soft inner shadow tufts
    tufts = (f'<path d="M58,128 Q66,138 78,134" fill="none" stroke="{h["leaf2"]}" stroke-width="3"/>'
             f'<path d="M122,134 Q134,138 142,128" fill="none" stroke="{h["leaf2"]}" stroke-width="3"/>'
             f'<path d="M88,70 Q100,62 112,70" fill="none" stroke="{h["leaf2"]}" stroke-width="3"/>')
    berries = {"sano": [(70, 92), (132, 96), (150, 132), (104, 58)], "regular": [(70, 92), (150, 132)], "debil": []}[health]
    fruit = "".join(f'<circle cx="{x}" cy="{y}" r="6" fill="#F2B33D" stroke-width="3"/>' for x, y in berries)
    body = (f'<g id="body" transform="translate(100 120) scale({scale}) translate(-100 -120)">'
            f'{outline}{fill}{tufts}</g>')
    leaves = f'<g id="leaves">{fruit}</g>'
    feet = (f'<g id="feet">'
            f'<path d="M88,176 L86,206 M112,176 L114,206" fill="none" stroke="{INK}" stroke-width="16"/>'
            f'<path d="M88,176 L86,206 M112,176 L114,206" fill="none" stroke="{trunk}" stroke-width="8"/>'
            f'<ellipse cx="82" cy="210" rx="13" ry="6" fill="{trunk}"/><ellipse cx="118" cy="210" rx="13" ry="6" fill="{trunk}"/>'
            f'</g>')

    def twig(x1, y1, x2, y2):
        return (arm(x1, y1, x2, y2, color=INK).replace('stroke-width="6"', 'stroke-width="10"')
                + arm(x1, y1, x2, y2, color=trunk).replace('stroke-width="6"', 'stroke-width="4"')
                + f'<g transform="translate({x2},{y2}) rotate({-40 if x2 > x1 else 220})">'
                  f'<path d="M0,0 C4,-8 14,-8 18,0 C14,6 4,6 0,0 Z" fill="{h["leaf"]}" stroke-width="2.5"/></g>')
    left = f'<g id="arm-left">{twig(48, 140, 26, 164)}</g>'
    right = f'<g id="arm-right">{twig(152, 132, 182, 102) if pose == "explicando" else twig(152, 140, 174, 164)}</g>'
    face = f'<g id="face">{cheeks(74, 126, 134, health)}{eyes(86, 114, 118, health, pose)}{mouth(100, 136, health, pose)}</g>'
    extras = ""
    if health == "regular":
        extras = fallen_leaf(150, 214, health, -10)
    if health == "debil":
        extras = fallen_leaf(140, 216, health, -20) + fallen_leaf(40, 210, health, 25) + fallen_leaf(160, 190, health, 60)
    return feet + left + right + body + leaves + face + f'<g id="extras">{extras}</g>'


# ---------- C: Tilo, a sprout living in a small pot ----------

def tilo(health, pose):
    h = HEALTH[health]
    pot = {"sano": "#E2856A", "regular": "#D98A73", "debil": "#C99A88"}[health]
    rim = {"sano": "#C9664E", "regular": "#C06E59", "debil": "#B08473"}[health]
    soil = {"sano": "#6B4A35", "regular": "#7D5C44", "debil": "#9C8268"}[health]
    bend = {"sano": 0, "regular": 18, "debil": 48}[health]
    n_leaves = {"sano": 3, "regular": 2, "debil": 1}[health]
    sprout = [f'<g id="leaves" transform="rotate({bend} 100 108)">',
              '<path d="M100,108 C96,88 104,70 100,40" fill="none" stroke-width="5"/>',
              f'<path d="M100,108 C96,88 104,70 100,40" fill="none" stroke="{h["leaf2"]}" stroke-width="2"/>']
    if n_leaves >= 1:
        sprout.append(leaf("M100,86 C88,70 68,70 62,80 C72,94 90,94 100,86 Z", health, "M98,86 Q80,80 66,80"))
    if n_leaves >= 2:
        sprout.append(leaf("M101,70 C112,54 132,54 138,64 C128,78 110,78 101,70 Z", health, "M103,70 Q120,64 134,64"))
    if n_leaves >= 3:
        sprout.append(leaf("M100,42 C90,28 92,14 100,8 C108,14 110,28 100,42 Z", health, "M100,40 L100,14"))
    else:
        sprout.append(f'<circle cx="100" cy="40" r="5" fill="{h["leaf2"]}" stroke-width="3"/>')
    sprout.append('</g>')
    body = (f'<g id="body">'
            f'<path d="M60,120 L140,120 L131,206 Q130,214 122,214 L78,214 Q70,214 69,206 Z" fill="{pot}"/>'
            f'<rect x="50" y="104" width="100" height="22" rx="8" fill="{rim}"/>'
            f'<ellipse cx="100" cy="108" rx="42" ry="5" fill="{soil}" stroke="none"/>'
            + (f'<path d="M122,150 L128,162 L123,170" fill="none" stroke-width="2.5"/>' if health == "debil" else "")
            + '</g>')
    feet = (f'<g id="feet"><ellipse cx="82" cy="216" rx="13" ry="6" fill="{rim}"/>'
            f'<ellipse cx="118" cy="216" rx="13" ry="6" fill="{rim}"/></g>')
    left = f'<g id="arm-left">{arm(64, 150, 42, 176, pot)}</g>'
    right = f'<g id="arm-right">{arm(136, 142, 170, 114, pot) if pose == "explicando" else arm(136, 150, 158, 176, pot)}</g>'
    face = f'<g id="face">{cheeks(76, 124, 170, health)}{eyes(87, 113, 154, health, pose)}{mouth(100, 172, health, pose)}</g>'
    extras = f'<g id="extras">{fallen_leaf(146, 228, health, -15) if health == "debil" else ""}</g>'
    return feet + left + right + body + "".join(sprout) + face + extras


CHARACTERS = {
    "pip": (pip, "Pip", "Una semilla curiosa con dos hojas: pregunta antes de explicar y nunca te dice qué elegir, solo qué pasa en cada camino.",
            "Semilla redonda + 2 hojas. Silueta de huevo, muy simple de animar (las hojas son las 'orejas' que expresan el ánimo)."),
    "mossa": (mossa, "Mossa", "Un arbusto bajito y tranquilo que camina despacio: le gusta poner los números en orden y contarlos con calma.",
              "Copa redonda de nubes verdes con piernas de tronco. Las bayas doradas = colchón de ahorro; se caen cuando la salud baja."),
    "tilo": (tilo, "Tilo", "Un brote que vive en su maceta: sabe que crecer lleva tiempo y te enseña cómo cambia tu árbol con cada decisión.",
             "Maceta de terracota con cara + brote. La maceta es 'lo que tienes hoy' (tronco); el brote crece o se dobla con la salud."),
}


def main():
    for key, (fn, name, *_rest) in CHARACTERS.items():
        for health in HEALTH:
            for pose in POSES:
                (OUT / f"{key}-{health}-{pose}.svg").write_text(
                    svg(fn(health, pose), f"{name} — {health}, {pose}"), encoding="utf-8")
    write_index(sys.argv[1] if len(sys.argv) > 1 else None)


def src(name):
    data = (OUT / name).read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(data).decode()


def write_index(embed_for_thread=None):
    cards = []
    for key, (_fn, name, line, note) in CHARACTERS.items():
        cells = "".join(
            f'<figure><img src="{src(f'{key}-{hl}-{p}.svg')}" alt="{name} {hl} {p}"><figcaption>{hl} · {p}</figcaption></figure>'
            for p in POSES for hl in HEALTH)
        cards.append(
            f'<section class="card"><header><h2>{name}</h2><p class="line">“{line}”</p>'
            f'<p class="note">{note}</p></header>'
            f'<div class="hero"><img class="bob" src="{src(f'{key}-sano-reposo.svg')}" alt="{name}"></div>'
            f'<div class="grid">{cells}</div></section>')
    html = INDEX.replace("{{CARDS}}", "\n".join(cards))
    (OUT / "index.html").write_text(html, encoding="utf-8")
    if embed_for_thread:  # variant without page background, for inline previews
        thread = html.replace("background:var(--bg);color:var(--ink);", "").replace("padding:24px 16px", "padding:0")
        Path(embed_for_thread).write_text(thread, encoding="utf-8")


INDEX = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Personaje: propuestas</title>
<style>
:root{--bg:#F6F3EA;--card:#FFFDF7;--ink:#2B3A33;--muted:#6B766F;--line:#E4DFD0}
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
<h1>Personaje: 3 propuestas</h1>
<p class="sub">Cada una en 3 estados de salud (sano · regular · débil) y 2 poses (reposo · explicando). Diseños originales: formas redondeadas simples, sin corteza ni rasgos humanoides de árbol. Todas comparten trazo (#2B3A33, 4px) y paleta de hojas con el árbol (ver STYLE.md).</p>
<div class="wrap">
{{CARDS}}
</div>
<p class="legend">Fila 1: reposo · Fila 2: explicando (brazo señalando a la derecha, boca abierta). Las versiones finales irán animadas (parpadeo, balanceo de hojas, caminar).</p>
</body></html>
"""

if __name__ == "__main__":
    main()
