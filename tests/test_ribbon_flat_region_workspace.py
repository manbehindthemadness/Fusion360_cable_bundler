"""
Verify bounded shared flat preparation with exact original geometry and projection arithmetic.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, dot, unit
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, TopologyChanged
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase, region
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import feature_plane
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_separation import (
    FlatPart,
    FlatSeparation,
    flat_prism,
    flat_span,
)
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_flat_geometry_reuse import _raw


def _model() -> SignedJoints:
    """
    Author one banked fold between occupied straights, independent of any saved solver input.
    """
    return SignedJoints(_route((Straight(3), fold(2, 1.2, 1.1, 0.3, 1), Straight(5))))


def _bounds(model: SignedJoints) -> tuple[FlatSeparation, ...]:
    """
    Share actual material between different fixed axes and profile heights.
    """
    return tuple(
        FlatSeparation(
            model,
            (Region(0, True), Region(1, True)),
            (FlatPart(FlatPhase.STRAIGHT, -0.6, 0.6, height),) * 2,
            axis,
        )
        for axis, height in (
            (Vector3(1, 0, 0), 0.5),
            (Vector3(0, 1, 0), 0.2),
            (unit(Vector3(1, 2, 3)), 0.4),
        )
    )


def test_different_constraint_axes_and_heights_share_only_two_region_preparations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Six independent projections need two shared preparations, retaining every raw gap on both sides.
    """
    model = _model()
    bounds = _bounds(model)
    prepared = Mock(wraps=region)
    independent = Mock(wraps=region)
    monkeypatch.setitem(vars(feature_plane), "prepare_flat_region", prepared)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.flat_separation.region", independent
    )
    for side in Side:
        assert [b.gap(model.initial, side) for b in bounds] == [
            _raw(b, model.initial, side) for b in bounds
        ]
        assert len(independent.call_args_list) == (6 if side is Side.BEFORE else 12)
    assert len(prepared.call_args_list) == 2
    assert model.flat_regions.statistics() == {
        "hits": 4,
        "preparations": 2,
        "retained": 2,
        "capacity": 64,
    }
    initial = model.initial
    changed = initial[:-1] + (initial[-1] + 0.01,)
    assert [b.gap(changed, Side.BEFORE) for b in bounds] == [
        _raw(b, changed, Side.BEFORE) for b in bounds
    ]
    assert len(prepared.call_args_list) == 3
    assert model.flat_regions.statistics() == {
        "hits": 6,
        "preparations": 3,
        "retained": 3,
        "capacity": 64,
    }


@pytest.mark.parametrize(
    "phase,index", ((FlatPhase.STRAIGHT, 0), (FlatPhase.BEFORE, 1), (FlatPhase.AFTER, 1))
)
@pytest.mark.parametrize(
    "axis", (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1), unit(Vector3(1, 2, 3)))
)
def test_transformed_flat_support_retains_exact_public_arithmetic_and_prism_bounds(
    phase: FlatPhase,
    index: int,
    axis: Vector3,
) -> None:
    """
    Preserve BEFORE/AFTER origins under large world translation and rigid rotation, including height.
    """
    model = _model()
    original = model.pieces(model.initial)[index]

    def rotate(v: Vector3) -> Vector3:
        """
        Rotate the authored frame by a right angle without changing local material coordinates.
        """
        return Vector3(-v.y, v.x, v.z)

    pose = original.pose
    piece = replace(
        original,
        pose=replace(
            pose,
            origin=rotate(pose.origin).translated(Vector3(1e6, -2e6, 3e6), 1),
            tangent=rotate(pose.tangent),
            width=rotate(pose.width),
        ),
    )
    part = FlatPart(phase, -0.6, 0.6, 0.5)
    bound = FlatSeparation(model, (Region(0, True), Region(1, True)), (part, part), axis)
    actual = bound._span(piece, part)
    assert actual == flat_span(piece, part, axis)
    vertices = flat_prism(piece, part)[0]
    projected = tuple(dot(point, axis) for point in vertices)
    assert actual == pytest.approx((min(projected), max(projected)), rel=0, abs=3e-8)


def test_phase_profile_placement_and_geometry_changes_never_borrow_an_old_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exact complete keys distinguish changed material and world placement, while identical requests reuse.
    """
    model = _model()
    piece = model.pieces(model.initial)[1]
    prepared = Mock(wraps=region)
    monkeypatch.setitem(vars(feature_plane), "prepare_flat_region", prepared)
    original = model.flat_regions(piece, FlatPhase.BEFORE, -0.6, 0.6)
    assert model.flat_regions(piece, FlatPhase.BEFORE, -0.6, 0.6) is original
    variants = (
        (piece, FlatPhase.AFTER, -0.6, 0.6),
        (piece, FlatPhase.BEFORE, -0.3, 0.6),
        (
            replace(
                piece,
                pose=replace(
                    piece.pose, origin=piece.pose.origin.translated(Vector3(1, 0, 0), 0.1)
                ),
            ),
            FlatPhase.BEFORE,
            -0.6,
            0.6,
        ),
        (replace(piece, geometry=fold(2, 1.2, 1.0, 0.3, 1)), FlatPhase.BEFORE, -0.6, 0.6),
    )
    for arguments in variants:
        assert model.flat_regions(*arguments) == region(*arguments)
    assert len(prepared.call_args_list) == 5


def test_region_workspaces_are_model_owned_and_eviction_reprepares_exact_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Separate contexts own their data, with at most64strong immutable keys and deterministic eviction.
    """
    model, other = _model(), _model()
    prepared = Mock(wraps=region)
    monkeypatch.setitem(vars(feature_plane), "prepare_flat_region", prepared)
    base = model.pieces(model.initial)[0]
    pieces = tuple(replace(base, geometry=Straight(3 + i / 100)) for i in range(65))
    first = model.flat_regions(pieces[0], FlatPhase.STRAIGHT, -0.6, 0.6)
    for piece in pieces[1:]:
        model.flat_regions(piece, FlatPhase.STRAIGHT, -0.6, 0.6)
    counts = [len(prepared.call_args_list)]
    assert model.flat_regions.statistics()["retained"] == 64
    model.flat_regions(pieces[-1], FlatPhase.STRAIGHT, -0.6, 0.6)
    counts.append(len(prepared.call_args_list))
    restored = model.flat_regions(pieces[0], FlatPhase.STRAIGHT, -0.6, 0.6)
    assert restored == first and restored is not first
    counts.append(len(prepared.call_args_list))
    assert other.flat_regions(pieces[0], FlatPhase.STRAIGHT, -0.6, 0.6) == first
    counts.append(len(prepared.call_args_list))
    assert id(other.flat_regions) != id(model.flat_regions)
    assert other.flat_regions.statistics() == {
        "hits": 0,
        "preparations": 1,
        "retained": 1,
        "capacity": 64,
    }
    assert counts == [65, 65, 66, 67]


@pytest.mark.parametrize("invalid", ("negative", "nonfinite", "size", "vanished"))
def test_invalid_coordinates_or_lost_material_cannot_bypass_validation_with_warm_cache(
    monkeypatch: pytest.MonkeyPatch,
    invalid: str,
) -> None:
    """
    Original full placement and stable-slot checks still precede shared geometry lookup.
    """
    model = _model()
    bound = _bounds(model)[0]
    bound.gap(model.initial, Side.BEFORE)
    prepared = Mock(side_effect=AssertionError("invalid placement reached cache preparation"))
    monkeypatch.setattr(model, "flat_regions", prepared)
    values = list(model.initial)
    if invalid == "negative":
        values[-1] = -1
    elif invalid == "nonfinite":
        values[-1] = float("nan")
    elif invalid == "size":
        values.pop()
    else:
        values[1] = 0
    with pytest.raises((ValueError, TopologyChanged)):
        bound.gap(tuple(values), Side.AFTER)
    prepared.assert_not_called()


def test_failed_phase_preparation_is_not_cached_as_valid_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Repeated unsupported phase requests keep raising the original error rather than yielding cached data.
    """
    model = _model()
    piece = model.pieces(model.initial)[1]
    prepared = Mock(wraps=region)
    monkeypatch.setitem(vars(feature_plane), "prepare_flat_region", prepared)
    for _ in range(2):
        with pytest.raises(ValueError, match="explicit before/after"):
            model.flat_regions(piece, FlatPhase.STRAIGHT, -0.6, 0.6)
    assert len(prepared.call_args_list) == 2


@pytest.mark.parametrize("extra", (False, True))
@pytest.mark.parametrize("kind", ("movable", "signed", "straight"))
def test_complete_coordinate_contract_guards_placement_expansion_and_length_gradient(
    extra: bool,
    kind: str,
) -> None:
    """
    Every reduced-coordinate adapter rejects truncated or surplus inputs before initial values can fill them.
    """
    from experiments.experiment_ribbon_bend_relocation.model import MovableBends
    from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots

    source = _model().original
    model: MovableBends = {
        "movable": MovableBends,
        "signed": SignedJoints,
        "straight": StraightSlots,
    }[kind](source)
    values = model.initial + (0.0,) if extra else model.initial[:-1]
    operations: tuple[Callable[[tuple[float, ...]], object], ...] = (
        model.expanded,
        model.pieces,
        model.length_gradient,
    )
    for operation in operations:
        with pytest.raises(ValueError, match="complete movable-bend"):
            operation(values)
