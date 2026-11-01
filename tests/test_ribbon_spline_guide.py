"""
Verify directed spline guidance, exact mirror branches and bounded contact selection.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Callable

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold
from experiments.experiment_ribbon_spline_guide.branches import Branch, branches, mirror_departure
from experiments.experiment_ribbon_spline_guide.guide import Guide, agreement
from experiments.experiment_ribbon_spline_guide.solve import solve


def _route(geometries: tuple[Piece, ...]) -> FoldRoute:
    """
    Create analytical endpoints without archived fixtures or native-coverage claims.
    """
    start = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    pose = start
    pieces = []
    for geometry in geometries:
        piece = PlacedPiece(pose, geometry, "analytical")
        pieces.append(piece)
        pose = piece.end_pose()
    targets = Targets(
        "analytical guide",
        start.origin,
        pose.origin,
        start.tangent,
        pose.tangent,
        start.width,
        pose.width,
        1,
        1.0,
    )
    return FoldRoute(targets, tuple(pieces), 1.0)


def _checkpoint() -> None:
    """
    Leave unit examples unbounded by wall time without changing physical decisions.
    """


def _record(event: dict[str, Any]) -> None:
    """
    Ignore synthetic proposal persistence in tests of other behavior.
    """
    del event


def test_guide_matches_directed_caps_and_scales_with_layout() -> None:
    """
    Preserve arrival travel sign and use no absolute-distance handle tuning.
    """
    source = _route((Straight(5), fold(1, 1.2, 1.3, 0.3, 0), Straight(8)))
    targets = source.targets
    guide = Guide.create(targets)
    for u, point, tangent in (
        (0, targets.start, targets.start_tangent),
        (1, targets.end, targets.end_tangent),
    ):
        actual, velocity = guide.sample(u)
        assert magnitude(difference(actual, point)) < 1e-12
        assert dot(unit(velocity), tangent) == pytest.approx(1)
    scaled = Guide.create(replace(targets, end=targets.end.translated(targets.end, 2)))
    for u in (0.0, 0.17, 0.5, 0.91, 1.0):
        point, velocity = guide.sample(u)
        actual, actual_velocity = scaled.sample(u)
        assert magnitude(difference(actual, point.translated(point, 2))) < 1e-11
        assert magnitude(difference(actual_velocity, velocity.translated(velocity, 2))) < 1e-11


def test_straight_control_has_zero_ordered_guide_error() -> None:
    """
    Retain a direct route rather than adding bends to follow its reference.
    """
    source = _route((Straight(10),))
    guide = Guide.create(source.targets)
    score = agreement(source, guide)
    assert score.rms_mm < 1e-12 and score.mean_direction_loss < 1e-12
    options = branches(source, guide, _checkpoint, _record)
    assert len(options) == 1 and options[0].identifier == "direct"
    assert options[0].route.material_length_mm == pytest.approx(10)
    assert len(options[0].route.pieces) == 1


def test_departure_mirror_changes_bow_without_changing_complete_pose() -> None:
    """
    Reverse a closed half-turn pair together; never flip an isolated terminal fold.
    """
    turn = fold(1, 1.2, math.pi, 0, 0)
    geometries = (turn, Straight(9), turn, fold(1, 1.2, 0.7, 0.2, 0))
    original = _route(geometries)
    mirrored = _route(mirror_departure(geometries))
    assert magnitude(difference(original.targets.end, mirrored.targets.end)) < 1e-12
    assert magnitude(difference(original.targets.end_tangent, mirrored.targets.end_tangent)) < 1e-12
    assert magnitude(difference(original.targets.end_width, mirrored.targets.end_width)) < 1e-12
    assert (
        magnitude(
            difference(original.pieces[0].surface(0.5, 0)[0], mirrored.pieces[0].surface(0.5, 0)[0])
        )
        > 1
    )
    assert mirror_departure((turn, Straight(3))) == (turn, Straight(3))


def test_all_exact_spatial_branches_retain_caps_and_material() -> None:
    """
    Check both algebraic rotation roots and mirror choices on synthetic spatial caps.
    """
    source = _route(
        (
            Straight(5),
            fold(1, 1.2, 0.8, 0.3, 0),
            Straight(7),
            fold(1, 1.2, -1.1, -0.2, 0),
            Straight(6),
        )
    )
    events: list[dict[str, Any]] = []
    options = branches(source, Guide.create(source.targets), _checkpoint, events.append)
    assert 2 <= len(options) <= 8
    assert {b.identifier.split("-")[0] for b in options} == {"root0", "root1"}
    assert all(cap_error(b.route) < 1e-7 and material_error(b.route) < 1e-10 for b in options)
    assert all(b.route.targets == source.targets and b.rewrites_evaluated <= 24 for b in options)
    assert any(e["stage"] == "closed_branch" for e in events)


@pytest.mark.parametrize("status", ["penetration", "unresolved"])
def test_contact_failure_never_passes_or_exceeds_four_branches(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """
    Preserve the baseline, failed candidates and skipped alternatives at budget end.
    """
    source = _route((Straight(10),))
    guide = Guide.create(source.targets)
    options = tuple(Branch(str(i), source, agreement(source, guide), 0) for i in range(8))

    def candidates(*args: Any) -> tuple[Branch, ...]:
        """
        Supply more exact candidates than the independent contact budget permits.
        """
        del args
        return options

    def contact(route: FoldRoute, *, checkpoint: Callable[[], None]) -> ContactResult:
        """
        Return an explicit physical rejection independent of guide agreement.
        """
        del route, checkpoint
        return ContactResult(status, 1)

    monkeypatch.setattr("experiments.experiment_ribbon_spline_guide.solve.branches", candidates)
    monkeypatch.setattr("experiments.experiment_ribbon_spline_guide.solve.inspect_contact", contact)
    result, details = solve(source, source, guide, _checkpoint, _record)
    assert result is source and details["contact_attempts"] == 4
    assert [b["status"] for b in details["branches"]] == [status] * 4 + [
        "contact_budget_unattempted"
    ] * 4


def test_zero_guide_gain_retains_baseline_with_real_contact_check() -> None:
    """
    Do not report an unchanged direct solution as a successful improvement.
    """
    source = _route((Straight(10),))
    result, details = solve(source, source, Guide.create(source.targets), _checkpoint, _record)
    assert result is source and details["reason"] == "candidate_did_not_improve_baseline_contract"


def test_guide_rejects_coincident_endpoints_and_out_of_range_parameters() -> None:
    """
    Refuse undefined handle scale and invalid diagnostic sample requests.
    """
    source = _route((Straight(10),))
    with pytest.raises(ValueError, match="Distinct"):
        Guide.create(replace(source.targets, end=source.targets.start))
    guide = Guide.create(source.targets)
    with pytest.raises(ValueError, match="parameter"):
        guide.sample(-0.1)
    with pytest.raises(ValueError, match="fraction"):
        guide.arc_sample(1.1)
