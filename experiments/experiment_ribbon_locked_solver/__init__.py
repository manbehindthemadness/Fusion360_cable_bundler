"""
Expose the selected joint material-fold solver and configurable aesthetic second pass.
"""

from .settings import VERSION, Settings
from .solver import Result, solve

__all__ = ["VERSION", "Settings", "Result", "solve"]
