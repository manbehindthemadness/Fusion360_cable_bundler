"""
Verify exact bounded placement reuse and duplicate hardware-member preparation on analytical geometry.
"""

from __future__ import annotations

import math
from dataclasses import replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.separation import Region
from experiments.experiment_ribbon_fold_route.contact_bounds import Span
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology
from experiments.experiment_ribbon_terminal_hardware import feature_guidance
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import member_planes
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_contact_refinement import _source
from tests.test_ribbon_feature_insertion import _targets


@pytest.mark.parametrize("scale", (1.0, 20.0))
def test_cached_allocations_equal_original_ordered_placement_arithmetic(scale: float) -> None:
    """
    Every authored topology and basis/interior vector retains exactly the original immutable pieces.
    """
    frames = Frames.create(_targets(scale))
    boundary = Boundary(frames.targets, 0.101 * scale)
    for chain in chains(boundary, frames, (0.3, 0.7), lambda: None, lambda event: None):
        model = Model(boundary, chain.topology)
        vectors = [(0.0,) * model.size, tuple(0.1 * i for i in range(model.size))]
        vectors += [tuple(float(i == j) for i in range(model.size)) for j in range(model.size)]
        for values in vectors:
            expected = model._place(values)
            actual = model.pieces(values)
            assert actual == expected
            assert model.pieces(values) is actual
        other = Model(boundary, chain.topology)
        assert other.pieces(vectors[-1]) == model.pieces(vectors[-1])
        assert other.pieces(vectors[-1]) is not model.pieces(vectors[-1])


def test_cache_retains_only_sixty_four_vectors_and_still_validates_hits() -> None:
    """
    Eviction recomputes exact geometry; malformed coordinates cannot pass through lookup.
    """
    frames = Frames.create(_targets())
    chain = chains(Boundary(frames.targets, 0.101), frames, (0.5,), lambda: None, lambda e: None)[0]
    model = Model(Boundary(frames.targets, 0.101), chain.topology)
    zero = (0.0,) * model.size
    first = model.pieces(zero)
    for i in range(1, 66):
        model.pieces((float(i),) + zero[1:])
    refreshed = model.pieces(zero)
    assert refreshed == first and refreshed is not first
    for values in ((-1.0,) + zero[1:], (math.nan,) + zero[1:], zero[:-1]):
        with pytest.raises(ValueError, match="finite nonnegative"):
            model.pieces(values)


@pytest.mark.parametrize("scale", (1.0, 20.0))
@pytest.mark.parametrize("folds", (0, 4, 6))
def test_fixed_radius_columns_match_full_equations_without_radius_basis_placement(
    monkeypatch: pytest.MonkeyPatch, scale: float, folds: int
) -> None:
    """
    Fixed-radius consumers receive exactly the old straight coefficients and RHS with fewer evaluations.
    """
    frames = Frames.create(_targets(scale))
    boundary = Boundary(frames.targets, 0.101 * scale)
    topology = (
        Topology("analytical empty", (), None)
        if folds == 0
        else chains(
            boundary,
            frames,
            (0.5,) if folds == 4 else (0.3, 0.7),
            lambda: None,
            lambda event: None,
        )[0].topology
    )
    original = Mock(wraps=Model._place)

    def measured(owner: Model, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Count full placements while retaining their exact original composition.
        """
        return original(owner, values)

    monkeypatch.setattr(Model, "_place", measured)
    complete = Model(boundary, topology)
    full_columns, full_right = complete.equations()
    assert original.call_count == complete.size + 1
    original.reset_mock()
    fixed = Model(boundary, topology)
    straight_columns, straight_right = fixed.straight_equations()
    assert straight_columns == full_columns[::2] and straight_right == full_right
    assert original.call_count == folds + 2


@pytest.mark.parametrize("bank", (0.0, -0.3, 0.4))
def test_overlapping_features_prepare_each_exact_box_member_once(
    monkeypatch: pytest.MonkeyPatch, bank: float
) -> None:
    """
    Repeated observations preserve selected families, sides, order and gaps without repeated axis work.
    """
    source = _source(bank)
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    report = inspect(source, hardware)
    whole = FeaturePlane.create(model, source, report, hardware, model.initial)
    assert whole is not None
    expected = member_planes([whole], model, model.initial)
    original = Mock(wraps=FeaturePlane._span)
    calls: list[FeaturePlane] = []

    def measured(self: FeaturePlane, pieces: tuple[PlacedPiece, ...], axis: Vector3) -> Span:
        """
        Count preparation boundary evaluations while retaining the original support calculation.
        """
        calls.append(self)
        return original(self, pieces, axis)

    monkeypatch.setattr(FeaturePlane, "_span", measured)
    single = member_planes([whole], model, model.initial)
    count = len(calls)
    calls.clear()
    # Whole-feature selections do not affect each member's independent axis choice.
    repeated = member_planes(
        [whole, replace(whole, family=(whole.family + 1) % 15)], model, model.initial
    )
    assert single == repeated == expected and len(calls) == count
    assert [p.gap(model.initial) for p in repeated] == [p.gap(model.initial) for p in expected]
    calls.clear()
    other_box = next(box for box in hardware.boxes if box != whole.box)
    member_planes([replace(whole, box=other_box)], model, model.initial)
    other_count = len(calls)
    calls.clear()
    member_planes([whole, replace(whole, box=other_box)], model, model.initial)
    assert len(calls) == count + other_count


def test_member_preparation_does_not_merge_distinct_model_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Equal-looking coordinate owners retain their own preparation rather than sharing model-bound state.
    """
    source = _source(0.2)
    model = SignedJoints(source)
    other = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    whole = FeaturePlane.create(model, source, inspect(source, hardware), hardware, model.initial)
    assert whole is not None
    original = feature_guidance.locate
    owners: list[int] = []

    def locate(route: FoldRoute, pieces: tuple[PlacedPiece, ...], member: Region) -> PlacedPiece:
        """
        Count original member-family preparation boundaries without changing their output.
        """
        owners.append(1)
        return original(route, pieces, member)

    monkeypatch.setitem(vars(feature_guidance), "locate", locate)
    member_planes([whole], model, model.initial)
    count = len(owners)
    owners.clear()
    member_planes([whole, replace(whole, model=other)], model, model.initial)
    assert len(owners) == 2 * count
