"""
Verify tolerance conversion, exact zero snapping and conservative reclosure/contact boundaries.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_zero_snap.snap import Policy, snap


def _route(lead: float) -> FoldRoute:
    """
    Compose a planar quarter turn with a small leading connector and a long exit.
    """
    start = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    pieces = []
    for shape in (
        Straight(lead),
        CylindricalFold(1.0, 1.5707963267948966, 0.0, 1.2, 0.0, 0.0),
        Straight(5.0),
    ):
        piece = PlacedPiece(
            start if not pieces else pieces[-1].end_pose(), shape, "analytical snap"
        )
        pieces.append(piece)
    end = pieces[-1].end_pose()
    targets = Targets(
        "zero snap analytical",
        start.origin,
        end.origin,
        start.tangent,
        end.tangent,
        start.width,
        end.width,
        1,
        1.0,
    )
    return FoldRoute(targets, tuple(pieces), 1.0)


def test_native_units_and_invalid_thresholds() -> None:
    """
    Use the centimeter-to-millimeter conversion and reject malformed numerical policy.
    """
    assert Policy(1e-6).threshold_mm == pytest.approx(1e-5)
    for invalid in (0.0, -1e-6, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite and positive"):
            Policy(invalid)


def test_no_snap_preserves_identity_without_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Leave geometry above the native threshold untouched without extra feasibility work.
    """
    route = _route(1e-4)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        """
        Reject unneeded projection/contact calls on an unchanged route.
        """
        raise AssertionError((args, kwargs))

    monkeypatch.setattr("experiments.experiment_ribbon_zero_snap.snap.reclose", forbidden)
    monkeypatch.setattr("experiments.experiment_ribbon_zero_snap.snap.inspect_contact", forbidden)
    result = snap(route, Policy(1e-6), lambda: None)
    assert result.route is route and result.status == "not_needed" and result.projections == 0


@pytest.mark.parametrize("status", ("separated", "penetration", "unresolved"))
def test_snap_recloses_before_contact_and_never_waives_rejection(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """
    Reallocate surviving radius/exit travel to preserve both ordered caps after zeroing the lead.
    """
    source = _route(1.3e-6)
    calls: list[FoldRoute] = []

    def contact(
        route: FoldRoute, *, maximum_pairs: int, checkpoint: Callable[[], None]
    ) -> ContactResult:
        """
        Independently inspect the reclosed material plan before returning a controlled contact outcome.
        """
        checkpoint()
        assert maximum_pairs == 1024 and cap_error(route) < 1e-7 and material_error(route) < 1e-10
        assert (
            route.targets == source.targets
            and route.material_length_mm <= source.material_length_mm + 1e-8
        )
        assert len(route.pieces) == len(source.pieces) - 1
        assert all(
            not isinstance(p.geometry, Straight) or p.geometry.material_length_mm > 1e-5
            for p in route.pieces
        )
        calls.append(route)
        return ContactResult(status, maximum_pairs)

    monkeypatch.setattr("experiments.experiment_ribbon_zero_snap.snap.inspect_contact", contact)
    result = snap(source, Policy(1e-6), lambda: None)
    assert len(calls) == 1 and result.removed_lengths_mm == pytest.approx((1.3e-6,))
    assert 0 < result.projections <= 2 * (2 * 1 + 2)
    assert result.contact_status == status
    assert result.maximum_parameter_change_mm <= 1e-5
    if status == "separated":
        assert result.route is calls[0] and result.status == "snapped_reclosed_and_separated"
    else:
        assert result.route is None and result.status == "contact_" + status


def test_resource_stop_is_not_swallowed() -> None:
    """
    Propagate the phase controller's hard stop before projecting or checking contact.
    """

    def stop() -> None:
        """
        Model the bounded phase reaching its source/time/memory gate.
        """
        raise TimeoutError("snap unit stop")

    with pytest.raises(TimeoutError, match="snap unit stop"):
        snap(_route(1.3e-6), Policy(1e-6), stop)


@pytest.mark.parametrize("returns_sliver", (False, True))
def test_unresolved_projection_or_remaining_sliver_never_reaches_contact(
    monkeypatch: pytest.MonkeyPatch,
    returns_sliver: bool,
) -> None:
    """
    Do not publish the original failing feature when reclosure fails or leaves tiny geometry.
    """
    source = _route(1.3e-6)

    def project(*args: Any) -> tuple[FoldRoute | None, int]:
        """
        Isolate the failed-closure and failed-canonicalization boundaries.
        """
        del args
        return (source if returns_sliver else None), 3

    def forbidden(*args: Any, **kwargs: Any) -> None:
        """
        Reject a physical acceptance attempt before canonicalization is established.
        """
        raise AssertionError((args, kwargs))

    monkeypatch.setattr("experiments.experiment_ribbon_zero_snap.snap.reclose", project)
    monkeypatch.setattr("experiments.experiment_ribbon_zero_snap.snap.inspect_contact", forbidden)
    result = snap(source, Policy(1e-6), lambda: None)
    assert (
        result.route is None and result.projections == 3 and result.contact_status == "unattempted"
    )
    assert result.status == ("numerical_gate_rejected" if returns_sliver else "closure_unresolved")
