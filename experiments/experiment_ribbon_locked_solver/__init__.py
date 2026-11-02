"""
Expose both gym solver versions and their configurable aesthetic second pass.
"""

from .settings import VERSION, Settings
from .solver import Result, solve
from .solver_v2 import solve as solve_v2
from .versions import DEFAULT_VERSION, V2

__all__ = ["VERSION", "V2", "DEFAULT_VERSION", "Settings", "Result", "solve", "solve_v2"]
