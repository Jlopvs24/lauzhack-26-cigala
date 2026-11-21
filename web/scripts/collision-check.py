"""Browser check: at every node of every branch, on desktop and phone widths, in EN/ES/FR/DE,
no visible branch card overlaps Lumi, her speech bubble, the dock or the Back button.

Needs the dev server (npm run dev, :5175) and the API (:8000). Uses the dev-only window.__cigala hook.
    python web/scripts/collision-check.py [--chrome PATH] [--out DIR]
Exit code 1 if any overlap is found.
"""
import argparse, asyncio, json, sys, urllib.request
from playwright.async_api import async_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--chrome", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
ap.add_argument("--base", default="http://127.0.0.1:5175/")
ap.add_argument("--api", default="http://127.0.0.1:8000")
ap.add_argument("--out", default=None, help="save a screenshot of every failing state here")
args = ap.parse_args()


def expand(path):
    req = urllib.request.Request(f"{args.api}/tree/expand", data=json.dumps({"path": path}).encode(),
                                 headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def all_paths():  # walk the tree the API serves (works for any depth)
    out, todo = [], [[]]
    while todo:
        p = todo.pop(0)
        out.append(p)
        for n in expand(p)["nodes"]:
            if n["status"] == "child":
                todo.append(p + [n["node_id"]])
    return out


MEASURE = """() => {
  const rect = (el) => { const r = el.getBoundingClientRect(); return r.width && r.height ? r : null; };
  const obstacles = ['.say-card', '#lumi', '.dock', '.nav-back'].map((s) => document.querySelector(s)).filter(Boolean).map(rect).filter(Boolean);
  const bad = [];
  for (const t of document.querySelectorAll('.tag')) {
    if (t.classList.contains('occluded') || +getComputedStyle(t).opacity < 0.5) continue;
    const a = t.querySelector('.card').getBoundingClientRect();
    for (const o of obstacles) if (a.right > o.left && a.left < o.right && a.bottom > o.top && a.top < o.bottom) bad.push(t.textContent.slice(0, 30));
  }
  const offscreen = [...document.querySelectorAll('.tag:not(.occluded)')].filter((t) => { const r = t.getBoundingClientRect(); return r.right < 0 || r.left > innerWidth || r.bottom < 0 || r.top > innerHeight; }).length;
  const faded = [...document.querySelectorAll('.tag.occluded.child, .tag.occluded.sibling')].map((t) => t.textContent.slice(0, 30));
  return { bad, offscreen, faded, side: document.querySelector('.narration')?.classList.contains('right') ? 'right' : 'left', tags: document.querySelectorAll('.tag').length };
}"""


async def run(browser, lang, width, height, paths, results):
    ctx = await browser.new_context(viewport={"width": width, "height": height}, is_mobile=width < 720, has_touch=width < 720)
    await ctx.add_init_script(f"try {{ localStorage.setItem('cigala.lang', '{lang}'); }} catch (e) {{}}")
    pg = await ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    await pg.goto(args.base)
    await pg.wait_for_function("window.__cigala")
    await pg.wait_for_timeout(1500)
    await pg.evaluate("window.__cigala.begin()")
    await pg.wait_for_timeout(5000)
    for p in paths:
        await pg.evaluate(f"window.__cigala.go({json.dumps(p)})")
        await pg.wait_for_function("!window.__cigala.busy", timeout=60000)
        await pg.wait_for_timeout(2600)  # camera settles, bubble appears, avoidance converges
        m = await pg.evaluate(MEASURE)
        key = f"{lang} {width}px {'/'.join(p) or 'root'}"
        results.append((key, m))
        if (m["bad"] or m["offscreen"] or m.get("faded")) and args.out:
            await pg.screenshot(path=f"{args.out}/{lang}_{width}_{'-'.join(p) or 'root'}.png")
    results.append((f"{lang} {width}px page errors", {"bad": errors, "offscreen": 0}))
    await ctx.close()


async def main():
    paths = all_paths()
    print(f"{len(paths)} nodes, 4 languages, 2 widths", flush=True)
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=args.chrome)
        await asyncio.gather(*[run(browser, lang, w, h, paths, results)
                               for lang in ("en", "es", "fr", "de") for (w, h) in ((1440, 860), (390, 844))])
        await browser.close()
    failed = [(k, m) for k, m in results if m["bad"] or m["offscreen"]]
    sides = {}
    for k, m in results:
        if "side" in m:
            sides[m["side"]] = sides.get(m["side"], 0) + 1
    print(f"states checked: {sum(1 for k, m in results if 'side' in m)}, bubble side: {sides}")
    for k, m in failed:
        print("OVERLAP" if m["bad"] else "OFFSCREEN", k, m["bad"], m.get("offscreen"))
    faded = [(k, m["faded"]) for k, m in results if m.get("faded")]
    print(f"states where a clickable card had to be faded: {len(faded)}")
    for k, f in faded:
        print("  faded", k, f)
    print("PASS" if not failed else f"FAIL ({len(failed)})")
    sys.exit(1 if failed else 0)

asyncio.run(main())
