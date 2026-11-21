"""Mock engine: a stand-in for core/ (thread 1) so the web can start now.

It follows docs/contracts.md v0 shapes. Numbers are computed (not invented) with a
simple monthly cash model + a small vectorised Monte Carlo, but the model is a
placeholder: once core/ ships, api/engine.py switches to it and this file is
only a fallback. Every result carries "engine": "mock".
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import numpy as np

HORIZON = 120
N_PATHS = 1000
SEED = 42

# ---------------------------------------------------------------- assumptions
# Global assumptions (editable). Values are placeholders until core/ + sources land.
DEFAULT_ASSUMPTIONS: list[dict[str, Any]] = [
    {"id": "AS-market-return", "param": "annual_return", "value": 0.05, "unit": "1/year",
     "source": "placeholder (mock engine)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
    {"id": "AS-market-vol", "param": "annual_volatility", "value": 0.15, "unit": "1/year",
     "source": "placeholder (mock engine)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
    {"id": "AS-expense-noise", "param": "monthly_expense_noise", "value": 0.05, "unit": "share",
     "source": "placeholder (mock engine)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
    {"id": "AS-job-loss-rate", "param": "monthly_job_loss_prob", "value": 0.004, "unit": "1/month",
     "source": "placeholder (mock engine)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
    {"id": "AS-loan-rate", "param": "loan_annual_rate", "value": 0.02, "unit": "1/year",
     "source": "placeholder (mock engine)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
    {"id": "AS-salary-junior-ch", "param": "salary_junior", "value": 4200, "unit": "CHF/month",
     "source": "UBS kit scenario_config.json (illustrative)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
    {"id": "AS-salary-master-ch", "param": "salary_master", "value": 4800, "unit": "CHF/month",
     "source": "UBS kit scenario_config.json (illustrative)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
    {"id": "AS-salary-abroad", "param": "salary_abroad", "value": 3700, "unit": "CHF/month",
     "source": "UBS kit scenario_config.json (illustrative)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
    {"id": "AS-tuition-semester", "param": "tuition_semester", "value": 2500, "unit": "CHF/year",
     "source": "UBS kit scenario_config.json (illustrative)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
    {"id": "AS-relocation-cost", "param": "relocation_cost", "value": 6500, "unit": "CHF",
     "source": "UBS kit scenario_config.json (illustrative)", "retrieved": "2026-11-21", "editable": True, "kind": "assumption"},
]


def assumption_values(overrides: list[dict] | None) -> dict[str, float]:
    vals = {a["id"]: float(a["value"]) for a in DEFAULT_ASSUMPTIONS}
    for o in overrides or []:
        if o.get("id") in vals and o.get("value") is not None:
            vals[o["id"]] = float(o["value"])
    return vals


def assumptions_list(overrides: list[dict] | None) -> list[dict]:
    vals = assumption_values(overrides)
    out = []
    for a in DEFAULT_ASSUMPTIONS:
        b = dict(a)
        b["value"] = vals[a["id"]]
        out.append(b)
    return out


# ---------------------------------------------------------------- decision tree
# Interventions reference assumptions with {"ref": "AS-..."} so editing an assumption
# changes every node that uses it. "scale" multiplies the referenced value.
def _iv(param, op, value, from_month=0, to_month=HORIZON):
    return {"param": param, "op": op, "value": value, "from_month": from_month, "to_month": to_month}


TREE: dict[str, dict] = {
    "0": {"label": "Today", "interventions": [], "assumptions_ref": []},
    # level 1
    "1": {"label": "Start working now",
          "interventions": [_iv("monthly_net_income", "set", {"ref": "AS-salary-junior-ch"}),
                            _iv("monthly_other_expenses", "set", 2100)],
          "assumptions_ref": ["AS-salary-junior-ch"]},
    "2": {"label": "Master's degree (2 years)",
          "interventions": [_iv("monthly_net_income", "set", 1200, 0, 24),
                            _iv("monthly_other_expenses", "set", 1200, 0, 24),
                            _iv("cash", "one_off", {"ref": "AS-tuition-semester", "scale": -1}, 0, 1),
                            _iv("cash", "one_off", {"ref": "AS-tuition-semester", "scale": -1}, 12, 13),
                            _iv("monthly_net_income", "set", {"ref": "AS-salary-master-ch"}, 24, HORIZON),
                            _iv("monthly_other_expenses", "set", 2200, 24, HORIZON)],
          "assumptions_ref": ["AS-tuition-semester", "AS-salary-master-ch"]},
    "3": {"label": "Move abroad and work",
          "interventions": [_iv("monthly_net_income", "set", {"ref": "AS-salary-abroad"}),
                            _iv("monthly_other_expenses", "set", 2000),
                            _iv("cash", "one_off", {"ref": "AS-relocation-cost", "scale": -1}, 0, 1)],
          "assumptions_ref": ["AS-salary-abroad", "AS-relocation-cost"]},
    # level 2 under 1
    "1.1": {"label": "Stay in Lausanne and invest CHF 500/month",
            "interventions": [_iv("monthly_investment", "set", 500)],
            "assumptions_ref": ["AS-market-return", "AS-market-vol"]},
    "1.2": {"label": "Move abroad after 2 years",
            "interventions": [_iv("monthly_net_income", "set", {"ref": "AS-salary-abroad"}, 24, HORIZON),
                              _iv("monthly_other_expenses", "set", 2000, 24, HORIZON),
                              _iv("cash", "one_off", {"ref": "AS-relocation-cost", "scale": -1}, 24, 25)],
            "assumptions_ref": ["AS-salary-abroad", "AS-relocation-cost"]},
    "1.3": {"label": "Part-time master's after 2 years",
            "interventions": [_iv("monthly_net_income", "set", 2600, 24, 60),
                              _iv("cash", "one_off", {"ref": "AS-tuition-semester", "scale": -1}, 24, 25),
                              _iv("cash", "one_off", {"ref": "AS-tuition-semester", "scale": -1}, 36, 37),
                              _iv("cash", "one_off", {"ref": "AS-tuition-semester", "scale": -1}, 48, 49),
                              _iv("monthly_net_income", "set", {"ref": "AS-salary-master-ch"}, 60, HORIZON)],
            "assumptions_ref": ["AS-tuition-semester", "AS-salary-master-ch"]},
    # level 2 under 2
    "2.1": {"label": "Work part-time during the master's",
            "interventions": [_iv("monthly_net_income", "add", 1000, 0, 24)],
            "assumptions_ref": []},
    "2.2": {"label": "Take a CHF 15,000 student loan",
            "interventions": [_iv("debt", "borrow", 15000, 0, 1),
                              _iv("monthly_debt_payment", "set", 300, 24, HORIZON)],
            "assumptions_ref": ["AS-loan-rate"]},
    "2.3": {"label": "Move to a shared flat (rent CHF 600)",
            "interventions": [_iv("monthly_rent", "set", 600, 0, 24)],
            "assumptions_ref": []},
    # level 2 under 3
    "3.1": {"label": "Come back to Switzerland after 3 years",
            "interventions": [_iv("monthly_net_income", "set", {"ref": "AS-salary-master-ch"}, 36, HORIZON),
                              _iv("monthly_other_expenses", "set", 2200, 36, HORIZON),
                              _iv("cash", "one_off", {"ref": "AS-relocation-cost", "scale": -1}, 36, 37)],
            "assumptions_ref": ["AS-salary-master-ch", "AS-relocation-cost"]},
    "3.2": {"label": "Stay abroad and invest CHF 400/month",
            "interventions": [_iv("monthly_investment", "set", 400)],
            "assumptions_ref": ["AS-market-return", "AS-market-vol"]},
    "3.3": {"label": "Master's abroad after 1 year",
            "interventions": [_iv("monthly_net_income", "set", 800, 12, 36),
                              _iv("cash", "one_off", -4000, 12, 13),
                              _iv("monthly_net_income", "set", {"ref": "AS-salary-master-ch"}, 36, HORIZON)],
            "assumptions_ref": ["AS-salary-master-ch"]},
}

# generic children for any deeper node
GENERIC_CHILDREN = [
    ("Invest CHF 300/month in an index fund", [_iv("monthly_investment", "add", 300)], ["AS-market-return", "AS-market-vol"]),
    ("Cut other expenses by CHF 200/month", [_iv("monthly_other_expenses", "add", -200)], []),
    ("Take a 6-month break next year", [_iv("monthly_net_income", "set", 0, 12, 18)], []),
]


def parent_of(node_id: str) -> str | None:
    if node_id == "0":
        return None
    return node_id.rsplit(".", 1)[0] if "." in node_id else "0"


def get_node(node_id: str) -> dict:
    if node_id in TREE:
        n = TREE[node_id]
    else:
        idx = int(node_id.rsplit(".", 1)[-1]) - 1
        if not 0 <= idx < len(GENERIC_CHILDREN):
            raise KeyError(node_id)
        label, ivs, refs = GENERIC_CHILDREN[idx]
        n = {"label": label, "interventions": ivs, "assumptions_ref": refs}
    return {"node_id": node_id, "parent_id": parent_of(node_id), **copy.deepcopy(n)}


def children_ids(node_id: str) -> list[str]:
    prefix = "" if node_id == "0" else node_id + "."
    return [f"{prefix}{i}" for i in (1, 2, 3)]


def ancestors(node_id: str) -> list[str]:
    """Root..node inclusive."""
    chain = []
    cur: str | None = node_id
    while cur is not None:
        chain.append(cur)
        cur = parent_of(cur)
    return list(reversed(chain))


# ---------------------------------------------------------------- simulation
def _resolve(value, vals):
    if isinstance(value, dict) and "ref" in value:
        return vals[value["ref"]] * float(value.get("scale", 1))
    return float(value)


def _series(profile: dict, interventions: list[dict], vals: dict) -> dict[str, np.ndarray]:
    s = {
        "monthly_net_income": np.full(HORIZON, float(profile.get("monthly_net_income", 0))),
        "monthly_rent": np.full(HORIZON, float(profile.get("monthly_rent", 0))),
        "monthly_other_expenses": np.full(HORIZON, float(profile.get("monthly_other_expenses", 0))),
        "monthly_investment": np.zeros(HORIZON),
        "monthly_debt_payment": np.zeros(HORIZON),
        "one_off": np.zeros(HORIZON),
        "borrow": np.zeros(HORIZON),
    }
    for liab in profile.get("liabilities") or []:
        s["monthly_debt_payment"] += float(liab.get("monthly_payment", 0))
    for iv in interventions:
        a, b = int(iv.get("from_month", 0)), int(iv.get("to_month", HORIZON))
        v = _resolve(iv["value"], vals)
        op, p = iv["op"], iv["param"]
        if op == "one_off":
            s["one_off"][a] += v
        elif op == "borrow":
            s["borrow"][a] += v
        elif op == "set":
            s[p][a:b] = v
        elif op == "add":
            s[p][a:b] += v
        elif op == "scale":
            s[p][a:b] *= v
    s["monthly_investment"] = np.maximum(s["monthly_investment"], 0)
    s["monthly_other_expenses"] = np.maximum(s["monthly_other_expenses"], 0)
    return s


WEATHER = {
    "recession": "Income -15% for 2 years, markets -20% at month 0",
    "inflation": "Expenses grow 4%/year faster than assumed",
    "market_crash": "Investments -35% at month 6",
    "job_loss": "No income for 6 months starting month 6",
}


def _apply_weather(s: dict, weather: list[str]) -> list[str]:
    applied = []
    t = np.arange(HORIZON)
    for w in weather or []:
        if w == "recession":
            s["monthly_net_income"][:24] *= 0.85
        elif w == "inflation":
            f = (1.04) ** (t / 12)
            s["monthly_rent"] *= f
            s["monthly_other_expenses"] *= f
        elif w == "job_loss":
            s["monthly_net_income"][6:12] = 0
        elif w not in WEATHER:
            continue
        applied.append(w)
    return applied


def _run(profile, s, vals, weather, n_paths, rng):
    """Vectorised paths. Path 0 of a deterministic run = no noise."""
    cash0 = float(profile.get("cash", 0))
    inv0 = sum(float(a.get("value", 0)) for a in profile.get("assets") or [])
    debt0 = sum(float(l.get("principal", 0)) for l in profile.get("liabilities") or [])
    mu = vals["AS-market-return"] / 12
    sig = vals["AS-market-vol"] / np.sqrt(12)
    loan_r = vals["AS-loan-rate"] / 12
    stochastic = rng is not None

    cash = np.full(n_paths, cash0)
    inv = np.full(n_paths, inv0)
    debt = np.full(n_paths, debt0)
    out_cash = np.empty((n_paths, HORIZON + 1))
    out_nw = np.empty((n_paths, HORIZON + 1))
    out_cash[:, 0], out_nw[:, 0] = cash, cash + inv - debt
    unemployed_left = np.zeros(n_paths, dtype=int)
    flows_in = np.zeros(n_paths)
    flows_out = np.zeros(n_paths)
    for t in range(HORIZON):
        income = np.full(n_paths, s["monthly_net_income"][t])
        exp = np.full(n_paths, s["monthly_rent"][t] + s["monthly_other_expenses"][t])
        r = np.full(n_paths, mu)
        if stochastic:
            lose = (rng.random(n_paths) < vals["AS-job-loss-rate"]) & (income > 2000) & (unemployed_left == 0)
            unemployed_left[lose] = 4
            income = np.where(unemployed_left > 0, income * 0.0, income)
            unemployed_left = np.maximum(unemployed_left - 1, 0)
            exp = exp * (1 + rng.normal(0, vals["AS-expense-noise"], n_paths))
            r = rng.normal(mu, sig, n_paths)
        if "recession" in weather and t == 0:
            inv = inv * 0.8
        if "market_crash" in weather and t == 6:
            inv = inv * 0.65
        pay = np.minimum(s["monthly_debt_payment"][t], debt * (1 + loan_r)) if debt.any() or s["monthly_debt_payment"][t] else 0
        debt = debt * (1 + loan_r) - pay + s["borrow"][t]
        contrib = s["monthly_investment"][t]
        inflow = income + s["borrow"][t] + max(s["one_off"][t], 0)
        outflow = exp + pay + contrib + max(-s["one_off"][t], 0)
        cash = cash + inflow - outflow
        inv = inv * (1 + r) + contrib
        flows_in += inflow
        flows_out += outflow
        out_cash[:, t + 1] = cash
        out_nw[:, t + 1] = cash + inv - debt
    return out_cash, out_nw, flows_in, flows_out


def _r(x):
    return [round(float(v), 2) for v in x]


def simulate(profile: dict, node_id: str, interventions: list[dict], overrides=None, weather=None,
             n_paths: int = N_PATHS, seed: int = SEED) -> dict:
    weather = list(weather or [])
    vals = assumption_values(overrides)
    s = _series(profile, interventions, vals)
    applied = _apply_weather(s, weather)

    det_cash, det_nw, fin, fout = _run(profile, s, vals, applied, 1, None)
    det_cash, det_nw = det_cash[0], det_nw[0]
    rng = np.random.default_rng(seed)
    mc_cash, mc_nw, _, _ = _run(profile, s, vals, applied, n_paths, rng)

    neg = np.where(det_cash[1:] < 0)[0]
    first_neg = int(neg[0]) if len(neg) else None
    monthly_exp0 = s["monthly_rent"][0] + s["monthly_other_expenses"][0]
    liquidity_months = float(det_cash[0] / monthly_exp0) if monthly_exp0 > 0 else 99.0

    as_of_year = int(str(profile.get("as_of", "2025-01-01"))[:4])
    goal_prob = {}
    for g in profile.get("goals") or []:
        y, m = int(g["target_date"][:4]), int(g["target_date"][5:7])
        idx = min(max((y - as_of_year) * 12 + m, 0), HORIZON)
        goal_prob[g["name"]] = round(float((mc_cash[:, idx] >= float(g["target"])).mean()), 3)

    debt_ratio = float(np.mean(s["monthly_debt_payment"][:12] / np.maximum(s["monthly_net_income"][:12], 1)))
    h_liq = 0.0 if first_neg is not None else min(liquidity_months / 6, 1.0)
    h_debt = max(0.0, 1 - debt_ratio / 0.35)
    h_goals = float(np.mean(list(goal_prob.values()))) if goal_prob else 0.5
    score = round(0.4 * h_liq + 0.2 * h_debt + 0.4 * h_goals, 3)

    # sensitivity: +10% on each assumption used by this run (deterministic)
    base_final = float(det_nw[-1])
    sens = []
    for aid in ["AS-market-return", "AS-salary-junior-ch", "AS-salary-master-ch", "AS-salary-abroad",
                "AS-tuition-semester", "AS-relocation-cost", "AS-loan-rate"]:
        ov = [{"id": k, "value": v} for k, v in vals.items()]
        ov = [o if o["id"] != aid else {"id": aid, "value": o["value"] * 1.1} for o in ov]
        v2 = assumption_values(ov)
        s2 = _series(profile, interventions, v2)
        _apply_weather(s2, weather)
        _, nw2, _, _ = _run(profile, s2, v2, applied, 1, None)
        d = round(float(nw2[0][-1]) - base_final, 2)
        if abs(d) > 0.005:
            sens.append({"assumption_id": aid, "change": "+10%", "delta_final_net_worth": d})
    sens.sort(key=lambda x: -abs(x["delta_final_net_worth"]))

    identity_ok = bool(abs(det_cash[-1] - (det_cash[0] + fin[0] - fout[0])) < 0.01)
    checks = [
        {"name": "cash_flow_identity", "passed": identity_ok,
         "detail": "final_cash == opening_cash + inflows - outflows"},
        {"name": "horizon_length", "passed": len(det_cash) == HORIZON + 1},
        {"name": "finite_values", "passed": bool(np.isfinite(mc_nw).all())},
        {"name": "bands_ordered", "passed": True},
    ]
    p10, p50, p90 = np.percentile(mc_nw, [10, 50, 90], axis=0)
    checks[3]["passed"] = bool((p10 <= p50 + 1e-9).all() and (p50 <= p90 + 1e-9).all())

    key = json.dumps([profile, node_id, interventions, vals, weather, n_paths, seed], sort_keys=True, default=str)
    trace_id = "sim-" + hashlib.sha1(key.encode()).hexdigest()[:10]
    return {
        "node_id": node_id,
        "engine": "mock",
        "seed": seed,
        "n_paths": n_paths,
        "horizon_months": HORIZON,
        "weather": applied,
        "deterministic": {"cash": _r(det_cash), "net_worth": _r(det_nw)},
        "bands": {"net_worth": {"p10": _r(p10), "p50": _r(p50), "p90": _r(p90)}},
        "metrics": {
            "final_net_worth_p50": round(float(p50[-1]), 2),
            "final_net_worth_deterministic": round(base_final, 2),
            "min_cash": round(float(det_cash.min()), 2),
            "first_negative_month": first_neg,
            "goal_probability": goal_prob,
            "liquidity_months": round(liquidity_months, 2),
        },
        "health": {"score": score,
                   "components": {"liquidity": round(h_liq, 3), "debt": round(h_debt, 3), "goals": round(h_goals, 3)}},
        "sensitivity": sens,
        "checks": checks,
        "trace_id": trace_id,
    }


def node_interventions(node_id: str) -> list[dict]:
    ivs = []
    for nid in ancestors(node_id):
        ivs.extend(get_node(nid)["interventions"])
    return ivs


def expand(profile: dict, path: list[str], overrides=None, weather=None) -> dict:
    """Visible nodes = root + chosen path + siblings of the last chosen node + its children."""
    path = [p for p in (path or []) if p and p != "0"]
    for i, p in enumerate(path):  # path must be a chain
        want_parent = "0" if i == 0 else path[i - 1]
        if parent_of(p) != want_parent:
            raise ValueError(f"path is not a chain at {p!r} (parent should be {want_parent!r})")
        get_node(p)
    current = path[-1] if path else "0"
    visible: list[tuple[str, str]] = [("0", "chosen")] + [(p, "chosen") for p in path]
    if path:
        visible += [(sid, "sibling") for sid in children_ids(parent_of(current)) if sid != current]
    visible += [(cid, "child") for cid in children_ids(current)]

    nodes = []
    for nid, status in visible:
        n = get_node(nid)
        n["status"] = status
        n["depth"] = 0 if nid == "0" else nid.count(".") + 1
        n["result"] = simulate(profile, nid, node_interventions(nid), overrides, weather)
        nodes.append(n)
    return {"current": current, "path": ["0"] + path, "nodes": nodes,
            "assumptions": assumptions_list(overrides), "weather_options": WEATHER}
