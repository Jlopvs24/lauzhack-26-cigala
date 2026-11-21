"""Generate synthetic Swiss financial documents + ground truth.

    python -m multimodal.gen.generate --people 20 --out data/synthetic

Writes <out>/docs/<doc_id>.(pdf|jpg|png) and <out>/manifest.jsonl (one line per
document with ground truth). Deterministic for a given --seed.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .content import BUILDERS, load_people
from .degrade import VARIANTS
from .render import render

ROOT = Path(__file__).resolve().parents[2]
VARIANT_CYCLE = ["pdf", "scan", "photo", "lowres", "hard"]


def pick_people(n: int, seed: int):
    people = load_people(seed=seed)
    rng = random.Random(seed)
    chosen = [people[0]]  # Alexia, the demo persona
    by_lang: dict[str, list] = {}
    for p in people[1:]:
        by_lang.setdefault(p.lang, []).append(p)
    langs = sorted(by_lang)
    i = 0
    while len(chosen) < n:
        pool = by_lang[langs[i % len(langs)]]
        chosen.append(pool.pop(rng.randrange(len(pool))))
        i += 1
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--people", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "data" / "synthetic"))
    args = ap.parse_args()

    out = Path(args.out)
    (out / "docs").mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    manifest = []
    k = 0
    for p in pick_people(args.people, args.seed):
        for doc_type, build in BUILDERS.items():
            # ~15% of documents are in English regardless of canton (expats, international employers)
            lang = "en" if rng.random() < 0.15 else p.lang
            c = build(p, rng, lang)
            variant = VARIANT_CYCLE[k % len(VARIANT_CYCLE)]
            if p.profile_id == "P00001":
                variant = {"payslip": "photo", "bank_statement": "pdf", "rental_contract": "scan"}[doc_type]
            k += 1
            doc_id = f"{p.profile_id}-{doc_type}"
            pdf_path = out / "docs" / f"{doc_id}.pdf"
            render(c, pdf_path, rng)
            if variant == "pdf":
                file = pdf_path
            else:
                img = VARIANTS[variant](pdf_path, rng)
                ext = "png" if variant == "lowres" else "jpg"
                file = out / "docs" / f"{doc_id}.{ext}"
                img.save(file, quality=rng.randint(30, 45) if variant == "hard" else rng.randint(55, 80)) if ext == "jpg" else img.save(file)
                pdf_path.unlink()
            manifest.append({
                "doc_id": doc_id, "file": file.relative_to(out).as_posix(), "doc_type": doc_type,
                "lang": lang, "variant": variant, "profile_id": p.profile_id,
                "truth": c.truth, "profile_fields": c.profile_fields,
            })
    with open(out / "manifest.jsonl", "w", encoding="utf-8") as f:
        for m in manifest:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"wrote {len(manifest)} documents to {out}")


if __name__ == "__main__":
    main()
