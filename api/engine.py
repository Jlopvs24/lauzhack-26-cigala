"""Single entry point to the financial engine.

Uses core/ (thread 1) when it is importable and exposes the expected functions,
otherwise the mock in api/mock_engine.py. Every result says which engine ran.
"""
from __future__ import annotations

import logging

from api import mock_engine

log = logging.getLogger("api.engine")

try:  # pragma: no cover - depends on thread 1
    import core  # type: ignore

    _CORE = core if all(hasattr(core, f) for f in ("expand", "simulate")) else None
except Exception:  # noqa: BLE001
    _CORE = None

ENGINE_NAME = "core" if _CORE else "mock"
log.info("engine: %s", ENGINE_NAME)


def expand(profile: dict, path: list[str], assumptions=None, weather=None) -> dict:
    if _CORE:
        return _CORE.expand(profile, path, assumptions, weather)
    return mock_engine.expand(profile, path, assumptions, weather)


def simulate(profile: dict, node: dict, assumptions=None, weather=None) -> dict:
    if _CORE:
        return _CORE.simulate(profile, node, assumptions, weather)
    node_id = node.get("node_id", "x")
    if node.get("interventions") is not None and node_id not in mock_engine.TREE:
        ivs = node["interventions"]
    else:
        ivs = mock_engine.node_interventions(node_id)
    return mock_engine.simulate(profile, node_id, ivs, assumptions, weather)


def node_info(node_id: str) -> dict:
    return mock_engine.get_node(node_id)


def assumptions(overrides=None) -> list[dict]:
    return mock_engine.assumptions_list(overrides)
