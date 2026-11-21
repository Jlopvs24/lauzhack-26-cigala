"""Keep web/src/scene/nodes.i18n.json in step with the engine's tree.

    python web/scripts/node-texts.py            # report rows that are missing or stale
    python web/scripts/node-texts.py --write    # add missing rows (es/fr/de = null) and refresh 'en'

Rows are keyed by the engine's English label. A row whose 'en' text changed is marked stale and its
translations are set to null, so `npm test` fails until someone translates them again.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TREE = ROOT / "core" / "data" / "trees" / "alexia.json"
TABLE = ROOT / "web" / "src" / "scene" / "nodes.i18n.json"
LANGS = ("es", "fr", "de")

def nodes(n):
    yield n
    for c in n.get("children", []):
        yield from nodes(c)

tree = json.loads(TREE.read_text(encoding="utf-8"))
table = json.loads(TABLE.read_text(encoding="utf-8"))
todo = []
for n in nodes(tree["root"]):
    en = [n["label"], n.get("description", "")]
    row = table.get(n["label"])
    if row is None:
        todo.append(f"missing  {n['node_id']}  {n['label']}")
        table[n["label"]] = {"en": en, **{l: None for l in LANGS}}
    elif row.get("en") != en:
        todo.append(f"stale    {n['node_id']}  {n['label']}")
        table[n["label"]] = {"en": en, **{l: None for l in LANGS}}
    elif any(not row.get(l) for l in LANGS):
        todo.append(f"untranslated {n['node_id']}  {n['label']}")
print("\n".join(todo) or "all node texts translated")
if "--write" in sys.argv and todo:
    TABLE.write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {TABLE}")
sys.exit(1 if todo else 0)
