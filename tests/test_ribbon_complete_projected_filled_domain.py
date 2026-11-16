"""
Check filled-region evidence against order loss, explicit closure gaps and narrow source domains.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.flat_chart import MaterialCut
from experiments.experiment_ribbon_complete.native_boundary_distance import BoundarySide
from experiments.experiment_ribbon_complete.projected_filled_domain import (
    DirectedBoundaryTrace,
    ProjectedFilledDomain,
)
from tests.test_ribbon_complete_native_boundary_distance import bound, fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def boundary(length: Fraction = Fraction(2)) -> tuple[DirectedBoundaryTrace, ...]:
    """
    Own four directed exact curves enclosing the source rectangle in original physical coordinates.
    """
    native, frame, graph = fixture()
    native = replace(
        native, rows=tuple(tuple((s * length / 2, q, b) for s, q, b in row) for row in native.rows)
    )
    frame = replace(frame, high=MaterialCut(length))
    zero, one, two = Fraction(0), Fraction(1), Fraction(2)
    corners = ((zero, zero), (two, zero), (two, one), (zero, one))
    sides = (BoundarySide.END0, BoundarySide.HIGH, BoundarySide.END1, BoundarySide.LOW)
    return tuple(
        DirectedBoundaryTrace(
            bound(native, frame, graph, side, (corners[i], corners[(i + 1) % 4])),
            i,
            (i + 1) % 4,
            False,
        )
        for i, side in enumerate(sides)
    )


def test_exact_fill_and_reversed_topological_orientation_share_zero_error() -> None:
    """
    Reversing the entire directed cycle preserves filled coverage without changing curve geometry.
    """
    original = boundary()
    reversed_cycle = tuple(
        replace(row, start_vertex=row.end_vertex, end_vertex=row.start_vertex, reversed=True)
        for row in reversed(original)
    )
    for rows in (original, reversed_cycle):
        result = ProjectedFilledDomain(rows, checkpoint)
        assert result.status == "within_projected_capture_filled_accuracy"
        assert result.forward_upper_mm == result.reverse_upper_mm == 0
        assert sum(result.closure_gaps_mm) == 0
        assert result.source_inradius_mm > 0


def test_split_side_retains_the_same_filled_region() -> None:
    """
    An additional coedge is not another side traversal or an independent geometric case.
    """
    rows = boundary()
    first = rows[0].finite
    native, frame, graph = first.trace.surface, first.frame, first.graph
    zero, one, two = Fraction(0), Fraction(1), Fraction(2)
    pieces = tuple(
        DirectedBoundaryTrace(
            bound(native, frame, graph, BoundarySide.END0, controls), start, end, False
        )
        for controls, start, end in (
            (((zero, zero), (one, zero)), 0, 4),
            (((one, zero), (two, zero)), 4, 1),
        )
    )
    result = ProjectedFilledDomain(pieces + rows[1:], checkpoint)
    assert result.status == "within_projected_capture_filled_accuracy"
    assert result.forward_upper_mm == result.reverse_upper_mm == 0


def test_parameter_direction_mismatch_cannot_hide_endpoint_bridges() -> None:
    """
    Even on identical boundary supports, reversing one curve produces explicit large gaps and fails fill accuracy.
    """
    rows = boundary()
    broken = (replace(rows[0], reversed=True), *rows[1:])
    result = ProjectedFilledDomain(broken, checkpoint)
    assert sum(result.closure_gaps_mm) == 4
    assert result.status == "unresolved_projected_capture_filled_accuracy"


def test_small_endpoint_gap_is_charged_without_welding_geometry() -> None:
    """
    A shortened generator retains its actual endpoint and an explicit proof bridge in the common allowance.
    """
    rows = boundary()
    first = rows[0].finite
    shortened = bound(
        first.trace.surface,
        first.frame,
        first.graph,
        BoundarySide.END0,
        ((Fraction(1, 100000), Fraction(0)), (Fraction(2), Fraction(0))),
    )
    result = ProjectedFilledDomain((replace(rows[0], finite=shortened), *rows[1:]), checkpoint)
    assert result.closure_gaps_mm[-1] == Fraction(1, 100000)
    assert result.collar_upper_mm == Fraction(2, 100000)
    assert result.status == "within_projected_capture_filled_accuracy"
    assert shortened.trace.curve.controls[0][0] == Fraction(1, 100000)


def test_boundary_proximity_cannot_replace_single_cyclic_side_coverage() -> None:
    """
    Missing and repeated traversals cannot inherit a fill proof from perfect boundary support distances.
    """
    rows = boundary()
    with pytest.raises(ValueError, match="directed vertex cycle"):
        ProjectedFilledDomain(rows[:-1], checkpoint)
    with pytest.raises(ValueError, match="exactly once cyclically"):
        ProjectedFilledDomain(rows + rows, checkpoint)


def test_foreign_owners_and_stopped_allocations_do_not_inherit_coverage() -> None:
    """
    Equivalent replacement geometry and exhausted work cannot reuse an owned coverage certificate.
    """
    rows = boundary()
    foreign = boundary()
    with pytest.raises(ValueError, match="SAME owners"):
        ProjectedFilledDomain((foreign[0], *rows[1:]), checkpoint)

    def stop() -> None:
        """
        Refuse work after the caller's fixed allocation expires.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        ProjectedFilledDomain(rows, stop)


def test_small_absolute_gap_cannot_erase_a_narrow_source_interior() -> None:
    """
    A sub-tolerance collar still requires a nonempty source core before winding can establish filled coverage.
    """
    rows = boundary(Fraction(1, 1000000))
    result = ProjectedFilledDomain((replace(rows[0], reversed=True), *rows[1:]), checkpoint)
    assert result.collar_upper_mm < Fraction(1, 100)
    assert 2 * result.collar_upper_mm >= result.source_inradius_mm
    assert result.status == "unresolved_projected_capture_filled_accuracy"


def test_translated_rectangle_bounds_dominate_its_independent_exact_filled_distance() -> None:
    """
    A genuine displaced filled domain has known distance even though each curve retains its original side assignment.
    """
    rows = boundary()
    displacement = Fraction(1, 100000)
    original = rows[0].finite.trace.surface
    translated = replace(
        original,
        rows=tuple(tuple((s + displacement, q, b) for s, q, b in row) for row in original.rows),
    )
    moved = tuple(
        replace(
            row,
            finite=bound(
                translated,
                row.finite.frame,
                row.finite.graph,
                row.finite.side,
                row.finite.trace.curve.controls,
            ),
        )
        for row in rows
    )
    proof = ProjectedFilledDomain(moved, checkpoint)
    assert proof.status == "within_projected_capture_filled_accuracy"
    assert proof.forward_upper_mm >= displacement
    assert proof.reverse_upper_mm >= displacement
    assert sum(proof.closure_gaps_mm) == 0
    vertices = [row.endpoints()[0][:2] for row in moved]

    def winding(s: Fraction, q: Fraction) -> int:
        """
        Independently count exact ray crossings of this rectangle's projected corner polygon.
        """
        count = 0
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            cross = (b[0] - a[0]) * (q - a[1]) - (s - a[0]) * (b[1] - a[1])
            if a[1] <= q < b[1] and cross > 0:
                count += 1
            if b[1] <= q < a[1] and cross < 0:
                count -= 1
        return count

    assert winding(displacement / 2, Fraction(0)) == 0
    assert abs(winding(Fraction(1), Fraction(0))) == 1
    assert abs(winding(2 + displacement / 2, Fraction(0))) == 1
