"""
Distinguish bidirectional finite boundary coverage from support coincidence, endpoint sampling and wrong ellipse branches.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.flat_chart import MaterialCut, certify
from experiments.experiment_ribbon_complete.flat_cut_domain import FlatCutFrame, from_chart
from experiments.experiment_ribbon_complete.native_boundary_distance import (
    BoundarySide,
    FiniteBoundaryChain,
    FiniteBoundaryTrace,
    ProfileGraph,
    interval_coverage_gap,
)
from experiments.experiment_ribbon_complete.native_material_chart import NativeSurfaceSnapshot
from experiments.experiment_ribbon_complete.native_surface_trace import NativeSurfaceTrace
from experiments.experiment_ribbon_complete.native_trim_boundary import NativeTrimCurve
from experiments.experiment_ribbon_complete.profile_conic import EllipseArc
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from tests.test_ribbon_complete_native_flat_embedding import chart
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def fixture() -> tuple[NativeSurfaceSnapshot, FlatCutFrame, ProfileGraph]:
    """
    Retain an upper elliptic patch in original binary coefficients with a regular q graph and two-millimeter generators.
    """
    zero, one = Fraction(0), Fraction(1)
    arc = MaterialArc(
        ((-0.6, 0.8), (0, 1.25), (0.6, 0.8)),
        (1, 0.8, 1),
        "upper",
    )
    graph = ProfileGraph(EllipseArc(arc), checkpoint)
    native = NativeSurfaceSnapshot(
        "revision",
        0,
        0,
        arc.label,
        1,
        2,
        (zero, zero, Fraction(2), Fraction(2)),
        (zero, zero, zero, one, one, one),
        tuple(
            tuple((s, Fraction(q), Fraction(b)) for q, b in arc.controls)
            for s in (zero, Fraction(2))
        ),
        (tuple(map(Fraction, arc.weights)),) * 2,
    )
    return native, from_chart(certify(chart())), graph


def bound(
    native: NativeSurfaceSnapshot,
    frame: FlatCutFrame,
    graph: ProfileGraph,
    side: BoundarySide,
    controls: tuple[tuple[Fraction, Fraction], ...],
) -> FiniteBoundaryTrace:
    """
    Bind an original positive UV trace to one selected finite source side.
    """
    curve = NativeTrimCurve(1, controls, (Fraction(1),) * len(controls))
    return FiniteBoundaryTrace(
        NativeSurfaceTrace(native, curve, checkpoint), frame, graph, side, checkpoint
    )


def test_exact_original_profile_caps_and_generators_cover_both_finite_directions() -> None:
    """
    All four exact sides qualify without inventing source-domain extension or dimensional errors.
    """
    native, frame, graph = fixture()
    zero, one, two = Fraction(0), Fraction(1), Fraction(2)
    for side, controls in (
        (BoundarySide.LOW, ((zero, zero), (zero, one))),
        (BoundarySide.HIGH, ((two, zero), (two, one))),
        (BoundarySide.END0, ((zero, zero), (two, zero))),
        (BoundarySide.END1, ((zero, one), (two, one))),
    ):
        trace = bound(native, frame, graph, side, controls)
        chain = FiniteBoundaryChain((trace,), checkpoint)
        assert chain.status == "within_finite_original_boundary_accuracy"
        assert chain.forward_upper_mm.numerator == chain.reverse_upper_mm.numerator == 0


def test_missing_end_coverage_and_generator_overrun_cannot_pass_on_line_coincidence() -> None:
    """
    A native subset is perfectly on the finite source yet misses both ends; a longer trace leaves the finite source.
    """
    native, frame, graph = fixture()
    zero = Fraction(0)
    subset = bound(
        native, frame, graph, BoundarySide.END0, ((Fraction(1, 2), zero), (Fraction(3, 2), zero))
    )
    chain = FiniteBoundaryChain((subset,), checkpoint)
    assert chain.forward_upper_mm.numerator == 0
    assert chain.coverage_gap_mm == chain.reverse_upper_mm == Fraction(1, 2)
    assert chain.status == "unresolved_finite_original_boundary_accuracy"
    shortened_source = replace(frame, high=MaterialCut(Fraction(1)))
    overrun = bound(
        native, shortened_source, graph, BoundarySide.END0, ((zero, zero), (Fraction(2), zero))
    )
    assert overrun.forward_upper_mm >= 1


def test_zero_tip_is_valid_but_zero_conic_residual_on_opposite_branch_is_not() -> None:
    """
    The finite generator proof does not divide by its extent, while conic support alone cannot select a profile branch.
    """
    native, frame, graph = fixture()
    zero = Fraction(0)
    tip = replace(frame, high=MaterialCut(-Fraction(graph.conic.arc.controls[0][0]), Fraction(1)))
    trace = bound(native, tip, graph, BoundarySide.END0, ((zero, zero), (zero, zero)))
    assert trace.source_interval == (zero, zero)
    assert (
        FiniteBoundaryChain((trace,), checkpoint).status
        == "within_finite_original_boundary_accuracy"
    )
    wrong = replace(
        native,
        rows=tuple(
            tuple((s, q, 2 * graph.conic.center[1] - b) for s, q, b in row) for row in native.rows
        ),
    )
    with pytest.raises(ValueError, match="original profile graph branch"):
        bound(
            wrong,
            frame,
            graph,
            BoundarySide.HIGH,
            ((Fraction(2), zero), (Fraction(2), Fraction(1))),
        )


@pytest.mark.parametrize(
    "source,intervals,expected",
    [
        ((0, 4), ((0, 1), (3, 4)), 1),
        ((0, 4), ((1, 3),), 1),
        ((0, 4), ((-1, 2), (1, 5)), 0),
        ((2, 2), ((0, 1), (3, 4)), 1),
        ((0, 1), ((3, 4),), 3),
    ],
)
def test_interval_union_distance_preserves_internal_and_external_missing_coverage(
    source: tuple[int, int], intervals: tuple[tuple[int, int], ...], expected: int
) -> None:
    """
    The exact interval distance retains holes, missing tips and disjoint coverage instead of welding neighboring intervals.
    """
    assert (
        interval_coverage_gap(
            (Fraction(source[0]), Fraction(source[1])),
            tuple((Fraction(a), Fraction(b)) for a, b in intervals),
        )
        == expected
    )


def test_foreign_chain_owners_and_resource_stop_are_rejected() -> None:
    """
    Numerically equal replacement owners cannot inherit a boundary-chain receipt or bypass an allocation stop.
    """
    native, frame, graph = fixture()
    controls = ((Fraction(0), Fraction(0)), (Fraction(2), Fraction(0)))
    first = bound(native, frame, graph, BoundarySide.END0, controls)
    foreign = bound(native, replace(frame), graph, BoundarySide.END0, controls)
    with pytest.raises(ValueError, match="SAME native surface"):
        FiniteBoundaryChain((first, foreign), checkpoint)

    def stop() -> None:
        """
        Refuse additional finite-boundary work after the shared allocation stops.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        FiniteBoundaryChain((first,), stop)
