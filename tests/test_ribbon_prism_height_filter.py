"""
Prune only disjoint negative prisms while preserving strict witnesses, comparison charges and cancellation.
"""

from __future__ import annotations

import math
from dataclasses import replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, cross
from experiments.experiment_ribbon_fold_route import contact_phase_core
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.contact_phase_core import CoreProbe, ProfileProbe
from experiments.experiment_ribbon_fold_route.contact_phase_prism import (
    FlatCore,
    height_separated,
    intersection_vertices,
    prepare,
)
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_phase_core_discovery import _flat_crossing


def _pair(
    scale: float = 1.0,
    angle: float = math.pi / 4,
    offset: float = 2.0,
    translation: Vector3 | None = None,
) -> tuple[PlacedPiece, PlacedPiece]:
    """
    Author parallel rotated slabs whose world boxes can overlap despite a genuine thickness gap.
    """
    tangent = Vector3(math.cos(angle), math.sin(angle), 0)
    width = Vector3(0, 0, 1)
    normal = cross(tangent, width)
    origin = translation if translation is not None else Vector3(0, 0, 0)
    first = PlacedPiece(
        Pose(origin, tangent, width), Straight(10 * scale), "authored height-filter control"
    )
    second = replace(
        first, pose=replace(first.pose, origin=origin.translated(normal, offset * scale))
    )
    return first, second


def _cores(
    pieces: tuple[PlacedPiece, PlacedPiece], scale: float = 1.0
) -> tuple[FlatCore, FlatCore]:
    """
    Use the unchanged valley-core factory, retaining its actual polygon and profile height.
    """
    first, second = (prepare(piece, FlatPhase.STRAIGHT, 1, scale) for piece in pieces)
    assert first is not None and second is not None
    return first, second


@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
@pytest.mark.parametrize("angle", (-0.4, 0.0, math.pi / 4))
@pytest.mark.parametrize(
    "offset,expected", ((0.1, False), (0.6, False), (0.600000000001, False), (2, True))
)
def test_only_strict_full_prism_height_separation_skips_clipping(
    scale: float, angle: float, offset: float, expected: bool
) -> None:
    """
    Overlap, contact and roundoff-scale gaps defer; a rejected pair has an empty original intersection.
    """
    cores = _cores(_pair(scale, angle, offset), scale)
    assert height_separated(*cores, lambda: None) is expected
    assert height_separated(*reversed(cores), lambda: None) is expected
    if expected:
        assert intersection_vertices(*cores, lambda: None) == ()


def test_large_translation_declines_acceleration_instead_of_claiming_precision() -> None:
    """
    Coordinate-scale padding must defer when it exceeds the available numerical separation.
    """
    cores = _cores(_pair(translation=Vector3(1e14, -2e14, 3e14)))
    assert not height_separated(*cores, lambda: None)


@pytest.mark.parametrize("invalid", ("height", "origin", "normal", "relative_overflow"))
def test_nonfinite_projection_data_falls_through_without_a_negative_decision(invalid: str) -> None:
    """
    Unknown arithmetic cannot become a separating proposal filter result.
    """
    first, second = _cores(_pair())
    if invalid == "height":
        first = replace(first, half_height=math.inf)
    elif invalid == "origin":
        first = replace(first, placement=replace(first.placement, origin=(math.inf, 0, 0)))
    elif invalid == "normal":
        first = replace(first, placement=replace(first.placement, normal=(math.nan, 0, 0)))
    else:
        first = replace(first, placement=replace(first.placement, origin=(-1e308, 0, 0)))
        second = replace(second, placement=replace(second.placement, origin=(1e308, 0, 0)))
    assert not height_separated(first, second, lambda: None)


@pytest.mark.parametrize("stop_at", (1, 2))
def test_cancellation_during_normal_checks_never_returns_a_filter_result(stop_at: int) -> None:
    """
    Both checkpoints preserve caller cancellation even for overlapping prisms.
    """
    cores = _cores(_pair(offset=0.1))
    checks = Mock(side_effect=[None] * (stop_at - 1) + [TimeoutError("caller stopped")])
    with pytest.raises(TimeoutError, match="caller stopped"):
        height_separated(*cores, checks)
    assert checks.call_count == stop_at


@pytest.mark.parametrize("probe_type", (CoreProbe, ProfileProbe))
def test_disjoint_world_box_overlap_keeps_comparison_charge_but_avoids_edges(
    monkeypatch: pytest.MonkeyPatch, probe_type: type[CoreProbe]
) -> None:
    """
    The accelerator changes only negative edge work, not the phase pool or inverse authority.
    """
    first, second = _pair()
    cores = _cores((first, second))
    assert all(a[0] <= b[1] and b[0] <= a[1] for a, b in zip(cores[0].bounds, cores[1].bounds))
    source = _route((Straight(10), Straight(1), Straight(10)))
    source = replace(source, pieces=(first, source.pieces[1], second))
    guarded = probe_type()
    observed = guarded(source, 0, 2, 1, lambda: None)
    with monkeypatch.context() as patch:
        patch.setitem(vars(contact_phase_core), "height_separated", lambda *_args: False)
        original = probe_type()
        expected = original(source, 0, 2, 1, lambda: None)
    assert observed == expected and observed.witness is None and observed.pairs_checked == 1
    assert guarded.comparisons == original.comparisons == 1
    assert guarded.edges == 0 < original.edges
    assert guarded.height_filter_attempts == guarded.height_rejected_proposals == 1
    assert guarded.inverse_tests == original.inverse_tests == 0


@pytest.mark.parametrize("phase", (FlatPhase.BEFORE, FlatPhase.AFTER))
@pytest.mark.parametrize("probe_type", (CoreProbe, ProfileProbe))
def test_actual_crossing_witness_matches_the_original_clipper(
    monkeypatch: pytest.MonkeyPatch, phase: FlatPhase, probe_type: type[CoreProbe]
) -> None:
    """
    True flat-phase crossings retain their exact point, ordered material coordinates and pair charge.
    """
    source = _flat_crossing(3, 0.75, -1, 1, phase)
    guarded = probe_type()(source, 0, 2, 32, lambda: None)
    with monkeypatch.context() as patch:
        patch.setitem(vars(contact_phase_core), "height_separated", lambda *_args: False)
        original = probe_type()(source, 0, 2, 32, lambda: None)
    assert guarded.witness is not None and guarded == original
