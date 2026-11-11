"""
Verify strict negative-only flat witnesses, complete original proofs and bounded exact reuse.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route import contact
from experiments.experiment_ribbon_fold_route.contact import (
    Penetration,
    ProbeResult,
    ProjectionReuse,
)
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import profile_arcs
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import (
    occupied_coordinates,
    profile_height,
)
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece


def load_routes() -> dict[str, FoldRoute]:
    """
    Retire the shared saved-layout entry point without reading or replaying historical geometry.

    Keep dependent controls explicitly skipped under the user's fresh-input
    policy. Independently authored analytical controls remain available.
    """
    raise pytest.skip.Exception(
        "Saved ribbon layout retired under user-directed fresh-input policy"
    )


@pytest.fixture(scope="module")
def routes() -> dict[str, FoldRoute]:
    """
    Reuse immutable mathematical fixture geometry within this component test module.
    """
    return load_routes()


@pytest.mark.parametrize("lines,diameter", ((1, 0.2), (3, 0.75), (8, 0.75)))
def test_circle_intervals_match_the_existing_actual_joined_profile(
    lines: int, diameter: float
) -> None:
    """
    Preserve conductor-lobe valleys, side extensions and true full-interval height bounds.
    """
    arcs = profile_arcs(lines, diameter)
    assert len(arcs) == lines + 2
    assert arcs[0].low_q == pytest.approx(-(lines + 0.2) * diameter / 2)
    for arc in arcs:
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            q = arc.low_q + fraction * (arc.high_q - arc.low_q)
            assert arc.height(q) == pytest.approx(profile_height(q, lines, diameter), abs=1e-8)
            assert arc.height(q) <= arc.maximum_height() + 1e-12


def test_flat_probe_finds_a_real_narrow_crossing_without_a_saved_witness(
    routes: dict[str, FoldRoute],
) -> None:
    """
    Derive the point from geometry and require both unchanged strict actual material inverse maps.
    """
    route = routes["overlap"]
    probe = FlatProbe()
    measured = probe(route, 3, 7, 64, None)
    assert measured.witness is not None and measured.limit is None
    assert measured.pairs_checked <= 4 and probe.supports <= 2048
    witness = measured.witness
    for index in witness.pieces:
        coordinates = occupied_coordinates(
            route.pieces[index], witness.point, route.targets.lines, route.targets.diameter_mm
        )
        assert coordinates is not None
        assert profile_height(coordinates[1], route.targets.lines, route.targets.diameter_mm) > abs(
            coordinates[2]
        )


def test_negative_acceleration_preserves_a_shared_budget_for_later_full_proof(
    routes: dict[str, FoldRoute],
) -> None:
    """
    The retained tiny crossing must be found before spending the whole original correction pool.
    """
    result = contact.inspect_contact(
        routes["overlap"],
        maximum_pairs=610,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        witness_probe=FlatProbe(),
        projection_reuse=ProjectionReuse.CELLS,
    )
    assert result.status == "penetration" and result.witness is not None
    assert result.witness.pieces == (3, 7) and result.pairs_checked < 32


def test_missed_probe_cannot_approve_an_unresolved_route(routes: dict[str, FoldRoute]) -> None:
    """
    A missed optional witness leaves all original comparisons and strict contact requirements active.
    """
    probe = Mock(return_value=ProbeResult(0))
    result = contact.inspect_contact(
        routes["overlap"],
        maximum_pairs=32,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        witness_probe=probe,
    )
    assert probe.called and result.status == "unresolved" and result.pairs_checked == 32


def test_support_exhaustion_disables_only_the_optional_probe(routes: dict[str, FoldRoute]) -> None:
    """
    Complete interval certification still decides the route after a negative accelerator limit.
    """
    probe = Mock(return_value=ProbeResult(0, limit="supports"))
    result = contact.inspect_contact(
        routes["separated"],
        maximum_pairs=1024,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        witness_probe=probe,
        projection_reuse=ProjectionReuse.CELLS,
    )
    assert result.status == "separated" and probe.call_count == 1


@pytest.mark.parametrize("invalid", ("witness", "budget"))
def test_optional_probe_cannot_manufacture_clearance_or_extra_work(
    routes: dict[str, FoldRoute],
    invalid: str,
) -> None:
    """
    Recheck proposed interior points and validate comparison accounting at the core boundary.
    """

    def probe(
        route: FoldRoute,
        first: int,
        second: int,
        remaining_pairs: int,
        checkpoint: Callable[[], None] | None,
    ) -> ProbeResult:
        """
        Deliberately return a malformed internal callback result for contract verification.
        """
        assert 0 <= first < second < len(route.pieces)
        if checkpoint is not None:
            checkpoint()
        if invalid == "budget":
            return ProbeResult(remaining_pairs + 1)
        return ProbeResult(
            0,
            Penetration((first, second), (0.5, 0.0, 0.0), (0.5, 0.0, 0.0), Vector3(1e6, 1e6, 1e6)),
        )

    with pytest.raises(ArithmeticError):
        contact.inspect_contact(
            routes["overlap"],
            maximum_pairs=32,
            cap_policy=CapPolicy.ANALYTIC_SUPPORT,
            witness_probe=probe,
        )


def test_cell_projection_reuse_preserves_the_exact_complete_certificate(
    routes: dict[str, FoldRoute],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reuse only identical immutable bounds while preserving every comparison and result bit.
    """
    original = contact.prepare_projection
    evaluations = [0]

    def prepare(piece: PlacedPiece, direction: Vector3) -> Callable[[Cell], Span]:
        """
        Count full analytic evaluations without changing any returned bound.
        """
        evaluate = original(piece, direction)

        def bound(cell: Cell) -> Span:
            """
            Observe a real analytic bound evaluation.
            """
            evaluations[0] += 1
            return evaluate(cell)

        return bound

    monkeypatch.setitem(vars(contact), "prepare_projection", prepare)
    plain = contact.inspect_contact(
        routes["separated"], maximum_pairs=1024, cap_policy=CapPolicy.ANALYTIC_SUPPORT
    )
    plain_count = evaluations[0]
    evaluations[0] = 0
    cached = contact.inspect_contact(
        routes["separated"],
        maximum_pairs=1024,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        projection_reuse=ProjectionReuse.CELLS,
    )
    assert plain.status == "separated" and asdict(plain) == asdict(cached)
    assert evaluations[0] < plain_count
