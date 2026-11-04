"""
Verify aesthetic certificates follow exact geometry and never bypass changed-route checking.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_aesthetic.solve import ContactSchedule
from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_locked_solver import smoothing_contact, solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from tests.test_ribbon_aesthetic import _route


def _sequence(
    monkeypatch: pytest.MonkeyPatch,
    event: dict[str, Any],
    final: FoldRoute,
) -> None:
    """
    Replace the costly aesthetic stages while keeping their actual recorder contract.
    """

    def run(
        first: FoldRoute,
        percent: float,
        checkpoint: Callable[[], None],
        record: Callable[[dict[str, Any]], None],
        *,
        contact_schedule: ContactSchedule = ContactSchedule.PER_STEP,
    ) -> tuple[FoldRoute, dict[str, str]]:
        """
        Forward an immutable proposal then return the declared final geometry.
        """
        del first, percent
        assert contact_schedule is ContactSchedule.FINAL_DESCENT
        checkpoint()
        record(event)
        return final, {"radius_easing": "iteration_budget"}

    monkeypatch.setitem(vars(smoothing_contact), "smooth", run)


def test_separated_certificate_survives_exact_reconstruction_and_final_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reuse a complete1563pair certificate without subjecting it to a smaller final budget.
    """
    first = _route((Straight(10),))
    final = restore(snapshot(first))
    contact = ContactResult("separated", 1563, reason="completed smoothing check")
    event = {"status": "accepted", "contact": asdict(contact), "route": snapshot(final)}
    _sequence(monkeypatch, event, final)
    rows: list[dict[str, Any]] = []
    smoothed = smoothing_contact.smooth_with_contact(first, 1, lambda: None, rows.append)
    assert smoothed.route is final and smoothed.contact == contact
    assert rows == [event]
    monkeypatch.setitem(
        vars(solver_v2),
        "construct",
        Mock(
            return_value=SimpleNamespace(
                route=first,
                contact=ContactResult("separated", 749),
                status="separated",
                contacts=1,
                contact_pairs=749,
                contact_seconds=0.0,
                closed_branches=1,
                unattempted_contacts=0,
                rejected=(),
            )
        ),
    )
    audit = Mock(side_effect=AssertionError("Exact final route already certified"))
    monkeypatch.setitem(vars(solver_v2), "inspect_contact", audit)
    result = solver_v2.solve(first.targets, Settings(1, False, False), lambda: None, rows.append)
    assert result.route is final
    assert result.detail["final_contact_source"] == "identical_accepted_smoothing_geometry"
    assert result.detail["contact_measurement"]["pairs_checked"] == 1563
    assert result.detail["status"] == "numerically_accepted"
    audit.assert_not_called()
    _sequence(monkeypatch, {**event, "status": "contact_started"}, final)
    audit.side_effect = None
    audit.return_value = ContactResult("unresolved", 1024, limit="pairs")
    unmeasured = solver_v2.solve(
        first.targets, Settings(1, False, False), lambda: None, rows.append
    )
    audit.assert_called_once()
    assert unmeasured.route is None
    assert unmeasured.detail["final_contact_source"] == "final_geometry_audit"


@pytest.mark.parametrize("change", ("radius", "target", "piece"))
def test_any_changed_material_snapshot_requires_fresh_contact(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """
    Do not carry evidence across even sub-tolerance changes in any authoritative geometry.
    """
    source = _route((Straight(10),))
    if change == "radius":
        final = replace(source, radius_mm=source.radius_mm + 1e-12)
    elif change == "target":
        final = replace(source, targets=replace(source.targets, diameter_mm=1 + 1e-12))
    else:
        piece = replace(source.pieces[0], geometry=Straight(10 + 1e-12))
        final = replace(source, pieces=(piece,))
    event = {
        "status": "accepted",
        "contact": asdict(ContactResult("separated", 1563)),
        "route": snapshot(source),
    }
    _sequence(monkeypatch, event, final)
    result = smoothing_contact.smooth_with_contact(source, 1, lambda: None, lambda item: None)
    assert result.contact is None


@pytest.mark.parametrize(
    "change",
    (
        {"status": "penetration"},
        {"status": "unresolved", "limit": "pairs"},
        {"status": "separated", "limit": "depth"},
        {"pairs_checked": True},
        {"pairs_checked": -1},
        {"witness": {}},
    ),
)
def test_failed_incomplete_or_malformed_measurements_are_not_reused(
    monkeypatch: pytest.MonkeyPatch, change: dict[str, Any]
) -> None:
    """
    Require a complete separated measurement even when an event claims acceptance.
    """
    source = _route((Straight(10),))
    contact = {**asdict(ContactResult("separated", 1563)), **change}
    event = {"status": "accepted", "contact": contact, "route": snapshot(source)}
    _sequence(monkeypatch, event, source)
    result = smoothing_contact.smooth_with_contact(source, 1, lambda: None, lambda item: None)
    assert result.contact is None


def test_rejected_proposal_cannot_certify_the_final_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep result and logging errors authoritative despite a valid-looking contact object.
    """
    source = _route((Straight(10),))
    event = {
        "status": "peak_lane_curvature_rejected",
        "contact": asdict(ContactResult("separated", 1563)),
        "route": snapshot(source),
    }
    _sequence(monkeypatch, event, source)
    result = smoothing_contact.smooth_with_contact(source, 1, lambda: None, lambda item: None)
    assert result.contact is None
    with pytest.raises(OSError, match="logging failed"):
        smoothing_contact.smooth_with_contact(
            source, 1, lambda: None, Mock(side_effect=OSError("logging failed"))
        )
