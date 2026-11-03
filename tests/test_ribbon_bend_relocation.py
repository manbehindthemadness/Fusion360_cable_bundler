"""
Verify bounded first-pass contraction preserves caps, physical gates and safe fallback behavior.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation import solve as relocation
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings


@pytest.fixture(scope="module")
def original() -> FoldRoute:
    """
    Construct the fixed five-conductor excursion from its gym inputs, without saved artifacts.
    """
    scene = Scene(Config(2641972872, 5, 0.75, 300, 300), Goal(10, 0, 0), Goal(7, 8, 1))
    result = solver_v2.solve(scene.targets, Settings(0, False, False), lambda: None, lambda e: None)
    assert result.route is not None and result.detail["contact"] == "separated"
    return result.route


def test_checkbox_contracts_first_pass_before_disabled_smoothing(original: FoldRoute) -> None:
    """
    Move existing bends rather than changing profiles/radii or hiding the excursion with aesthetics.
    """
    rows: list[dict[str, Any]] = []
    result = solver_v2.solve(original.targets, Settings(0), lambda: None, rows.append)
    assert result.route is result.first_pass and result.route is not None
    assert result.detail["contraction"]["status"] == "shortened"
    assert result.detail["stages"] == {"smoothing": "disabled"}
    assert result.detail["construction"]["raw_length_mm"] == pytest.approx(
        original.material_length_mm
    )
    assert result.route.material_length_mm < original.material_length_mm * 0.3
    assert result.detail["contact"] == "separated"
    assert result.detail["contraction"]["contacts"] <= 2
    assert result.detail["first_pass_seconds"] >= result.detail["contraction"]["elapsed_seconds"]
    assert result.route.targets == original.targets
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
    before = [p.geometry for p in original.pieces if isinstance(p.geometry, CylindricalFold)]
    after = [p.geometry for p in result.route.pieces if isinstance(p.geometry, CylindricalFold)]
    assert len(before) == len(after) == 4
    assert [f.radius_mm for f in after] == pytest.approx([f.radius_mm for f in before], abs=1e-14)
    assert [f.width_mm for f in after] == [f.width_mm for f in before]
    assert any(row.get("stage") == "first_pass_contraction" and row.get("route") for row in rows)


@pytest.mark.parametrize("status", ("unresolved", "penetration"))
def test_failed_shorter_certificates_retain_original_safe_route(
    original: FoldRoute, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Never convert a missing clearance certificate or collision into accepted contraction.
    """
    inspect = Mock(return_value=ContactResult(status, 1024))
    monkeypatch.setitem(vars(relocation), "inspect_contact", inspect)
    result = relocation.contract(original, lambda: None, lambda e: None)
    assert result.route is original and result.contact is None
    assert result.detail["status"] == "baseline_retained"
    assert 1 <= inspect.call_count <= 2


def test_local_cpu_exhaustion_retains_baseline(
    original: FoldRoute, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Stop optional improvement at its own CPU cap without losing accepted geometry.
    """
    clock = iter((0.0, 0.4, 0.4))
    monkeypatch.setitem(vars(relocation), "process_time", lambda: next(clock))
    inspect = Mock(side_effect=AssertionError("Expired contraction must not start a certificate"))
    monkeypatch.setitem(vars(relocation), "inspect_contact", inspect)
    result = relocation.contract(original, lambda: None, lambda e: None)
    assert result.route is original and result.contact is None
    assert result.detail["stop_reason"] == "phase_budget"
    inspect.assert_not_called()


def test_local_wall_allowance_preserves_accepted_route(
    original: FoldRoute, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Exhaust remaining first-pass time without converting a valid baseline into a failure.
    """
    clock = iter((0.0, 0.6, 0.6))
    monkeypatch.setitem(vars(relocation), "perf_counter", lambda: next(clock))
    result = relocation.contract(original, lambda: None, lambda e: None, maximum_seconds=0.5)
    assert result.route is original and result.contact is None
    assert result.detail["stop_reason"] == "phase_budget"


def test_outer_hard_resource_error_is_not_masked(original: FoldRoute) -> None:
    """
    Propagate caller cancellation/time/source failures rather than reporting a successful fallback.
    """

    def stopped() -> None:
        """
        Model the existing worker's hard cancellation or resource boundary.
        """
        raise TimeoutError("worker cancelled")

    with pytest.raises(TimeoutError, match="worker cancelled"):
        relocation.contract(original, stopped, lambda e: None)
