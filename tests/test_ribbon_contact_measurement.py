"""
Verify temporary pair-limit logging never becomes a false contact certificate.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.performance import for_layout
from experiments.experiment_ribbon_feature_insertion import solve as construction
from experiments.experiment_ribbon_feature_insertion.contact_measurement import ContactPolicy
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_locked_solver import controller, solver_v2, worker
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.versions import V2


@pytest.mark.parametrize(
    "result, permitted",
    (
        (ContactResult("separated", 10), True),
        (ContactResult("unresolved", 1024, reason="pair limit", limit="pairs"), True),
        (ContactResult("penetration", 10), False),
        (ContactResult("unresolved", 10, limit="depth"), False),
        (ContactResult("unresolved", 0, reason="irregular material map"), False),
    ),
)
def test_only_explicit_pair_limit_is_a_temporary_geometry_permission(
    result: ContactResult, permitted: bool
) -> None:
    """
    Preserve strict defaults and distinguish budget measurement from real rejection.
    """
    assert ContactPolicy.LOG_PAIR_LIMIT.permits_geometry(result) is permitted
    assert ContactPolicy.STRICT.permits_geometry(result) is (result.status == "separated")


def _scene() -> Scene:
    """
    Retain the user's examined compact-branch contact regression without artifact dependencies.
    """
    return Scene(Config(4033669276, 3, 0.75, 300, 300), Goal(10, 6, 0), Goal(2, 6, 1))


def test_closed_branch_clears_empty_profile_corners_with_original_contact_budget() -> None:
    """
    Accept the fixed failed gym after bounding actual profile material, without rerouting.
    """
    scene = Scene(Config(2641972872, 3, 0.75, 300, 300), Goal(10, 0, 0), Goal(7, 8, 1))
    rows: list[dict[str, Any]] = []
    result = solver_v2.solve(scene.targets, Settings(0), lambda: None, rows.append)
    assert result.route is not None
    assert result.detail["status"] == "numerically_accepted"
    assert result.detail["contact"] == "separated"
    assert result.detail["contact_measurement"]["pairs_checked"] <= 1024
    assert result.detail["cap_error_mm"] < 1e-7
    assert result.route.material_length_mm == pytest.approx(23.433206320916888)


def test_compact_route_is_retained_as_unmeasured_without_relaxing_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve diagnostic permission for a deliberately exhausted contact measurement.
    """
    rows: list[dict[str, Any]] = []
    monkeypatch.setitem(
        vars(construction),
        "inspect_contact",
        Mock(
            return_value=ContactResult(
                "unresolved", 1024, unresolved_pieces=(1, 2), reason="pair limit", limit="pairs"
            )
        ),
    )
    result = solver_v2.solve(
        _scene().targets,
        Settings(0),
        lambda: None,
        rows.append,
        contact_policy=ContactPolicy.LOG_PAIR_LIMIT,
    )
    route = result.route
    assert route is not None
    assert route.material_length_mm == pytest.approx(20.057442613744374, abs=1e-7)
    assert result.detail["status"] == "geometry_ready_contact_unmeasured"
    assert result.detail["contact"] == "unresolved" and result.detail["contact_warning"] is True
    assert result.detail["contact_measurement"]["limit"] == "pairs"
    assert result.detail["contact_measurement"]["pairs_checked"] == 1024
    assert result.detail["contact_measurement"]["unresolved_pieces"] == (1, 2)
    assert any(row["stage"] == "feature_contact" and row["status"] == "unresolved" for row in rows)


def test_worker_and_counters_keep_contact_unmeasured_after_geometry_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve the warning through serialized plans, numerical results and UI observations.
    """
    scene = _scene()
    monkeypatch.setitem(
        vars(construction),
        "inspect_contact",
        Mock(
            return_value=ContactResult(
                "unresolved", 1024, unresolved_pieces=(1, 2), reason="pair limit", limit="pairs"
            )
        ),
    )
    pins = {"source": "digest"}
    (tmp_path / "plan.json").write_text(
        json.dumps(
            {
                "version": V2,
                "result_id": "warning-case",
                "targets": asdict(scene.targets),
                "gym": scene.payload(),
                "settings": asdict(Settings(0)),
                "sources": pins,
                "native_point_tolerance_mm": 1e-5,
                "contact_measurement_policy": ContactPolicy.LOG_PAIR_LIMIT.value,
            }
        )
    )
    monkeypatch.setitem(vars(worker), "verify", lambda: pins)
    manifest = json.loads(worker.run(tmp_path).read_text())
    recorded = manifest["solvers"][0]
    assert recorded["status"] == "recorded" and recorded["contact_warning"] is True
    contact = next(rule for rule in recorded["rules"] if rule["name"] == "Contact measurement")
    assert contact["status"] == "unmeasured" and contact["value"] == 1024
    assert (tmp_path / "route.json").exists()
    (tmp_path / "native-result.json").write_text(
        json.dumps({"status": "built_and_named_fidelity_checks_pass", "generation_seconds": 1.0})
    )
    assert (
        "contact measurement incomplete"
        in for_layout(scene.targets, scene.payload(), tmp_path)["status"]
    )


def test_controller_default_remains_strict_and_override_is_v2_only(tmp_path: Path) -> None:
    """
    Keep a temporary session's policy visible while v1 retains its original contact gate.
    """
    from experiments.experiment_ribbon_locked_solver.lock import ROOT

    normal = controller.Controller(ROOT / ".venv/bin/python", tmp_path / "normal", "owned", Mock())
    temporary = controller.Controller(
        ROOT / ".venv/bin/python",
        tmp_path / "temporary",
        "owned",
        Mock(),
        contact_policy=ContactPolicy.LOG_PAIR_LIMIT,
    )
    assert (
        normal.state()["active_solver"]["contact_measurement_policy"] == ContactPolicy.STRICT.value
    )
    choices = temporary.state()["available_solvers"]
    assert choices[0]["contact_measurement_policy"] == ContactPolicy.LOG_PAIR_LIMIT.value
    assert choices[1]["contact_measurement_policy"] == ContactPolicy.STRICT.value


def test_compact_route_now_passes_strict_contact_within_original_budget() -> None:
    """
    Resolve the original gym regression without the temporary policy or a larger budget.
    """
    result = solver_v2.solve(_scene().targets, Settings(0), lambda: None, lambda event: None)
    assert result.route is not None
    assert result.route.material_length_mm == pytest.approx(20.057442613744374, abs=1e-7)
    assert result.detail["status"] == "numerically_accepted"
    assert result.detail["contact"] == "separated"
    assert result.detail["contact_warning"] is False
    assert result.detail["contact_measurement"]["pairs_checked"] == 198
