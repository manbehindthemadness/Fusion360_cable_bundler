"""
Challenge the sampled search filter independently of endpoint fit success.
"""

import math

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.director_edge_filter import EdgeFeasibility
from experiments.experiment_ribbon_cap_transition.director_fields import DirectorField
from experiments.experiment_ribbon_cap_transition.director_rotation_transport import (
    integrate_rotation,
)
from experiments.experiment_ribbon_cap_transition.director_route_objective import free_penalties
from experiments.experiment_ribbon_cap_transition.director_transport import DirectorPath
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def _path_and_targets(field: DirectorField) -> tuple[DirectorPath, EndpointCase]:
    """
    Author small forward controls without supplying a witness to a routing solver.
    """
    path = integrate_rotation(field, 512, lambda: None)
    last = path.states[-1]
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase(
        "filter-control",
        Vector3(0, 0, 0),
        Vector3(*last[:3]),
        x,
        Vector3(*last[3:6]),
        y,
        Vector3(*last[6:9]),
        field.lines,
        field.diameter_mm,
    )
    return path, case


def test_regular_straight_control_is_admissible() -> None:
    """
    Leave an ordinary straight ribbon available to the bounded search.
    """
    field = DirectorField("straight", 80, (0, 0, 0, 0), (0, 0, 0, 0))
    path, case = _path_and_targets(field)
    assert EdgeFeasibility(case)(path)


def test_both_edges_matter_when_center_and_existing_penalties_are_clean() -> None:
    """
    Reject excessive companion-edge curvature despite an acceptable outside proxy.
    """
    half, length = 14.4, 100.0
    reach = math.hypot(half, 0.75)
    amplitude = 0.6 * length / (2 * math.pi * half)
    field = DirectorField(
        "companion-edge",
        length,
        (0.4 * length / reach, 0, 0, 0),
        (0, 0, amplitude, 0),
    )
    path, case = _path_and_targets(field)
    assert not any(free_penalties(case, path))
    k, _, eta_s = field.sample(0)
    assert abs(k) * reach / (1 + half * abs(eta_s)) < 0.8
    assert abs(k) * reach / (1 - half * abs(eta_s)) > 0.8
    assert not EdgeFeasibility(case)(path)
    floor = EdgeFeasibility(case).minimum_length_ratio(path)
    assert floor > 1
    expanded = DirectorField(
        field.name,
        field.length_mm * floor,
        field.bending,
        field.ruling,
        field.lines,
        field.diameter_mm,
    )
    for i in range(129):
        bend, _, gradient = expanded.sample(i / 128)
        assert abs(bend) * reach / (1 - half * abs(gradient)) < 0.78


def test_folded_zero_curvature_map_cannot_pass() -> None:
    """
    Reject material-map reversal even where every regular path curvature is zero.
    """
    field = DirectorField("fold", 80, (0, 0, 0, 0), (0, 0, 2, 0))
    path, case = _path_and_targets(field)
    assert not EdgeFeasibility(case)(path)
