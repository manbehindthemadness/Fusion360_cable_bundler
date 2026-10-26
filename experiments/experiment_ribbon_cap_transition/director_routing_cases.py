"""
Reserve inverse-routing targets without exposing reference paths to the solver.
"""

from __future__ import annotations

import math

from .director_fields import DirectorField


def reserved_fields() -> tuple[DirectorField, ...]:
    """
    Freeze six new target-authoring witnesses before endpoint-solver development.

    Only endpoint poses/dimensions may enter solve(). The witness fields certify
    reference reachability within this model,not physical or native compliance.
    Check all witness policies before interpreting route success statistics.
    """
    return (
        DirectorField(
            "R01_hidden_gentle_spatial", 80, (math.pi / 2, 0, 0, 0), (0.175, -0.175, 0, 0)
        ),
        DirectorField("R02_hidden_mixed", 110, (1.3, -0.4, 0.6, 0.3), (0.2, -0.2, 0.2, 0.1)),
        DirectorField("R03_hidden_reversal", 100, (0, 0, 4, 0), (0, 0, 0.6, 0)),
        DirectorField("R04_hidden_negative_bank", 95, (-2, 0, 0.4, 0), (0.3, -0.3, 0.15, 0)),
        DirectorField("R05_hidden_return", 130, (math.pi, -math.pi, 0, 0), (0.075, -0.075, 0, 0)),
        DirectorField("R06_hidden_twisting_entry", 85, (1.8, 0, -0.3, 0.2), (0, 0, 0.45, 0)),
    )
