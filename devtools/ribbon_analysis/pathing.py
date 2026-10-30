"""
Share versioned pathing-rule identities across controls, archives and numerical workers.
"""

from enum import Enum


class PathRules(Enum):
    """
    Distinguish the two-rule pathing experiment from reproducible historical policies.
    """

    MACARONI = "macaroni + no lateral bending"
    HISTORICAL = "historical"
