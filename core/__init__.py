"""cigala financial engine. Pure functions, JSON in -> JSON out. The LLM never computes.

Entry points for api/ (signatures match api/engine.py):
- expand(profile, path, assumptions=None, weather=None)  -> visible tree nodes, each with a SimulationResult
- simulate(profile, node, assumptions=None, weather=None) -> one SimulationResult
- node_info(node_id), assumptions_list(overrides), weather_catalog()
Lower level: simulate_node(profile, interventions, ...), load_profile(), load_tree().
"""
from .assumptions import build_assumptions, default_assumptions
from .simulate import ENGINE_VERSION, sensitivity_analysis, simulate_node
from .tree import (assumptions_list, expand, load_profile, load_tree, node_info, simulate,
                   visible_nodes)
from .weather import weather_catalog

__all__ = ["ENGINE_VERSION", "assumptions_list", "build_assumptions", "default_assumptions", "expand",
           "load_profile", "load_tree", "node_info", "sensitivity_analysis", "simulate", "simulate_node",
           "visible_nodes", "weather_catalog"]
