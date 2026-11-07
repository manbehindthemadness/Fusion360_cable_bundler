"""
Verify complete local flat-region guidance and one evidence-derived free incident reflection.
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, dot
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_feature_insertion.separation import Side, locate
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_separation import (
    FlatSeparation,
    flat_prism,
    flat_span,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.incident_model import IncidentJoints
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import jacobian
from tests.test_ribbon_flat_contact import load_routes


@pytest.fixture(scope="module")
def routes() -> dict[str, FoldRoute]:
    """
    Load the same immutable one-boundary mathematical regression shapes.
    """
    return load_routes()


def test_contact_guidance_covers_whole_profile_intervals_and_flat_extents(
    routes: dict[str, FoldRoute],
) -> None:
    """
    A narrow real crossing produces complete material-region constraints rather than point fibers.
    """
    route = routes["overlap"]
    hit = FlatProbe()(route, 3, 7, 64, None).witness
    assert hit is not None
    model = SignedJoints(route)
    bound = FlatSeparation.create(model, route, hit)
    assert bound is not None
    assert tuple(part.phase for part in bound.parts) == (FlatPhase.BEFORE, FlatPhase.AFTER)
    assert (bound.parts[0].low_q, bound.parts[0].high_q) == (2.25, 3.0)
    assert (bound.parts[1].low_q, bound.parts[1].high_q) == (3.0, 3.075)
    assert max(bound.gap(model.initial, side) for side in Side) < 0
    for tag, part in zip(bound.pair, bound.parts):
        piece = locate(route, model.pieces(model.initial), tag)
        points, _, _ = flat_prism(piece, part)
        for axis in (bound.axis, Vector3(1, 0, 0), Vector3(0, 0, 1)):
            actual = tuple(dot(point, axis) for point in points)
            assert flat_span(piece, part, axis) == pytest.approx(
                (min(actual), max(actual)), abs=1e-10
            )


def test_incident_reflection_frees_angle_bank_and_runways_but_preserves_other_signs(
    routes: dict[str, FoldRoute],
) -> None:
    """
    Reflect one supplied incident ordinal; do not freeze its shape or invent angle candidates.
    """
    source = routes["incident_source"]
    ordinary = SignedJoints(source)
    reflected = IncidentJoints(source, 2)
    assert reflected.indices == ordinary.indices
    changed = [i for i, (a, b) in enumerate(zip(ordinary.initial, reflected.initial)) if a != b]
    assert len(changed) == 1
    angle = changed[0]
    assert reflected.indices[angle] == 9 and reflected.initial[angle] == -ordinary.initial[angle]
    low, high = reflected.bounds(angle)
    assert low <= reflected.initial[angle] <= high
    candidate = reflected.route(reflected.initial)
    assert candidate is not None and reflected.preserves(candidate)
    assert not ordinary.preserves(candidate)
    assert all(math.isfinite(value) for value in reflected.initial)


@pytest.mark.parametrize("ordinal", (-1, 4, True))
def test_invalid_incident_identity_cannot_start_joint_work(
    routes: dict[str, FoldRoute], ordinal: int
) -> None:
    """
    Reject missing or ambiguous incident folds before correction.
    """
    with pytest.raises(ValueError):
        IncidentJoints(routes["incident_source"], ordinal)


@pytest.mark.parametrize(
    "field,value",
    (
        ("maximum_updates", 0),
        ("maximum_updates", True),
        ("maximum_updates", 5),
        ("remaining_pairs", 2049),
        ("remaining_pairs", 0),
        ("maximum_cpu_seconds", 0.36),
        ("maximum_cpu_seconds", True),
        ("maximum_seconds", 2.1),
        ("maximum_length_mm", float("nan")),
        ("minimum_straight_mm", 0),
    ),
)
def test_flat_contact_correction_cannot_enlarge_or_disable_work_limits(
    routes: dict[str, FoldRoute],
    field: str,
    value: Any,
) -> None:
    """
    Reject malformed or renewed allowances before constructing any joint or terminal constraint.
    """
    options = {
        "maximum_updates": 3,
        "remaining_pairs": 610,
        "maximum_cpu_seconds": 0.2,
        "maximum_seconds": 1.0,
        "maximum_length_mm": 100.0,
        "minimum_straight_mm": 1e-5,
        field: value,
    }
    with pytest.raises(ValueError):
        joint_contact.recover(
            routes["overlap"],
            Report("unresolved", 0),
            Mock(spec=Gate),
            lambda: None,
            lambda e: None,
            **options,
        )


def test_shared_joint_derivatives_preserve_bounds_and_fixed_native_slots() -> None:
    """
    Keep the established one-sided finite difference at bounds and avoid moving fixed slots.
    """
    model = Mock(spec=MovableBends)
    model.bounds.return_value = (0.0, 1.0)
    calls = []
    checkpoint = Mock()

    def equations(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Retain every probed coordinate vector for the fixed-slot contract.
        """
        calls.append(values)
        x, y = values
        return x + y - 1, x**2 + 2 * y

    result = jacobian(model, (0.0, 0.0), equations, 2, {1}, checkpoint)
    assert result[0] == pytest.approx((1.0, 0.0))
    assert result[1] == pytest.approx((1e-5, 0.0))
    assert calls == [(0.0, 0.0), (1e-5, 0.0)]
    assert checkpoint.call_count == 2
