"""Parameter optimisation against PUBLIC verified targets (#48 item 8).

    python -m core.bench.optimise            # markdown tables (the numbers of OPTIMISATION.md)
    python -m core.bench.optimise --json

Honest by construction:
- objective = the one of ``harness.score``: weighted squared error, in tolerance units, over the
  entries of ``targets.json`` with ``status: "verified"`` and weight > 0. Public Swiss sources only;
  the UBS synthetic ledgers are never a target;
- searched = parameters tagged ``tunable`` in ``params.json`` that have a sourced ``range`` and that
  at least one used target informs. Rules (payroll, tax tables, thresholds, value judgements) are
  never searched (``harness.search`` refuses them too);
- every parameter stays inside its sourced range;
- method: seeded random search (``SAMPLES`` points), then coordinate refinement in a shrinking window;
- overfitting guards. A parameter leaves its sourced default only if:
  1. material: moving it lowers the loss by at least ``MATERIAL`` (0.25 = the default sits more than
     half a tolerance from what the targets say; inside that, the target's own uncertainty wins); and
  2. robust: with two or more targets on the parameter, the best fit stays on the same side of the
     default when any one of them is left out (leave-one-target-out), so no single window or source
     drives the move. With a single target that test is impossible, so the bar is higher instead:
     a gain of at least ``MATERIAL_SINGLE`` (1.0 = the default is more than one tolerance away).
"""
from __future__ import annotations

import json
import sys

import numpy as np

from ..assumptions import build_assumptions
from .harness import HERE, load_params, load_targets, model_quantity, score

SEED = 20261121
SAMPLES = 400
ROUNDS = 4
MATERIAL = 0.25
MATERIAL_SINGLE = 1.0
PRE_ITEM_7 = {"AS-unemployment-duration": 6}  # the only bench-relevant default that item 7 corrected


def informs(t: dict) -> tuple[str, ...]:
    """Engine params a target constrains."""
    if t["kind"] == "assumption":
        return (t["param"],)
    if t["kind"] == "real_return":
        return ("investment_return_mean", "inflation_mean")
    return ()


def used_targets() -> list[dict]:
    return [t for t in load_targets() if t["status"] == "verified" and t.get("weight", 1) > 0
            and t.get("target") is not None and informs(t)]


def search_space(targets: list[dict]) -> dict[str, dict]:
    """Tunable parameters with a sourced range that at least one used target informs."""
    _, classes = load_params(HERE / "params.json")
    aset = build_assumptions()
    wanted = {p for t in targets for p in informs(t)}
    space = {}
    for pid, cls in classes.items():
        a = aset.get(pid)
        if cls == "tunable" and a is not None and a["param"] in wanted and a.get("range"):
            space[pid] = {"param": a["param"], "default": float(a["value"]), "range": [float(x) for x in a["range"]]}
    return space


def loss_of(ov: dict, targets: list[dict]) -> float:
    """Same objective as ``harness.score`` (weighted squared error in tolerance units), unrounded."""
    A = build_assumptions(overrides=ov or None).values()
    return float(sum(t.get("weight", 1.0) * ((model_quantity(t, A, None) - t["target"]) / t["tolerance"]) ** 2
                     for t in targets))


def fit(targets: list[dict], space: dict[str, dict]) -> dict:
    """Best parameter set inside the ranges for these targets. A parameter that none of these
    targets informs is not searched and stays at its default."""
    wanted = {p for t in targets for p in informs(t)}
    fixed = {i: sp["default"] for i, sp in space.items() if sp["param"] not in wanted}
    space = {i: sp for i, sp in space.items() if sp["param"] in wanted}
    ids = list(space)
    lo = np.array([space[i]["range"][0] for i in ids])
    hi = np.array([space[i]["range"][1] for i in ids])
    best = {i: space[i]["default"] for i in ids}
    best_loss = loss_of(best, targets)
    rng = np.random.default_rng(SEED)
    for x in lo + rng.random((SAMPLES, len(ids))) * (hi - lo):  # 1. seeded random search
        ov = dict(zip(ids, map(float, x)))
        f = loss_of(ov, targets)
        if f < best_loss:
            best, best_loss = ov, f
    width = (hi - lo) / 4
    for _ in range(ROUNDS):  # 2. coordinate refinement in a shrinking window
        for k, pid in enumerate(ids):
            for v in np.clip(np.linspace(best[pid] - width[k], best[pid] + width[k], 21), lo[k], hi[k]):
                f = loss_of({**best, pid: float(v)}, targets)
                if f < best_loss - 1e-12:
                    best, best_loss = {**best, pid: float(v)}, f
        width = width / 3
    return {**best, **fixed}


def optimise() -> dict:
    targets = used_targets()
    space = search_space(targets)
    default = {i: space[i]["default"] for i in space}
    best = fit(targets, space)
    loo = {t["id"]: fit([u for u in targets if u["id"] != t["id"]], space) for t in targets
           if any(space[i]["param"] in informs(t) for i in space)}
    chosen, params = {}, {}
    for pid, sp in space.items():
        step = (sp["range"][1] - sp["range"][0]) / 1000  # below this a move is numerical noise

        def side(v: float) -> int:
            return int(np.sign(v - default[pid])) if abs(v - default[pid]) > step else 0

        mine = [t["id"] for t in targets if sp["param"] in informs(t)]  # the targets on this parameter
        gain = loss_of({**best, pid: default[pid]}, targets) - loss_of(best, targets)
        flips = sorted(tid for tid in mine if side(loo[tid][pid]) != side(best[pid]))
        if len(mine) >= 2:
            robust, need = side(best[pid]) != 0 and not flips, MATERIAL
        else:  # one source only: leave-one-out is impossible, ask for a larger gain instead
            robust, need, flips = gain >= MATERIAL_SINGLE, MATERIAL_SINGLE, []
        moved = bool(gain >= need and robust)
        chosen[pid] = round(best[pid], 4) if moved else default[pid]
        params[pid] = {**sp, "targets": mine, "best_fit": round(best[pid], 5), "loss_gain": round(gain, 4),
                       "gain_needed": need, "robust": bool(robust), "changes_side_without": flips,
                       "loo_range": [round(min(loo[t][pid] for t in mine), 5), round(max(loo[t][pid] for t in mine), 5)],
                       "chosen": chosen[pid], "moved": moved}
    sets = {"before_item_7": PRE_ITEM_7, "defaults": {}, "best_fit": {k: round(v, 5) for k, v in best.items()},
            "chosen": {k: v for k, v in chosen.items() if v != default[k]}}
    scores = {name: score(ov or None) for name, ov in sets.items()}
    weights = {t["id"]: t.get("weight", 1) for t in load_targets()}
    rows = []
    for i, p in enumerate(scores["defaults"]["parts"]):
        if p.get("used"):
            rows.append({"id": p["id"], "target": p["target"], "tolerance": p["tolerance"], "weight": weights[p["id"]],
                         **{f"model_{n}": s["parts"][i]["model"] for n, s in scores.items()},
                         **{f"loss_{n}": s["parts"][i]["loss"] for n, s in scores.items()}})
    return {"seed": SEED, "samples": SAMPLES, "rounds": ROUNDS, "material": MATERIAL, "material_single": MATERIAL_SINGLE,
            "loss": {n: s["loss"] for n, s in scores.items()}, "targets_scored": len(rows),
            "targets_in_objective": len(targets), "params": params, "sets": sets, "targets": rows}


def headline_impact(sets: dict[str, dict]) -> list[dict]:
    """Root and first-level nodes under each parameter set: final net worth and funding gap."""
    from .. import expand
    out = []
    for label, ov in sets.items():
        for n in expand(None, [], ov or None, sensitivity=False, exploration=False)["nodes"]:
            m = n["result"]["metrics"]
            out.append({"set": label, "node_id": n["node_id"], "label": n["label"],
                        "final_net_worth": m["final_net_worth"], "final_net_worth_real": m["final_net_worth_real"],
                        "min_cash": m["min_cash"], "first_negative_month": m["first_negative_month"],
                        "plan_check": n["result"]["plan_check"]["level"]})
    return out


WHAT_IFS = {"real_wage_0.5pct": {"AS-real-wage-growth": 0.005}, "real_wage_2pct": {"AS-real-wage-growth": 0.02}}


def main() -> None:
    r = optimise()
    r["impact"] = headline_impact({k: r["sets"][k] for k in ("defaults", "best_fit", "chosen")} | WHAT_IFS)
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2))
        return
    L = r["loss"]
    print(f"loss over {r['targets_in_objective']} verified targets with weight > 0 ({r['targets_scored']} scored): "
          f"before item 7 {L['before_item_7']}, defaults {L['defaults']}, best fit {L['best_fit']}, chosen {L['chosen']} "
          f"(seed {r['seed']}, {r['samples']} samples + {r['rounds']} refinement rounds)\n")
    print("| target | public value | tolerance | weight | model (defaults) | loss (defaults) | model (best fit) | loss (best fit) |")
    print("|---|---|---|---|---|---|---|---|")
    for t in r["targets"]:
        print(f"| `{t['id']}` | {t['target']} | {t['tolerance']} | {t['weight']} | {t['model_defaults']} | {t['loss_defaults']} | "
              f"{t['model_best_fit']} | {t['loss_best_fit']} |")
    print("\n| parameter | sourced default | range | targets | best fit | leave-one-out best fits | loss gain (needed) | robust | chosen |")
    print("|---|---|---|---|---|---|---|---|---|")
    for pid, c in r["params"].items():
        if len(c["targets"]) < 2:
            rob = "one source"
        else:
            rob = "yes" if c["robust"] else f"no: side changes without {', '.join(c['changes_side_without']) or 'a move'}"
        print(f"| `{pid}` | {c['default']} | {c['range']} | {len(c['targets'])} | {c['best_fit']} | "
              f"{c['loo_range'][0]} to {c['loo_range'][1]} | {c['loss_gain']} ({c['gain_needed']}) | {rob} | "
              f"{c['chosen']}{' (moved)' if c['moved'] else ' (kept)'} |")
    print("\n| node | set | final net worth | at today's prices | min cash | first negative month | plan check |")
    print("|---|---|---|---|---|---|---|")
    order = ["defaults", "best_fit", "chosen", *WHAT_IFS]
    for x in sorted(r["impact"], key=lambda x: (x["node_id"], order.index(x["set"]))):
        print(f"| {x['node_id']} {x['label']} | {x['set']} | {x['final_net_worth']:,.0f} | {x['final_net_worth_real']:,.0f} | "
              f"{x['min_cash']:,.0f} | {x['first_negative_month']} | {x['plan_check']} |")


if __name__ == "__main__":
    main()
