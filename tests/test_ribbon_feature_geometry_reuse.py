"""
Verify exact feature dependencies without replaying saved routing geometry.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import cross, dot, unit
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, locate
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import feature_plane
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import jacobian
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route


def _plane(family: int = 0, side: Side = Side.BEFORE) -> FeaturePlane:
    """
    Author four independent folds, selecting complete leading fold and internal straight material.
    """
    source = _route(
        (
            Straight(2),
            fold(2, 1.2, 0.8, 0.2, 1),
            Straight(3),
            fold(2, 1.2, -1.0, -0.3, 1),
            Straight(4),
            fold(2, 1.2, 1.2, 0.1, 1),
            Straight(3),
            fold(2, 1.2, -0.7, 0.4, 1),
            Straight(2),
        )
    )
    model = SignedJoints(source)
    box = Hardware.create(source.targets, Dimensions.scaled(source.targets)).boxes[0]
    return FeaturePlane(
        model, Region(0, False), (Region(0, False), Region(1, True)), box, family, side
    )


def _raw(plane: FeaturePlane, values: tuple[float, ...]) -> float:
    """
    Evaluate the original uncached axis/span/corner arithmetic at the complete validated coordinates.
    """
    pieces = plane.model.pieces(values)
    source = plane.model.original
    reference = locate(source, pieces, plane.reference)
    assert 0 <= plane.family < 6
    axes = plane.box.axes + (
        reference.pose.tangent,
        reference.pose.width,
        unit(cross(reference.pose.tangent, reference.pose.width)),
    )
    axis = unit(axes[plane.family])
    cell = Cell(
        0,
        Span(0, 1),
        Span(-source.half_width_mm, source.half_width_mm),
        Span(-source.targets.diameter_mm / 2, source.targets.diameter_mm / 2),
    )
    spans = tuple(
        feature_plane.projection(locate(source, pieces, member), cell, axis)
        for member in plane.members
    )
    span = Span(min(part.low for part in spans), max(part.high for part in spans))
    corners = tuple(dot(point, axis) for point in plane.corners)
    gap = span.low - max(corners) if plane.side is Side.AFTER else min(corners) - span.high
    return gap / plane.model.scale


@pytest.mark.parametrize("family", (0, 3, 4, 5))
@pytest.mark.parametrize("side", tuple(Side))
def test_unrelated_suffix_probes_preserve_exact_gap_with_one_actual_member_projection(
    monkeypatch: pytest.MonkeyPatch, family: int, side: Side
) -> None:
    """
    Repeated late perturbations cannot force unchanged leading geometry to reproject.
    """
    plane = _plane(family, side)
    values = plane.model.initial
    probes = [values]
    for index in range(6, len(values)):
        for delta in (-1e-5, 1e-5):
            probes.append(values[:index] + (values[index] + delta,) + values[index + 1 :])
    expected = [_raw(plane, probe) for probe in probes]
    projected = Mock(wraps=feature_plane.projection)
    monkeypatch.setitem(vars(feature_plane), "projection", projected)
    assert [plane.gap(probe) for probe in probes] == expected
    assert projected.call_count == len(plane.members)
    assert len(probes) == 15


@pytest.mark.parametrize(
    "reference,index",
    (
        (Region(0, False), 0),
        (Region(0, False), 1),
        (Region(0, False), 2),
        (Region(0, False), 3),
        (Region(2, False), 4),
    ),
    ids=("pose", "angle", "bank", "member", "axis_reference"),
)
def test_relevant_placement_and_material_changes_receive_new_exact_measurements(
    monkeypatch: pytest.MonkeyPatch, reference: Region, index: int
) -> None:
    """
    Changes to a selected fold, its world pose or an included straight cannot borrow old bounds.
    """
    plane = replace(_plane(3), reference=reference)
    values = plane.model.initial
    changed = values[:index] + (values[index] + 1e-5,) + values[index + 1 :]
    expected = _raw(plane, changed)
    plane.gap(values)
    projected = Mock(wraps=feature_plane.projection)
    monkeypatch.setitem(vars(feature_plane), "projection", projected)
    assert plane.gap(changed) == expected and projected.call_count == len(plane.members)


def test_whole_constrained_derivative_matrix_is_identical_with_fewer_projections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Original finite-difference probes retain every raw row while unchanged prefix dependencies reuse work.
    """
    plane = _plane(5)
    model = plane.model

    def raw(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Evaluate the original complete cap and hardware rows without dependency reuse.
        """
        return model.residual(values) + (_raw(plane, values),)

    def reused(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Change only hardware evaluation reuse, preserving raw cap equations and derivative probes.
        """
        return model.residual(values) + (plane.gap(values),)

    projected = Mock(wraps=feature_plane.projection)
    monkeypatch.setitem(vars(feature_plane), "projection", projected)
    expected = jacobian(
        model, model.initial, raw, 7, frozenset(), lambda: None, admissible=model.admissible
    )
    original_calls = projected.call_count
    projected.reset_mock()
    measured = jacobian(
        model, model.initial, reused, 7, frozenset(), lambda: None, admissible=model.admissible
    )
    assert measured == expected and projected.call_count < original_calls


def test_distinct_planes_and_models_cannot_share_measurements_and_eviction_recomputes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Bound retention belongs to one fixed box/family/side/model, with original arithmetic after eviction.
    """
    plane = _plane()
    values = plane.model.initial
    baseline = plane.gap(values)
    alternatives = (
        replace(plane, side=Side.AFTER),
        replace(plane, family=3),
        replace(
            plane,
            box=Hardware.create(plane.model.original.targets, Dimensions(10, 10, 10)).boxes[1],
        ),
        _plane(),
    )
    expected = [_raw(other, other.model.initial) for other in alternatives]
    projected = Mock(wraps=feature_plane.projection)
    monkeypatch.setitem(vars(feature_plane), "projection", projected)
    assert [other.gap(other.model.initial) for other in alternatives] == expected
    assert projected.call_count == len(plane.members) * len(alternatives)
    for i in range(1, 67):
        plane.gap((values[0] + i * 1e-5,) + values[1:])
    projected.reset_mock()
    assert plane.gap(values) == baseline and projected.call_count == len(plane.members)


def test_suffix_domain_errors_are_not_hidden_by_matching_leading_geometry() -> None:
    """
    Full coordinate validation remains mandatory before an exact dependency-cache hit.
    """
    plane = _plane()
    values = plane.model.initial
    plane.gap(values)
    with pytest.raises(ValueError):
        plane.gap(values[:-1] + (-1.0,))
