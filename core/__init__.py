"""cigala financial engine. Pure functions, JSON in -> JSON out. The LLM never computes.

Entry points for api/ (signatures match api/engine.py):
- expand(profile, path, assumptions=None, weather=None)  -> visible tree nodes, each with a SimulationResult
- simulate(profile, node, assumptions=None, weather=None) -> one SimulationResult
- node_info(node_id), assumptions_list(overrides), weather_catalog()
- report_data(profile, path, assumptions=None, weather=None) -> every number of the path report
- explore(profile, path, assumptions=None, weather=None) -> exploration + tornado of the current node (lazy)
- warm(profile=None) -> precompute the whole tree into the cache (start-up)
- payslip(gross_month, age, assumptions=None) -> one month's Swiss payroll deductions (gross -> net)
- validation() -> live self-checks (identities, reproducibility, monotonicity, isolation, UBS kit) with evidence
Lower level: simulate_node(profile, interventions, ...), load_profile(), load_tree().
"""
from .assumptions import build_assumptions, default_assumptions
from .simulate import ENGINE_VERSION, sensitivity_analysis, simulate_node
from .tree import (assumptions_list, expand, explore, warm, load_profile, load_tree, node_info, simulate,
                   visible_nodes)
from .report import report_data
from .payroll import payslip as _payslip


def payslip(gross_month: float, age: float, assumptions=None) -> dict:
    """One month's payroll at today's prices: AHV/IV/EO, ALV, NBU, BVG employee/employer, net.
    ``assumptions`` are optional overrides (``{id_or_param: value}`` or the API list form)."""
    return _payslip(gross_month, age, build_assumptions([], assumptions).values())


from .validation import validation
from .weather import weather_catalog

__all__ = ["ENGINE_VERSION", "assumptions_list", "build_assumptions", "default_assumptions", "expand",
           "load_profile", "load_tree", "node_info", "payslip", "report_data", "explore", "warm", "validation", "sensitivity_analysis", "simulate", "simulate_node",
           "visible_nodes", "weather_catalog"]
