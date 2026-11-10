"""
Reuse optional direction proposals only through the original complete material interval proof.
"""

from __future__ import annotations

import math
from dataclasses import asdict, replace
from typing import Any, Callable, Literal
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, cross, unit
from experiments.experiment_ribbon_fold_route import contact
from experiments.experiment_ribbon_fold_route.contact import ProbeResult, ProjectionReuse
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route

_DISTANCES = (0.0, 0.2, 0.6, 0.9, 1.05, 1.3, 1.7, 1.8, 2.0, 2.2, 2.5, 3.0)


def _banked_width(tangent: Vector3, bank: float) -> Vector3:
    """
    Rotate an orthogonal width around the analytical member's unit tangent.
    """
    base = unit(cross(tangent, Vector3(0, 1, 0)))
    normal = cross(tangent, base)
    c, s = math.cos(bank), math.sin(bank)
    return Vector3(base.x * c + normal.x * s, base.y * c + normal.y * s, base.z * c + normal.z * s)


def _skew(index: int) -> FoldRoute:
    """
    Author analytical skew-member controls; these are not complete-ribbon qualification cases.
    """
    phi, theta, psi, delta = (
        -0.45 + 0.07 * index,
        0.55 + 0.08 * index,
        0.4 + 0.13 * index,
        0.38 + 0.09 * index,
    )
    ta, wa = Vector3(1, 0, 0), Vector3(0, math.cos(phi), math.sin(phi))
    tb = unit(
        Vector3(math.cos(theta), math.sin(theta) * math.cos(psi), math.sin(theta) * math.sin(psi))
    )
    wb = _banked_width(tb, delta)
    gap = unit(cross(ta, tb))
    distance = _DISTANCES[index]
    start = Vector3(
        gap.x * distance - tb.x * 10, gap.y * distance - tb.y * 10, gap.z * distance - tb.z * 10
    )
    pieces = (
        PlacedPiece(Pose(Vector3(-10, 0, 0), ta, wa), Straight(20), "analytical skew A"),
        PlacedPiece(Pose(start, tb, wb), Straight(20), "analytical skew B"),
    )
    return replace(_route((Straight(20),)), pieces=pieces)


def _inspect(route: FoldRoute, probe: Any) -> contact.ContactResult:
    """
    Keep the same profile, cap policy, finite comparison ceiling and exact projection cache mode.
    """
    return contact.inspect_contact(
        route,
        maximum_pairs=2048,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        projection_reuse=ProjectionReuse.CELLS,
        witness_probe=probe,
    )


@pytest.mark.parametrize("index", range(12))
def test_axis_reuses_existing_queries_and_preserves_collision_decisions(index: int) -> None:
    """
    Compare with the identical probe discarding only its proposed direction, independently checking witnesses.
    """
    route = _skew(index)
    baseline_probe, proposed_probe = FlatProbe(), FlatProbe()

    def without_axis(
        source: FoldRoute,
        first: int,
        second: int,
        remaining: int,
        checkpoint: Callable[[], None] | None,
    ) -> ProbeResult:
        """
        Retain every original witness/support comparison while disabling only the new interval proposal.
        """
        return replace(
            baseline_probe(source, first, second, remaining, checkpoint), axis_proposal=None
        )

    baseline, proposed = _inspect(route, without_axis), _inspect(route, proposed_probe)
    before, after = asdict(baseline), asdict(proposed)
    before.pop("pairs_checked")
    after.pop("pairs_checked")
    for field in ("axis_tests", "axis_separations"):
        before.pop(field)
        after.pop(field)
    assert after == before and asdict(proposed_probe) == asdict(baseline_probe)
    assert baseline.axis_tests == baseline.axis_separations == 0
    assert 0 <= proposed.axis_separations <= proposed.axis_tests
    assert proposed.pairs_checked <= baseline.pairs_checked
    if index in (6, 7, 8):
        assert baseline.pairs_checked == {6: 22, 7: 18, 8: 14}[index]
        assert proposed.pairs_checked == 2
        assert proposed.axis_tests == proposed.axis_separations == 1
    if proposed.witness is not None:
        for piece in proposed.witness.pieces:
            assert (
                occupied_coordinates(
                    route.pieces[piece],
                    proposed.witness.point,
                    route.targets.lines,
                    route.targets.diameter_mm,
                )
                is not None
            )


@pytest.mark.parametrize(
    "axis",
    (
        Vector3(0, 0, 0),
        Vector3(math.nan, 0, 1),
        Vector3(math.inf, 1, 0),
        Vector3(True, 0, 1),
        "not a vector",
    ),
)
def test_invalid_optional_direction_cannot_certify_material(axis: Any) -> None:
    """
    Reject malformed nonzero/finite contracts before using an external probe's proposed direction.
    """
    probe = Mock(return_value=ProbeResult(0, axis_proposal=axis))
    with pytest.raises(ValueError, match="finite nonzero"):
        _inspect(_skew(6), probe)


@pytest.mark.parametrize("limit", ("pairs", "supports"))
def test_incomplete_probe_does_not_transfer_direction_authority(
    limit: Literal["pairs", "supports"],
) -> None:
    """
    Pair exhaustion stays unresolved; support exhaustion resumes the unchanged full interval proof.
    """
    route = _skew(6)
    invalid_axis: Any = "invalid if used"
    probe = Mock(return_value=ProbeResult(0, limit=limit, axis_proposal=invalid_axis))
    result = _inspect(route, probe)
    if limit == "pairs":
        assert result.status == "unresolved" and result.limit == "pairs"
    else:
        assert result == _inspect(route, None)


def test_an_unhelpful_axis_cannot_override_an_actual_penetration() -> None:
    """
    A guessed direction adds no positive evidence when its full material intervals overlap.
    """
    route = _skew(2)
    probe = Mock(return_value=ProbeResult(0, axis_proposal=Vector3(0, 1, 0)))
    result = _inspect(route, probe)
    assert result.status == "penetration" and result.witness is not None
    probe.assert_called_once()
    for piece in result.witness.pieces:
        assert (
            occupied_coordinates(
                route.pieces[piece],
                result.witness.point,
                route.targets.lines,
                route.targets.diameter_mm,
            )
            is not None
        )


def test_proposal_verification_keeps_the_original_caller_guard() -> None:
    """
    Cancellation or exhausted work after a probe prevents the extra interval proof from accepting.
    """
    finished = [False]

    def propose(
        route: FoldRoute,
        first: int,
        second: int,
        remaining_pairs: int,
        checkpoint: Callable[[], None] | None,
    ) -> ProbeResult:
        """
        Return a potentially useful direction after the caller's time or cancellation state changes.
        """
        assert 0 <= first < second < len(route.pieces) and remaining_pairs > 0
        assert checkpoint is not None
        finished[0] = True
        return ProbeResult(0, axis_proposal=Vector3(0, 0, 1))

    def guard() -> None:
        """
        Preserve the original caller failure instead of treating it as a missed optional proposal.
        """
        if finished[0]:
            raise TimeoutError("original work exhausted")

    with pytest.raises(TimeoutError, match="original work exhausted"):
        contact.inspect_contact(_skew(6), witness_probe=propose, checkpoint=guard)


def test_flat_probe_direction_still_checks_curved_material(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Force interval fallback where a straight crosses the circular portion between separated flat phases.
    """
    source = _route((fold(2, 1.2, math.pi, 0, 1.5),))
    straight = PlacedPiece(
        Pose(Vector3(3.0, 0, 2), Vector3(1, 0, 0), Vector3(0, 1, 0)),
        Straight(1),
        "curved interior crossing",
    )
    route = replace(source, pieces=(*source.pieces, straight))
    original = contact.occupied_coordinates
    calls = [0]

    def miss_initial_points(
        candidate: PlacedPiece, point: Vector3, lines: int, diameter: float
    ) -> tuple[float, float, float] | None:
        """
        Make only the first root-point search inconclusive; subsequent inversions remain actual strict checks.
        """
        calls[0] += 1
        return None if calls[0] <= 2 else original(candidate, point, lines, diameter)

    monkeypatch.setitem(vars(contact), "occupied_coordinates", miss_initial_points)
    probe = Mock(return_value=ProbeResult(0, axis_proposal=Vector3(0, 0, 1)))
    result = _inspect(route, probe)
    assert result.status == "penetration" and result.witness is not None
    probe.assert_called_once()
    for piece in result.witness.pieces:
        assert (
            original(
                route.pieces[piece],
                result.witness.point,
                route.targets.lines,
                route.targets.diameter_mm,
            )
            is not None
        )
