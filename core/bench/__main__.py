"""python -m core.bench [--json] [--params FILE]: calibration / benchmark report (#42)."""
import json
import sys

from .harness import load_params, report


def main() -> None:
    overrides = None
    if "--params" in sys.argv:
        overrides, _ = load_params(sys.argv[sys.argv.index("--params") + 1])
    r = report(overrides=overrides)
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2))
        return
    t, v = r["targets"], r["targets_verified_only"]
    print(f"Public targets: loss {v['loss']} over {v['targets_used']} verified targets; "
          f"{t['loss']} over {t['targets_used']} verified + to_verify (of {t['targets_total']})")
    for p in t["parts"]:
        mark = f"z={p['z']:+.2f}" if p.get("used") else p.get("reason", "")
        print(f"  {p['id']:<28} {p['status']:<10} target={p['target']} model={p['model']}  {mark}")
    if isinstance(r.get("ubs"), str):
        print(r["ubs"])
        return
    L = r["ledger"]
    print(f"\nUBS ledger consistency: {'PASS' if L['passed'] else 'FAIL'} over {L['profiles']} profiles x months "
          f"({L['months']}); violations {L['violations']}; max errors {L['max_abs_error_chf']}")
    print("\nImplied by the UBS synthetic generator vs ours:")
    for row in r["implied"]["rows"]:
        print(f"  {row['quantity']:<52} UBS {row['ubs_median']}  ours {row['ours']} ({row['ours_from']})")
    print("\nUBS scenario assumptions vs our tree:")
    for row in r["scenario_assumptions"]:
        print(f"  {row['parameter']:<22} UBS Alexia {row['ubs_alexia']}  UBS median {row['ubs_all_profiles_median']}  "
              f"ours {row['ours']} {row['ours_range']}")
    for key in ("replay_zero", "replay_swiss"):
        x = r[key]
        print(f"\nReplay ({x['world']} world): final-cash error in months of budget median "
              f"{x['final_cash_error_months_of_budget']['median']} (p10 {x['final_cash_error_months_of_budget']['p10']}, "
              f"p90 {x['final_cash_error_months_of_budget']['p90']}); mean |path error| {x['mean_abs_path_error_months_of_budget']}")
    print("\nDrift vs the UBS ledgers (median final-cash error, months of budget):")
    for row in r["drift"]:
        print(f"  {row['step']:<32} {row['final_cash_error_months_of_budget']:+.3f}")


if __name__ == "__main__":
    main()
