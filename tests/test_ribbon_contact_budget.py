"""
Reuse unspent first-pass contact pair work without changing branch order or physical acceptance.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_feature_insertion import solve as construction
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_joint_route.boundary import Boundary


def _construct(
    monkeypatch: pytest.MonkeyPatch, outcomes: tuple[ContactResult, ...], allowances: list[int]
) -> construction.Result:
    """
    Keep three real algebraic closures while isolating the certificate's work accounting.
    """
    scene = Scene(Config(1281098652, 3, 0.75, 300, 300), Goal(18, 7, 1), Goal(12, 2, 1))
    frames = Frames.create(scene.targets)
    remaining = iter(outcomes)

    def measure(*args: Any, maximum_pairs: int, checkpoint: Callable[[], None]) -> ContactResult:
        """
        Return explicit dispositions and consumed work without claiming geometry coverage.
        """
        del args
        checkpoint()
        allowances.append(maximum_pairs)
        return next(remaining)

    monkeypatch.setitem(vars(construction), "inspect_contact", measure)
    radius = scene.targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    return construction.construct(
        Boundary(frames.targets, radius), frames, (0.5,), 1e-5, lambda: None, lambda e: None
    )


def test_cheap_rejections_leave_work_for_existing_third_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reach the remaining exact root with the original aggregate pair ceiling.
    """
    allowances: list[int] = []
    result = _construct(
        monkeypatch,
        (
            ContactResult("penetration", 135),
            ContactResult("penetration", 347),
            ContactResult("separated", 255),
        ),
        allowances,
    )
    assert allowances == [1024, 1024, 1024]
    assert result.contacts == result.closed_branches == 3
    assert result.contact_pairs == 737 < construction.CONTACT_PAIR_BUDGET
    assert result.route is not None and result.allocation is not None
    assert result.allocation.chain.roots == (0, 1)
    assert result.unattempted_contacts == 0 and result.status == "separated"


@pytest.mark.parametrize("second_pairs", (1024, 1000))
def test_exhausted_pair_pool_never_accepts_unmeasured_geometry(
    monkeypatch: pytest.MonkeyPatch, second_pairs: int
) -> None:
    """
    Stop after two full certificates or limit the third to exactly the remaining work.
    """
    allowances: list[int] = []
    remainder = 1024 - second_pairs
    outcomes = (
        ContactResult("unresolved", 1024, limit="pairs"),
        ContactResult("penetration", second_pairs),
        ContactResult("unresolved", remainder, limit="pairs"),
    )
    result = _construct(monkeypatch, outcomes, allowances)
    assert allowances == [1024, 1024] + ([remainder] if remainder else [])
    assert result.contact_pairs == construction.CONTACT_PAIR_BUDGET
    assert result.route is None and result.status == "no_separated_chain"
    assert result.contacts == len(allowances)
    assert result.unattempted_contacts == result.closed_branches - result.contacts


def test_reported_work_cannot_overrun_certificate_allowance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Treat inconsistent external measurement accounting as a hard error.
    """
    with pytest.raises(ArithmeticError, match="pair allowance"):
        _construct(monkeypatch, (ContactResult("separated", 1025),), [])


def test_zero_work_failures_still_stop_at_finite_derived_branch_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve a finite root bound when rejection happens before subdivision.
    """
    allowances: list[int] = []
    result = _construct(monkeypatch, (ContactResult("unresolved", 0),) * 3, allowances)
    assert result.route is None and result.contacts == result.closed_branches == 3
    assert result.contact_pairs == 0 and allowances == [1024] * 3
