"""Regenerate the example JSON files used in docs/contracts.md.

    python -m core.examples.generate
"""
import json
from pathlib import Path

from core import expand, load_profile, simulate

HERE = Path(__file__).resolve().parent


def main() -> None:
    profile = load_profile()
    (HERE / "expand_alexia_root.json").write_text(json.dumps(expand(profile, [])), encoding="utf-8")
    (HERE / "expand_alexia_2.json").write_text(json.dumps(expand(profile, ["2"])), encoding="utf-8")
    (HERE / "simulate_alexia_2_recession.json").write_text(
        json.dumps(simulate(profile, {"node_id": "2"}, None, ["recession"])), encoding="utf-8")
    print("written to", HERE)


if __name__ == "__main__":
    main()
