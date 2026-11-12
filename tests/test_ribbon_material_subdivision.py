"""
Preserve complete material coverage and strict contact gates under phase-guided cuts.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import cast

import pytest

from experiments.experiment_ribbon_fold_route.contact import ProjectionReuse, inspect_contact
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.contact_subdivision import Subdivision, subdivide
from experiments.experiment_ribbon_fold_route.contact_traversal import ContactTraversal
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_restoration_handoff import _source


@pytest.mark.parametrize("scale", (1e-3, 1.0, 1e3))
@pytest.mark.parametrize("bank", (-0.7, 0.0, 0.7))
@pytest.mark.parametrize("angle", (-1.2, 1.2))
def test_phase_cuts_preserve_parent_material_and_depth(
    scale: float, bank: float, angle: float
) -> None:
    """
    Partition all material at an actual current-width phase transition across signs and scales.
    """
    geometry = fold(2 * scale, 1.2 * scale, angle, bank, scale)
    cell = Cell(3, Span(0, 1), Span(-0.6 * scale, 0.6 * scale), Span(-0.1 * scale, 0.1 * scale), 7)
    first, second = subdivide(cell, geometry, Subdivision.MATERIAL_PHASES)
    assert first.piece == second.piece == cell.piece
    assert first.depth == second.depth == cell.depth + 1
    assert first.q is second.q is cell.q and first.height is second.height is cell.height
    assert first.u.low == cell.u.low < first.u.high == second.u.low < second.u.high == cell.u.high
    cuts = tuple(value for q in (cell.q.low, cell.q.high) for value in geometry.bend_interval(q))
    assert first.u.high in cuts
    assert subdivide(cell, geometry, Subdivision.MIDPOINT) == cell.split(
        geometry.material_length_mm
    )


@pytest.mark.parametrize("cuts", ((), (math.nan, math.inf, -math.inf, 0, 1, -0.1, 1.1)))
def test_invalid_or_boundary_hints_keep_midpoint_and_other_dimensions_ignore_hints(
    cuts: tuple[float, ...],
) -> None:
    """
    Nonfinite/outside/boundary cuts never omit a slab or create an empty child.
    """
    cell = Cell(0, Span(0, 1), Span(-1, 1), Span(-0.1, 0.1))
    assert cell.split(10, longitudinal_cuts=cuts) == cell.split(10)
    assert cell.split(1, longitudinal_cuts=(0.3,)) == cell.split(1)
    thick = Cell(0, Span(0, 0.01), Span(-0.1, 0.1), Span(-2, 2))
    assert thick.split(10, longitudinal_cuts=(0.003,)) == thick.split(10)
    assert cell.split(2, longitudinal_cuts=(0.25, 0.75))[0].u.high == 0.25
    assert subdivide(cell, Straight(10), Subdivision.MATERIAL_PHASES) == cell.split(10)


def test_phase_contact_and_resumption_keep_strict_witness_and_original_budget() -> None:
    """
    Actual occupied material rejects without accepting budget exhaustion; suspended walks retain policy.
    """
    route = _source()
    result = inspect_contact(
        route,
        maximum_pairs=2048,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        projection_reuse=ProjectionReuse.CELLS,
        subdivision=Subdivision.MATERIAL_PHASES,
    )
    assert result.status == "penetration" and result.witness is not None
    witness = result.witness
    for index, expected in zip(witness.pieces, (witness.first, witness.second)):
        assert (
            occupied_coordinates(
                route.pieces[index], witness.point, route.targets.lines, route.targets.diameter_mm
            )
            == expected
        )
    traversal = ContactTraversal(
        route,
        maximum_pairs=2048,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        projection_reuse=ProjectionReuse.CELLS,
        subdivision=Subdivision.MATERIAL_PHASES,
    )
    partial = traversal.advance(1)
    assert (
        partial.status == "unresolved" and partial.limit == "pairs" and partial.pairs_checked == 1
    )
    assert asdict(traversal.advance(2048)) == asdict(result)


@pytest.mark.parametrize("policy", tuple(Subdivision))
def test_both_policies_require_complete_separation_for_an_authored_gentle_route(
    policy: Subdivision,
) -> None:
    """
    A clear positive control needs the same full analytic proof; unknown policies reject.
    """
    route = _route((Straight(5), fold(2, 1.2, 1.0, 0.4, 1), Straight(5)))
    result = inspect_contact(
        route, maximum_pairs=2048, cap_policy=CapPolicy.ANALYTIC_SUPPORT, subdivision=policy
    )
    assert result.status == "separated" and result.limit is None
    with pytest.raises(ValueError, match="subdivision"):
        inspect_contact(route, subdivision=cast(Subdivision, cast(object, "guessed")))
