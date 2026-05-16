"""Scenario registry.

Add a new scenario by:
  1. Creating ``src/scenarios/<slug>.py`` with a class whose ``meta`` is a
     ``ScenarioMeta`` and which implements ``compute_windows(monthly, horizon)``.
  2. Importing it here and appending an instance to ``SCENARIOS``.
  3. Adding the matching ``docs/scenarios/<slug>.html`` page and a notebook.
  4. Re-running ``python -m src.export`` and ``python -m src.report``.
"""
from __future__ import annotations

from .annual_dca import AnnualDCA100
from .base import Scenario, ScenarioMeta
from .lump_sum import LumpSum1k

SCENARIOS: list[Scenario] = [LumpSum1k(), AnnualDCA100()]

__all__ = ["SCENARIOS", "Scenario", "ScenarioMeta"]
