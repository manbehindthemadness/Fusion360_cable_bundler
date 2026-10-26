"""
Check generic seed ranking and its independent scalar length projection contract.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, unit
from experiments.experiment_ribbon_cap_transition.director_fields import DirectorField
from experiments.experiment_ribbon_cap_transition.director_rotation_transport import (
    integrate_rotation,
)
from experiments.experiment_ribbon_cap_transition.director_route_objective import free_penalties
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.director_seed_bank import candidates, ranked_seed
from experiments.experiment_ribbon_cap_transition.director_shooting import FREE, field_for, residual
from experiments.experiment_ribbon_cap_transition.director_transport import DirectorPath
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def _checkpoint() -> None:
    """
    Bound runtime separately in live experiments.
    """


def test_ranked_generic_shape_recovers_scale_without_reference_path_input() -> None:
    """
    Supply only a pose authored from a unit-rotation shape and recover its length.
    """
    field = DirectorField("author", 120, (math.pi / 2, 0, 0, 0), (0.4, -0.4, 0, 0))
    witness = integrate_rotation(field, 64, _checkpoint)
    last = witness.states[-1]
    case = EndpointCase(
        "anonymous",
        Vector3(0, 0, 0),
        Vector3(*last[:3]),
        Vector3(1, 0, 0),
        unit(Vector3(*last[3:6])),
        Vector3(0, 1, 0),
        unit(Vector3(*last[6:9])),
    )

    def build(values: tuple[float, ...]) -> RoutingField:
        """
        Bind only the target and the shared routing coordinate interpretation.
        """
        return field_for(case, values, policy=FREE)

    def score(path: DirectorPath) -> tuple[float, ...]:
        """
        Use named endpoint and current geometry policies without fixture lookup.
        """
        return residual(case, path) + free_penalties(case, path)

    selected, metrics = ranked_seed(case, (), build, score, _checkpoint)
    assert metrics["seed_screenings"] == len(candidates()) == 44
    assert metrics["seed_score"] < 1e-20
    assert abs(build(selected).length_mm - 120) < 1e-9
