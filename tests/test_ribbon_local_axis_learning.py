"""
Reuse actual local separation directions only after proving each new full material-cell pair.
"""

from __future__ import annotations

import math
from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from cable_bundler.routing.geometry import Vector3, cross, unit
from experiments.experiment_ribbon_fold_route import contact
from experiments.experiment_ribbon_fold_route.contact_axes import (
    AxisContinuation,
    AxisLearning,
    ProposedAxes,
)
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_traversal import ContactTraversal
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_probe_axis import _skew


def _context() -> ProposedAxes:
    """
    Request local learning explicitly without supplying any external direction or witness probe.
    """
    return ProposedAxes(AxisContinuation.MATERIAL_CELLS, learning=AxisLearning.LOCAL_SEPARATIONS)


def _interior_bar(bank: float) -> FoldRoute:
    """
    Place a separated bar inside an oblique U envelope; these volumes are an analytical contact fixture.
    """
    source = _route((fold(2.0, 1.2, math.pi, bank, 4.0),))
    bar = PlacedPiece(
        Pose(Vector3(0.5, 0, 2), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(2), "U interior bar"
    )
    tangent = unit(Vector3(1, 2, 3))
    frame = Pose(Vector3(3, -2, 1), tangent, unit(cross(tangent, Vector3(-2, 1, 0.5))))
    pieces = tuple(
        PlacedPiece(
            Pose(
                frame.point(p.pose.origin),
                frame.direction(p.pose.tangent),
                frame.direction(p.pose.width),
            ),
            p.geometry,
            p.label,
        )
        for p in (*source.pieces, bar)
    )
    return replace(source, pieces=pieces)


@pytest.mark.parametrize("bank", (0.0, 0.2, -0.3))
def test_actual_local_separation_supplies_later_hints_without_an_external_probe(
    bank: float,
) -> None:
    """
    Preserve analytical separation and measure real re-proofs instead of treating retained hints as clearance.
    """
    route = _interior_bar(bank)
    contexts = [ProposedAxes(AxisContinuation.MATERIAL_CELLS), _context()]
    results = []
    inversions = []
    for context in contexts:
        inverse = Mock(wraps=contact.occupied_coordinates)
        with patch.dict(vars(contact), occupied_coordinates=inverse):
            results.append(
                contact.inspect_contact(
                    route,
                    maximum_pairs=2048,
                    cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                    projection_reuse=contact.ProjectionReuse.CELLS,
                    proposed_axes=context,
                )
            )
        inversions.append(inverse.call_count)
    assert results[0].status == results[1].status == "separated"
    assert contexts[1].local_hints > 0
    assert inversions[1] <= inversions[0] and results[1].pairs_checked <= results[0].pairs_checked
    if bank == 0.0:
        assert contexts[1].descendant_separations > 0 and inversions[1] < inversions[0]
    else:
        assert contexts[1].descendant_separations == 0 and results[1] == results[0]
    assert contexts[0].local_hints == contexts[0].descendant_tests == 0


@pytest.mark.parametrize("index", range(5))
def test_learned_directions_never_hide_actual_thick_material_penetration(index: int) -> None:
    """
    Both original strict material inverses must verify every actual occupied-point witness.
    """
    route = _skew(index)
    result = contact.inspect_contact(route, maximum_pairs=2048, proposed_axes=_context())
    assert result.status == "penetration" and result.witness is not None
    for piece in result.witness.pieces:
        assert (
            contact.occupied_coordinates(
                route.pieces[piece],
                result.witness.point,
                route.targets.lines,
                route.targets.diameter_mm,
            )
            is not None
        )


def test_learning_keeps_existing_fifo_capacity_and_reprojects_both_changed_cells() -> None:
    """
    Hints carry only direction and original-pair identity; no span, cell or positive result survives.
    """
    source = _skew(6)
    route = replace(source, pieces=(source.pieces[0],) * 67)
    context = _context()
    context.bind(route)
    axis = Vector3(0, 0, 1)
    first = Cell(0, Span(0, 0.5), Span(0, 1), Span(0, 1), 1)
    for index in range(2, 67):
        context.learn_local(first, replace(first, piece=index), axis)
    assert context.local_hints == 65 and context.statistics()["retained_directions"] == 64
    assert context.statistics()["retained_resolutions"] == 64
    project = Mock(side_effect=(Span(0, 1), Span(2, 3), Span(0, 3), Span(1, 2)))
    assert not context.separates_descendants(first, replace(first, piece=2), project, None)
    assert context.separates_descendants(first, replace(first, piece=66), project, None)
    assert not context.separates_descendants(
        replace(first, u=Span(0.5, 1)), replace(first, piece=66), project, None
    )
    assert project.call_count == 4 and context.tests == 2 and context.separations == 1
    assert not context.separates_descendants(
        replace(first, u=Span(0, 1)), replace(first, piece=66), project, None
    )
    assert project.call_count == 4
    assert context.resolution_deferrals == 1


def test_cancelled_reproof_never_uses_a_previous_positive_result() -> None:
    """
    Caller cancellation must propagate before any new projection even when a direction is retained.
    """
    context = _context()
    context.bind(_skew(6))
    first = Cell(0, Span(0, 0.5), Span(0, 1), Span(0, 1), 1)
    context.learn_local(first, replace(first, piece=1), Vector3(0, 0, 1))
    project = Mock()
    guard = Mock(side_effect=InterruptedError("original guard"))
    with pytest.raises(InterruptedError, match="original guard"):
        context.separates_descendants(first, replace(first, piece=1), project, guard)
    project.assert_not_called()
    assert context.tests == context.separations == 0
    assert context.statistics()["retained_directions"] == 1


@pytest.mark.parametrize("chunk", (1, 2, 4))
def test_suspension_preserves_learning_without_renewing_work_or_context(chunk: int) -> None:
    """
    Match the exact uninterrupted proof and counters under one immutable cumulative allowance.
    """
    route = _interior_bar(0.0)
    expected_context = _context()
    expected = contact.inspect_contact(
        route,
        maximum_pairs=2048,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        proposed_axes=expected_context,
    )
    context = _context()
    traversal = ContactTraversal(
        route, maximum_pairs=2048, cap_policy=CapPolicy.ANALYTIC_SUPPORT, proposed_axes=context
    )
    result = traversal.advance(chunk)
    for limit in range(2 * chunk, 2049, chunk):
        if result.limit != "pairs":
            break
        result = traversal.advance(limit)
    assert result == expected and context.statistics() == expected_context.statistics()


def test_default_learning_is_disabled_and_invalid_policy_cannot_silently_enable_it() -> None:
    """
    Preserve existing hint ownership and reject unsupported policy combinations before traversal.
    """
    context = ProposedAxes(AxisContinuation.MATERIAL_CELLS)
    context.bind(_skew(6))
    first = Cell(0, Span(0, 0.5), Span(0, 1), Span(0, 1), 1)
    context.learn_local(first, replace(first, piece=1), Vector3(0, 0, 1))
    assert context.statistics()["retained_directions"] == context.local_hints == 0
    assert "local_separation_hints" not in context.statistics()
    with pytest.raises(ValueError, match="material-cell continuation"):
        ProposedAxes(learning=AxisLearning.LOCAL_SEPARATIONS)


@pytest.mark.parametrize("limit", ("pairs", "depth"))
def test_local_learning_cannot_replace_an_exhausted_full_material_proof(limit: str) -> None:
    """
    Preserve finite unresolved outcomes when the original cell/depth allowance cannot certify the pair.
    """
    result = contact.inspect_contact(
        _interior_bar(0.0),
        maximum_pairs=1 if limit == "pairs" else 2048,
        maximum_depth=1 if limit == "depth" else 36,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        proposed_axes=_context(),
    )
    assert result.status == "unresolved" and result.limit == limit


def test_learned_hint_context_cannot_transfer_to_another_walk() -> None:
    """
    An identical route still needs a new bounded context and complete proof.
    """
    route = _interior_bar(0.0)
    context = _context()
    assert contact.inspect_contact(route, proposed_axes=context).status == "separated"
    for source in (route, replace(route)):
        with pytest.raises(ValueError, match="fresh optional-axis context"):
            contact.inspect_contact(source, proposed_axes=context)


@pytest.mark.parametrize("scale", (0.1, 1.0, 20.0))
def test_size_priority_defers_only_the_optional_test_at_coarser_material_resolution(
    scale: float,
) -> None:
    """
    Use the actual material size rather than depth, world orientation or a fixed numerical cutoff.
    """
    source = _skew(6)
    route = replace(
        source, pieces=tuple(replace(p, geometry=Straight(20 * scale)) for p in source.pieces)
    )
    context = _context()
    context.bind(route)
    first = Cell(0, Span(0, 0.25), Span(0, 0.1 * scale), Span(0, 0.1 * scale), 1)
    second = replace(first, piece=1)
    context.learn_local(first, second, Vector3(0, 0, 1))
    project = Mock(side_effect=(Span(0, 1), Span(2, 3)))
    assert not context.separates_descendants(replace(first, u=Span(0, 0.5)), second, project, None)
    project.assert_not_called()
    assert context.separates_descendants(first, second, project, None)
    assert project.call_count == 2 and context.resolution_deferrals == 1
    assert context.statistics()["retained_resolutions"] == 1


def test_invalid_material_extent_does_not_store_a_direction_or_resolution() -> None:
    """
    Validate untrusted cell identities and extents before mutating the bounded hint context.
    """
    context = _context()
    context.bind(_skew(6))
    first = Cell(0, Span(0, 0.5), Span(0, 1), Span(0, 1), 1)
    with pytest.raises(ValueError, match="nonnegative material extents"):
        context.learn_local(replace(first, u=Span(1, 0)), replace(first, piece=1), Vector3(0, 0, 1))
    assert context.local_hints == 0
    assert (
        context.statistics()["retained_resolutions"]
        == context.statistics()["retained_directions"]
        == 0
    )
