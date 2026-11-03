"""
Recover a progressing algebraic branch only after original contact acceptance fails.
"""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_feature_insertion import solve as construction
from experiments.experiment_ribbon_feature_insertion.allocation import Allocation
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.reclosure import Unclosed
from experiments.experiment_ribbon_feature_insertion.reclosure import refine as refine_branch
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_joint_route.boundary import Boundary


def _run(record: list[dict[str, Any]]) -> construction.Result:
    """
    Recreate the gym input with both closed and still-progressing exact-root branches.
    """
    scene = Scene(Config(1041927501, 5, 0.75, 300, 300), Goal(18, 11, 1), Goal(6, 2, 1))
    frames = Frames.create(scene.targets)
    radius = scene.targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    return construction.construct(
        Boundary(frames.targets, radius), frames, (0.5,), 1e-5, lambda: None, record.append
    )


def test_contact_failure_does_not_hide_existing_progressing_branch() -> None:
    """
    Close and certify the closest pending root without accepting the original depth-limited route.
    """
    rows: list[dict[str, Any]] = []
    result = _run(rows)
    assert result.route is not None and result.allocation is not None
    assert result.allocation.chain.roots == (1, 1)
    assert result.contacts == 3 and result.contact_pairs == 748
    continuation = [r for r in rows if r["stage"] == "feature_closure_continuation"]
    assert len(continuation) == 1 and continuation[0]["maximum_additional_steps"] == 4
    contacts = [r for r in rows if r["stage"] == "feature_contact" and "contact" in r]
    assert [r["status"] for r in contacts] == ["penetration", "unresolved", "separated"]
    assert contacts[1]["contact"]["limit"] == "depth"
    assert contacts[-1]["pair_budget_remaining"] == 1300


@pytest.mark.parametrize("status", ("penetration", "unresolved"))
def test_recovered_closure_still_requires_actual_contact_acceptance(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Stop after the single allowed continuation if its new certificate also fails.
    """
    contact = Mock(return_value=ContactResult(status, 1))
    monkeypatch.setitem(vars(construction), "inspect_contact", contact)
    rows: list[dict[str, Any]] = []
    result = _run(rows)
    assert result.route is None and result.contacts == result.closed_branches == 3
    assert contact.call_count == 3 and result.contact_pairs == 3
    assert len([r for r in rows if r["stage"] == "feature_closure_continuation"]) == 1


@pytest.mark.parametrize("separated", (True, False))
def test_accepted_baseline_or_exhausted_pair_work_skips_continuation(
    monkeypatch: pytest.MonkeyPatch, separated: bool
) -> None:
    """
    Spend no continuation work after success or after two full rejected certificates.
    """
    contact = Mock(return_value=ContactResult("separated" if separated else "unresolved", 1024))
    monkeypatch.setitem(vars(construction), "inspect_contact", contact)
    rows: list[dict[str, Any]] = []
    result = _run(rows)
    assert (result.route is not None) is separated
    assert not any(r["stage"] == "feature_closure_continuation" for r in rows)
    assert result.contacts <= 2 and result.contact_pairs <= 2048


def test_hard_failure_in_continuation_is_not_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Propagate resource errors instead of retaining a contact-rejected baseline.
    """

    def refine(
        boundary: Boundary,
        unfinished: Unclosed,
        threshold_mm: float,
        maximum_steps: int,
        checkpoint: Callable[[], None],
        record: Callable[[dict[str, Any]], None],
    ) -> Allocation | Unclosed | None:
        """
        Permit original refinement and model a resource stop at the recovery boundary.
        """
        if maximum_steps == 4:
            raise TimeoutError("continuation resource stop")
        return refine_branch(boundary, unfinished, threshold_mm, maximum_steps, checkpoint, record)

    monkeypatch.setitem(vars(construction), "refine", refine)
    monkeypatch.setitem(
        vars(construction), "inspect_contact", Mock(return_value=ContactResult("penetration", 1))
    )
    with pytest.raises(TimeoutError, match="continuation resource stop"):
        _run([])
