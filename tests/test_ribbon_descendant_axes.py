"""
Re-prove optional learned directions on complete descendant cells without inherited clearance.
"""

from __future__ import annotations

from dataclasses import fields, replace
from unittest.mock import Mock, patch

import pytest

from cable_bundler.routing.geometry import Vector3, cross, unit
from experiments.experiment_ribbon_fold_route import contact
from experiments.experiment_ribbon_fold_route.contact_axes import AxisContinuation, ProposedAxes
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_traversal import ContactTraversal
from tests.test_ribbon_probe_axis import _skew


def _proposal(index: int, delta: float) -> Vector3:
    """
    Perturb an analytical skew normal to model a useful direction learned before slight motion.
    """
    first, second = _skew(index).pieces
    normal = unit(cross(first.pose.tangent, second.pose.tangent))
    return unit(normal.translated(first.pose.tangent, delta).translated(second.pose.tangent, delta))


@pytest.mark.parametrize("index", (6, 7, 8))
@pytest.mark.parametrize("delta", (0.005, 0.01, 0.02))
def test_child_reproof_preserves_separation_and_reduces_actual_inverse_work(
    index: int,
    delta: float,
) -> None:
    """
    Compare identical authored geometry and proposed direction under the original finite ceiling.
    """
    route = _skew(index)
    results: list[contact.ContactResult] = []
    inversions: list[int] = []
    contexts: list[ProposedAxes] = []
    for policy in AxisContinuation:
        context = ProposedAxes(policy)
        contexts.append(context)
        inverse = Mock(wraps=contact.occupied_coordinates)
        with patch.dict(vars(contact), occupied_coordinates=inverse):
            results.append(
                contact.inspect_contact(
                    route,
                    maximum_pairs=2048,
                    cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                    witness_probe=Mock(
                        return_value=contact.ProbeResult(0, axis_proposal=_proposal(index, delta))
                    ),
                    probe_order=contact.ProbeOrder.MATERIAL_CELLS,
                    projection_reuse=contact.ProjectionReuse.CELLS,
                    proposed_axes=context,
                )
            )
        inversions.append(inverse.call_count)
    before, after = results
    assert before.status == after.status == "separated"
    assert after.pairs_checked <= before.pairs_checked
    assert inversions[1] <= inversions[0]
    useful = (index == 6 and delta >= 0.01) or delta == 0.02
    if useful:
        assert contexts[1].descendant_separations > 0
        assert after.pairs_checked < before.pairs_checked
        assert inversions[1] < inversions[0]
    else:
        assert after == before
        assert contexts[1].descendant_tests == 0


@pytest.mark.parametrize("index", range(5))
def test_optional_child_axis_cannot_hide_material_penetration(index: int) -> None:
    """
    Independently invert every reported actual strict crossing on both original members.
    """
    route = _skew(index)
    result = contact.inspect_contact(
        route,
        maximum_pairs=2048,
        witness_probe=Mock(return_value=contact.ProbeResult(0, axis_proposal=Vector3(0, 1, 0))),
        proposed_axes=ProposedAxes(AxisContinuation.MATERIAL_CELLS),
    )
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


@pytest.mark.parametrize("chunk", (1, 2))
def test_suspended_child_proofs_keep_one_context_and_original_ceiling(chunk: int) -> None:
    """
    Match uninterrupted work across resumptions without repeating the root proposal.
    """
    route = _skew(6)
    axis = _proposal(6, 0.02)
    expected_context = ProposedAxes(AxisContinuation.MATERIAL_CELLS)
    expected = contact.inspect_contact(
        route,
        maximum_pairs=32,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        witness_probe=Mock(return_value=contact.ProbeResult(0, axis_proposal=axis)),
        probe_order=contact.ProbeOrder.MATERIAL_CELLS,
        proposed_axes=expected_context,
    )
    probe = Mock(return_value=contact.ProbeResult(0, axis_proposal=axis))
    context = ProposedAxes(AxisContinuation.MATERIAL_CELLS)
    traversal = ContactTraversal(
        route,
        maximum_pairs=32,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        witness_probe=probe,
        proposed_axes=context,
    )
    result = traversal.advance(chunk)
    for limit in range(2 * chunk, 33, chunk):
        if result.limit != "pairs":
            break
        result = traversal.advance(limit)
    assert result == expected
    assert context.statistics() == expected_context.statistics()
    probe.assert_called_once()
    assert len(fields(expected)) == 9


@pytest.mark.parametrize("limit", ("pairs", "depth"))
def test_unhelpful_direction_cannot_override_exhaustion(limit: str) -> None:
    """
    Preserve finite unresolved dispositions when no strict separation was proved.
    """
    context = ProposedAxes(AxisContinuation.MATERIAL_CELLS)
    result = contact.inspect_contact(
        _skew(6),
        maximum_pairs=1 if limit == "pairs" else 2048,
        maximum_depth=1,
        witness_probe=Mock(return_value=contact.ProbeResult(0, axis_proposal=Vector3(1, 0, 0))),
        probe_order=contact.ProbeOrder.MATERIAL_CELLS,
        proposed_axes=context,
    )
    assert result.status == "unresolved" and result.limit == limit
    assert context.separations == 0


def test_context_cannot_transfer_proofs_even_to_equivalent_geometry() -> None:
    """
    Require a fresh context for every independent walk, including an identical source object.
    """
    route = _skew(6)
    context = ProposedAxes(AxisContinuation.MATERIAL_CELLS)
    contact.inspect_contact(route, proposed_axes=context)
    for source in (route, replace(route), _skew(7)):
        with pytest.raises(ValueError, match="fresh optional-axis context"):
            contact.inspect_contact(source, proposed_axes=context)


def test_fifo_retains_only_bounded_same_pair_directions_and_reprojects_both_cells() -> None:
    """
    Exercise eviction and cancellation protocol; physical decisions are tested on actual geometry above.
    """
    source = _skew(6)
    route = replace(source, pieces=(source.pieces[0],) * 67)
    context = ProposedAxes(AxisContinuation.MATERIAL_CELLS)
    context.bind(route)
    axis = Vector3(0, 0, 1)
    for index in range(2, 67):
        context.retain((0, index), axis)
    assert context.statistics()["retained_directions"] == 64
    first = Cell(0, Span(0, 0.5), Span(0, 1), Span(0, 1), 1)
    second = replace(first, piece=2)
    project = Mock(side_effect=(Span(0, 1), Span(2, 3)))
    assert not context.separates_descendants(first, second, project, None)
    project.assert_not_called()
    second = replace(second, piece=66)
    assert context.separates_descendants(first, second, project, None)
    assert project.call_args_list[0].args == (first, axis)
    assert project.call_args_list[1].args == (second, axis)
    guard = Mock(side_effect=InterruptedError("original guard"))
    with pytest.raises(InterruptedError, match="original guard"):
        context.separates_descendants(first, second, project, guard)
    assert project.call_count == 2 and context.tests == context.separations == 1


def test_unbound_context_and_invalid_material_identities_cannot_retain_direction() -> None:
    """
    Reject malformed pair ownership before retaining optional guidance.
    """
    context = ProposedAxes(AxisContinuation.MATERIAL_CELLS)
    axis = Vector3(0, 0, 1)
    with pytest.raises(ValueError, match="Bind a contact source"):
        context.retain((0, 1), axis)
    context.bind(_skew(6))
    for pair in ((1, 0), (0, 2), (True, 1)):
        with pytest.raises(ValueError, match="material identities"):
            context.retain(pair, axis)
