"""
Detect thin affine-cell crossings without converting box overlap or a missed proposal into clearance.
"""

from __future__ import annotations

import math
from dataclasses import fields, replace
from typing import Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, cross, unit
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.contact_affine_witness import AffineWitnesses
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.contact_traversal import ContactTraversal
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_traversal import _parallel
from tests.test_ribbon_probe_axis import _skew

Coordinates = tuple[float, float, float]


def _roots(route: FoldRoute) -> tuple[Cell, Cell]:
    """
    Supply complete first/second material boxes for an independently authored route.
    """
    cells = tuple(
        Cell(
            i,
            Span(0.0, 1.0),
            Span(-route.half_width_mm, route.half_width_mm),
            Span(-route.targets.diameter_mm / 2, route.targets.diameter_mm / 2),
        )
        for i in (0, 1)
    )
    return cells[0], cells[1]


def _occupied(route: FoldRoute) -> Callable[[int, Vector3], Coordinates | None]:
    """
    Keep actual joined-profile inverse verification at the proposal boundary.
    """

    def inspect(index: int, point: Vector3) -> Coordinates | None:
        """
        Resolve one exact original member and world point without a physical-boundary double.
        """
        return occupied_coordinates(
            route.pieces[index], point, route.targets.lines, route.targets.diameter_mm
        )

    return inspect


def _verify(route: FoldRoute, result: ContactResult) -> None:
    """
    Independently verify both returned material interiors and the stable nine-field receipt.
    """
    assert result.status == "penetration" and result.witness is not None
    for index in result.witness.pieces:
        assert _occupied(route)(index, result.witness.point) is not None
    assert len(fields(result)) == 9


@pytest.mark.parametrize("gap", (0.8, 0.99, 0.999))
def test_thin_parallel_overlap_is_detected_within_the_same_single_cell_pair(gap: float) -> None:
    """
    Original center tests miss a thin full-profile overlap; the verified intersection mean finds it.
    """
    source = _parallel(gap)
    source = replace(source, pieces=source.pieces[:2])
    baseline = inspect_contact(source, maximum_pairs=1)
    assert baseline.status == "unresolved" and baseline.limit == "pairs"
    context = AffineWitnesses()
    measured = inspect_contact(source, maximum_pairs=1, affine_witnesses=context)
    _verify(source, measured)
    assert measured.pairs_checked == 1
    assert context.attempts == context.candidates == context.witnesses == 1
    assert context.edges == 24 and context.inverse_requests == 2


@pytest.mark.parametrize("index", range(12))
def test_authored_skew_decisions_remain_physical_under_bounded_affine_proposals(index: int) -> None:
    """
    Match clear/penetrating dispositions against the original full proof and re-invert every witness.
    """
    source = _skew(index)
    baseline = inspect_contact(source, maximum_pairs=2048)
    context = AffineWitnesses()
    measured = inspect_contact(source, maximum_pairs=2048, affine_witnesses=context)
    assert measured.status == baseline.status
    assert measured.pairs_checked <= 2048 and context.attempts <= 32
    assert (
        context.edges <= 24 * context.attempts
        and context.inverse_requests <= 2 * context.candidates
    )
    if measured.witness is not None:
        _verify(source, measured)


@pytest.mark.parametrize("bank", (-0.3, 0.0, 0.3))
@pytest.mark.parametrize("at_end", (False, True))
def test_banked_flat_fold_phases_supply_actual_material_witnesses(
    bank: float, at_end: bool
) -> None:
    """
    Check BEFORE/AFTER affine frames against the real folded map rather than a flattened replacement.
    """
    source = _route((fold(2, 1.2, 1.1, bank, 5),))
    member = source.pieces[0]
    u = 0.9 if at_end else 0.1
    center, velocity, across, _ = member.surface(u, 0.0)
    tangent, normal = unit(velocity), unit(cross(velocity, across))
    straight = PlacedPiece(
        Pose(center.translated(across, -1.0).translated(normal, 0.2), across, tangent),
        Straight(2),
        "authored crossing in actual flat phase",
    )
    route = replace(source, pieces=(member, straight))
    first, second = _roots(route)
    first = replace(first, u=Span(0.85, 0.95) if at_end else Span(0.05, 0.15))
    context = AffineWitnesses()
    context.bind(route)
    found = context.inspect(first, second, _occupied(route), None)
    assert found is not None and context.witnesses == 1
    for index in (0, 1):
        assert _occupied(route)(index, found[2]) is not None


@pytest.mark.parametrize("gap,side", ((1.0, 0.0), (0.9, 0.8)))
def test_tangency_and_empty_joined_profile_space_never_become_a_penetration(
    gap: float,
    side: float,
) -> None:
    """
    A convex box mean on a real boundary or in empty profile space must fail actual inversion.
    """
    source = _parallel(gap)
    second = replace(
        source.pieces[1], pose=replace(source.pieces[1].pose, origin=Vector3(0, side, gap))
    )
    route = replace(source, pieces=(source.pieces[0], second))
    context = AffineWitnesses()
    result = inspect_contact(route, maximum_pairs=1, affine_witnesses=context)
    assert result.status == "unresolved" and result.witness is None
    assert context.attempts == context.candidates == 1 and context.witnesses == 0


def test_curved_material_is_declined_without_flattening_or_inverse_claims() -> None:
    """
    A cylindrical interval cannot enter the affine proposal path or acquire a box-based exemption.
    """
    source = _route((fold(2, 1.2, 1.1, 0.3, 5), Straight(2)))
    first, second = _roots(source)
    first = replace(first, u=Span(0.49, 0.51), q=Span(-0.01, 0.01))
    context = AffineWitnesses()
    context.bind(source)
    inverse = Mock(side_effect=AssertionError("Curved material has no affine witness authority"))
    assert context.inspect(first, second, inverse, None) is None
    assert context.nonaffine == 1 and context.attempts == 0
    inverse.assert_not_called()


def test_capacity_is_nonrenewable_and_never_changes_the_default_complete_proof() -> None:
    """
    Exhausted optional discovery falls back to the unchanged checker, without clearance credit.
    """
    source = _skew(5)
    expected = inspect_contact(source, maximum_pairs=2048)
    disabled = AffineWitnesses(0)
    assert inspect_contact(source, maximum_pairs=2048, affine_witnesses=disabled) == expected
    assert disabled.attempts == 0 and disabled.limited > 0
    limited = AffineWitnesses(1)
    limited.bind(source)
    first, second = _roots(source)
    rejected = Mock(return_value=None)
    limited.inspect(first, second, rejected, None)
    count = rejected.call_count
    assert limited.inspect(first, second, rejected, None) is None
    assert limited.attempts == 1 and limited.limited == 1 and rejected.call_count == count


@pytest.mark.parametrize("invalid", (-1, 33, True, math.nan))
def test_invalid_optional_work_cannot_enlarge_the_allowance(invalid: int) -> None:
    """
    Keep the fixed upper ceiling and reject booleans, negatives and noninteger limits.
    """
    with pytest.raises(ValueError, match="zero to 32"):
        AffineWitnesses(invalid)


def test_source_isolation_and_edge_guard_prevent_reuse_or_late_witnesses() -> None:
    """
    Original cancellation propagates before further edge work and no context can bind another walk.
    """
    source = _parallel(0.99)
    context = AffineWitnesses()
    context.bind(source)
    inverse = Mock(side_effect=AssertionError("No inverse after cancellation"))
    guard = Mock(side_effect=(None, None, InterruptedError("original guard")))
    with pytest.raises(InterruptedError, match="original guard"):
        context.inspect(*_roots(source), inverse, guard)
    assert context.attempts == 1 and context.edges == 1 and context.witnesses == 0
    inverse.assert_not_called()
    for route in (source, replace(source), _parallel(0.9)):
        with pytest.raises(ValueError, match="fresh affine witness context"):
            context.bind(route)


def test_chunked_affine_discovery_retains_one_context_and_same_final_receipt() -> None:
    """
    Optional intersection work is neither repeated nor renewed at a material-stack suspension.
    """
    source = _skew(5)
    expected_context = AffineWitnesses()
    expected = inspect_contact(source, maximum_pairs=2048, affine_witnesses=expected_context)
    context = AffineWitnesses()
    traversal = ContactTraversal(source, maximum_pairs=2048, affine_witnesses=context)
    result = traversal.advance(1)
    for limit in range(32, 2049, 32):
        if result.limit != "pairs":
            break
        result = traversal.advance(limit)
    assert result == expected and context.statistics() == expected_context.statistics()
    assert traversal.advance(2048) is result
