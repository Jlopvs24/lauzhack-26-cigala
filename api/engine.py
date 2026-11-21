"""Single entry point to the financial engine.

Uses core/ (thread 1) when it is importable and exposes the contract v1 functions,
otherwise the mock in api/mock_engine.py. The rest of api/ only talks to this module,
so it works the same on both engines.
"""
from __future__ import annotations

import logging

from api import mock_engine

log = logging.getLogger("api.engine")

_REQUIRED = ("expand", "simulate", "node_info", "assumptions_list")
try:  # pragma: no cover - depends on thread 1
    import core  # type: ignore

    _CORE = core if all(hasattr(core, f) for f in _REQUIRED) else None
except Exception:  # noqa: BLE001
    _CORE = None

ENGINE_NAME = "core" if _CORE else "mock"
log.info("engine: %s", ENGINE_NAME)


def expand(profile: dict | None, path: list[str], assumptions=None, weather=None) -> dict:
    if _CORE:
        return _CORE.expand(profile, path, assumptions, weather)
    return mock_engine.expand(profile or default_profile(), path, assumptions, weather)


def simulate(profile: dict | None, node: dict, assumptions=None, weather=None) -> dict:
    if _CORE:
        if node.get("interventions") is None:
            _CORE.node_info(str(node.get("node_id")))  # unknown id -> ValueError (422), not a blank node
        return _CORE.simulate(profile, node, assumptions, weather)
    profile = profile or default_profile()
    node_id = node.get("node_id", "x")
    if node.get("interventions") is not None and node_id not in mock_engine.TREE:
        ivs = mock_engine.node_interventions(node["parent_id"]) if node.get("parent_id") else []
        ivs = ivs + node["interventions"]
    else:
        mock_engine.get_node(node_id)  # KeyError if unknown
        ivs = mock_engine.node_interventions(node_id)
    return mock_engine.simulate(profile, node_id, ivs, assumptions, weather)


def node_info(node_id: str) -> dict:
    """{node_id, parent_id, label, interventions, children: [ids]}. Raises KeyError/ValueError if unknown."""
    if _CORE:
        return _CORE.node_info(node_id)
    n = mock_engine.get_node(node_id)
    n["children"] = mock_engine.children_ids(node_id)
    return n


def path_to(node_id: str) -> list[str]:
    """Chosen path (without the root) that leads to node_id: "2.2" -> ["2", "2.2"]."""
    chain = []
    cur = node_info(node_id)
    while cur.get("parent_id") is not None:
        chain.append(cur["node_id"])
        cur = node_info(cur["parent_id"])
    return list(reversed(chain))


def assumptions(overrides=None) -> list[dict]:
    if _CORE:
        return _CORE.assumptions_list(overrides)
    return mock_engine.assumptions_list(overrides)


def default_profile() -> dict:
    import json
    from pathlib import Path

    if _CORE and hasattr(_CORE, "load_profile"):
        return _CORE.load_profile()
    return json.loads((Path(__file__).parent / "fixtures" / "alexia.json").read_text(encoding="utf-8"))
