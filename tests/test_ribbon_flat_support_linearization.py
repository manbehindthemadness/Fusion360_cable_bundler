"""
Verify complete-support derivatives and bounded linear expansion on independently authored flat geometry.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, cross, unit
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, locate
from experiments.experiment_ribbon_fold_relaxation.steps import advance
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_separation import FlatPart, FlatSeparation
from experiments.experiment_ribbon_terminal_hardware.flat_support_linearization import (
    active_supports,
    linearize,
)
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import Difference, jacobian
from tests.test_ribbon_terminal_protection import _two_folds


def _case(scale: float, sign: float) -> tuple[SignedJoints, FlatSeparation]:
    """
    Bind full BEFORE and straight prisms on a mirrored two-bend route, with a tied straight-face support.
    """
    source = _two_folds(scale, sign, 2.0)
    model = SignedJoints(source)
    pair = Region(0, False), Region(1, True)
    second = locate(source, model.pieces(model.initial), pair[1])
    axis = unit(cross(second.pose.tangent, second.pose.width))
    parts = (
        FlatPart(
            FlatPhase.BEFORE,
            -source.half_width_mm,
            source.half_width_mm,
            source.targets.diameter_mm / 2,
        ),
        FlatPart(
            FlatPhase.STRAIGHT,
            -source.half_width_mm,
            source.half_width_mm,
            source.targets.diameter_mm / 2,
        ),
    )
    return model, FlatSeparation(model, pair, parts, axis)


def _equations(
    flat: FlatSeparation, side: Side, minimum_gap_mm: float = 1e-8
) -> Callable[[tuple[float, ...]], tuple[float, ...]]:
    """
    Isolate support algebra with six neutral cap rows, without asserting physical feasibility.
    """

    def evaluate(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Preserve the exact full-region nonlinear material residual.
        """
        return (0.0,) * 6 + (minimum_gap_mm / flat.model.scale - flat.gap(values, side),)

    return evaluate


@pytest.mark.parametrize("minimum_gap_mm", [1e-8, 1e-7])
def test_expansion_preserves_the_callers_physical_gap(minimum_gap_mm: float) -> None:
    """
    Different correction policies retain their original gap rather than inheriting a weaker threshold.
    """
    model, flat = _case(1, 1)
    side = max(
        Side, key=lambda candidate: _equations(flat, candidate, minimum_gap_mm)(model.initial)[-1]
    )
    evaluate = _equations(flat, side, minimum_gap_mm)
    terms = evaluate(model.initial)
    rows = jacobian(
        model,
        model.initial,
        evaluate,
        7,
        set(),
        lambda: None,
        admissible=model.admissible,
        difference=Difference.ONE_SIDED,
    )
    expanded = linearize(
        [(flat, side)],
        model.initial,
        terms,
        rows,
        model,
        set(),
        model.admissible,
        lambda: None,
        minimum_gap_mm=minimum_gap_mm,
    )
    assert expanded.bundles == 1 and expanded.topology_declines == 0
    assert max(expanded.terms[6:]) == pytest.approx(terms[-1], abs=1e-13)
    assert expanded.supports[0].minimum_gap_mm == minimum_gap_mm


@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
@pytest.mark.parametrize("sign", (-1.0, 1.0))
@pytest.mark.parametrize("side", tuple(Side))
@pytest.mark.parametrize("minimum_gap_mm", [1e-8, 1e-7])
def test_complete_active_branches_match_raw_span_and_actual_direction(
    scale: float, sign: float, side: Side, minimum_gap_mm: float
) -> None:
    """
    Keep tied support extrema and signed height identities under both separation orders and scales.
    """
    model, flat = _case(scale, sign)
    values = model.initial
    bundle = active_supports(flat, side, values, minimum_gap_mm=minimum_gap_mm)
    base = bundle.residuals(values)
    assert base is not None and len(base) > 1
    raw = _equations(flat, side, minimum_gap_mm)
    assert max(base) == pytest.approx(raw(values)[-1], abs=1e-13)
    rows = jacobian(
        model,
        values,
        lambda v: bundle.residuals(v) or (),
        len(base),
        set(),
        lambda: None,
        admissible=model.admissible,
        difference=Difference.ONE_SIDED,
    )
    direction = tuple(
        -0.03 if full % 4 == 2 else 0.01 if full % 4 == 1 else 0.0 for full in model.indices
    )
    predicted = max(sum(a * b for a, b in zip(row, direction)) for row in rows)
    fraction = 1e-6
    moved = advance(model, values, direction, fraction)
    actual = (raw(moved)[-1] - raw(values)[-1]) / fraction
    assert predicted == pytest.approx(actual, abs=2e-5)
    moved_branches = bundle.residuals(moved)
    assert moved_branches is not None
    assert max(moved_branches) <= raw(moved)[-1] + 1e-13


@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
@pytest.mark.parametrize("sign", (-1.0, 1.0))
def test_bounded_expansion_preserves_raw_equations_and_fixed_columns(
    scale: float, sign: float
) -> None:
    """
    Expand every active branch within thirteen physical rows and retain native masks without mutating inputs.
    """
    model, flat = _case(scale, sign)
    values = model.initial
    side = min(Side, key=lambda s: flat.gap(values, s))
    evaluate = _equations(flat, side)
    terms = evaluate(values)
    fixed = {0}
    rows = jacobian(
        model,
        values,
        evaluate,
        7,
        fixed,
        lambda: None,
        admissible=model.admissible,
        difference=Difference.ONE_SIDED,
    )
    before = [list(row) for row in rows]
    output = linearize(
        [(flat, side)], values, terms, rows, model, fixed, model.admissible, lambda: None
    )
    assert output.bundles == 1 and 1 < len(output.terms) - 6 <= 13
    assert output.added_rows == len(output.terms) - len(terms)
    assert max(output.terms[6:]) == pytest.approx(terms[-1], abs=1e-13)
    assert all(row[0] == 0 for row in output.rows)
    assert rows == before and terms == evaluate(values)
    assert output.capacity_declines == output.topology_declines == 0
    full = (0.0,) * 12 + terms
    full_rows = [[0.0] * len(values) for _ in range(12)] + rows
    declined = linearize(
        [(flat, side)], values, full, full_rows, model, fixed, model.admissible, lambda: None
    )
    assert declined.bundles == 0 and declined.capacity_declines == 1
    assert declined.terms == full and declined.rows == tuple(tuple(row) for row in full_rows)


def test_changed_vertex_topology_and_cancellation_never_create_partial_rows() -> None:
    """
    A failed caller guard remains hard; malformed identity cannot silently substitute another vertex.
    """
    model, flat = _case(1, 1)
    values = model.initial
    bundle = active_supports(flat, Side.BEFORE, values)
    assert replace(bundle, sizes=(1, 1)).residuals(values) is None
    evaluate = _equations(flat, Side.BEFORE)
    terms = evaluate(values)
    with pytest.raises(InterruptedError, match="source stop"):
        linearize(
            [(flat, Side.BEFORE)],
            values,
            terms,
            [[0.0] * len(values) for _ in terms],
            model,
            set(),
            model.admissible,
            Mock(side_effect=InterruptedError("source stop")),
        )


@pytest.mark.parametrize("sign", (-1.0, 1.0))
def test_smooth_support_keeps_original_rows_without_more_derivative_queries(sign: float) -> None:
    """
    A unique support pair retains the ordinary derivative policy and allocates no additional probes.
    """
    model, original = _case(1, sign)
    flat = replace(original, axis=unit(Vector3(0.31, 0.5, 0.8)))
    values = model.initial
    side = min(Side, key=lambda s: flat.gap(values, s))
    assert len(active_supports(flat, side, values).pairs) == 1
    terms = _equations(flat, side)(values)
    rows = [[0.0] * len(values) for _ in terms]
    queries = Mock(side_effect=AssertionError("Smooth support needs no new endpoint"))
    output = linearize([(flat, side)], values, terms, rows, model, set(), queries, lambda: None)
    assert output.bundles == output.added_rows == 0
    assert output.terms == terms and output.rows == tuple(tuple(row) for row in rows)
    queries.assert_not_called()


@pytest.mark.parametrize("branch_slope", (-1.0, 1.0))
def test_branch_substitution_requires_a_contradictory_direction(branch_slope: float) -> None:
    """
    Keep successful scalar directions unless another active branch contradicts their predicted descent.
    """
    from experiments.experiment_ribbon_terminal_hardware.flat_support_linearization import (
        Linearization,
    )

    caps = (0.0,) * 6
    cap_rows = ((0.0,),) * 6
    original_terms = caps + (1.0,)
    original_rows = [list(row) for row in cap_rows + ((1.0,),)]
    bundle = Linearization(caps + (1.0, 1.0), cap_rows + ((1.0,), (branch_slope,)), 1, 1, 0, 0)
    assert bundle.contradicts(original_terms, original_rows, (-1.0,)) is (branch_slope < 0)
    assert not bundle.contradicts(original_terms, original_rows, (1.0,))
    assert not replace(bundle, bundles=0).contradicts(original_terms, original_rows, (-1.0,))
    with pytest.raises(ValueError, match="complete linear"):
        bundle.contradicts(original_terms, original_rows, ())


@pytest.mark.parametrize("sign", (-1.0, 1.0))
def test_memory_retains_support_branches_after_their_tie_splits(sign: float) -> None:
    """
    Keep diagnosed corners through an actual geometry change, while leaving unrelated constraints undiagnosed.
    """
    from experiments.experiment_ribbon_terminal_hardware.flat_support_linearization import (
        SupportMemory,
        SupportSelection,
    )

    model, flat = _case(1.0, sign)
    values = model.initial
    side = min(Side, key=lambda s: flat.gap(values, s))
    memory = SupportMemory()
    evaluate = _equations(flat, side)
    rows = jacobian(
        model,
        values,
        evaluate,
        7,
        set(),
        lambda: None,
        admissible=model.admissible,
        difference=Difference.ONE_SIDED,
    )
    untouched = linearize(
        [(flat, side)],
        values,
        evaluate(values),
        rows,
        model,
        set(),
        model.admissible,
        lambda: None,
        memory=memory,
        selection=SupportSelection.RETAIN,
    )
    assert untouched.bundles == 0 and not memory.active
    identified = linearize(
        [(flat, side)], values, evaluate(values), rows, model, set(), model.admissible, lambda: None
    )
    assert identified.bundles == 1 and identified.supports
    memory.remember(identified.supports)
    assert memory.active and memory.get(flat, side) is identified.supports[0]
    direction = tuple(
        -0.03 if full % 4 == 2 else 0.01 if full % 4 == 1 else 0.0 for full in model.indices
    )
    moved = advance(model, values, direction, 1e-3)
    terms = evaluate(moved)
    assert terms[-1] > 0
    rows = jacobian(
        model,
        moved,
        evaluate,
        7,
        set(),
        lambda: None,
        admissible=model.admissible,
        difference=Difference.ONE_SIDED,
    )
    retained = linearize(
        [(flat, side)],
        moved,
        terms,
        rows,
        model,
        set(),
        model.admissible,
        lambda: None,
        memory=memory,
        selection=SupportSelection.RETAIN,
    )
    assert retained.bundles == 1
    assert set(identified.supports[0].pairs) <= set(retained.supports[0].pairs)
    assert max(retained.terms[6:]) == pytest.approx(terms[-1], abs=1e-13)
    assert len(retained.terms) - 6 <= 13
    memory.remember(retained.supports)
    assert memory.get(replace(flat), side) is None
    assert memory.get(flat, Side.AFTER if side is Side.BEFORE else Side.BEFORE) is None
    memory.prune([])
    assert not memory.active
