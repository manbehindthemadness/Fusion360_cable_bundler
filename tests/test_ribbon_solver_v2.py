"""
Verify v2 gym dispatch, bounded tight construction and optional shared post-processing.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym import Config, generate
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion.contact_measurement import ContactPolicy
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_locked_solver import controller, solver_v2, worker
from experiments.experiment_ribbon_locked_solver.lock import ROOT
from experiments.experiment_ribbon_locked_solver.settings import VERSION, Settings
from experiments.experiment_ribbon_locked_solver.solver import Result
from experiments.experiment_ribbon_locked_solver.versions import V2, method
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("version", (VERSION, V2))
def test_controller_advertises_v2_default_and_freezes_explicit_method(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    """
    Keep v1 selectable without silently substituting v2 or losing actual native tolerance.
    """
    runner = controller.Controller(
        ROOT / ".venv/bin/python", tmp_path, "owned", Mock(), native_point_tolerance_mm=2e-5
    )
    assert runner.state()["active_solver"]["id"] == V2
    assert runner.state()["active_solver"]["settings"]["smoothing_percent"] == 0
    assert [entry["id"] for entry in runner.state()["available_solvers"]] == [V2, VERSION]
    monkeypatch.setattr(controller.lock, "verify", lambda: {"pin": "value"})
    launch = Mock(return_value=Mock())
    monkeypatch.setattr(controller.subprocess, "Popen", launch)
    scene = generate()
    runner.start(
        {"procedures": [{"id": version, "settings": asdict(method(version).defaults)}]},
        scene.targets,
        gym=scene.payload(),
    )
    plan = json.loads((Path(launch.call_args.args[0][-1]) / "plan.json").read_text())
    assert plan["version"] == version and plan["native_point_tolerance_mm"] == 2e-5
    assert runner.state()["active_solver"]["id"] == version
    assert runner._log is not None
    runner._log.close()


@pytest.mark.parametrize("version", (VERSION, V2))
def test_worker_dispatches_one_explicit_version_without_cross_version_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    """
    Keep unresolved results explicit and forward native tolerance only to v2.
    """
    scene = generate()
    pins = {"pin": "value"}
    settings = method(version).defaults
    (tmp_path / "plan.json").write_text(
        json.dumps(
            {
                "version": version,
                "result_id": "test",
                "targets": asdict(scene.targets),
                "gym": scene.payload(),
                "sources": pins,
                "settings": asdict(settings),
                "native_point_tolerance_mm": 2e-5,
            }
        )
    )
    legacy = Mock(return_value=Result(None, None, {"status": "unresolved"}, None))
    current = Mock(return_value=Result(None, None, {"status": "unresolved"}, None))
    monkeypatch.setitem(vars(worker), "verify", lambda: pins)
    monkeypatch.setitem(vars(worker), "solve", legacy)
    monkeypatch.setitem(vars(worker), "solve_v2", current)
    material_error(_route((Straight(2.125),)))
    assert material_error.cache_info().currsize > 0
    destination = worker.run(tmp_path)
    selected, other = (current, legacy) if version == V2 else (legacy, current)
    selected.assert_called_once()
    other.assert_not_called()
    if version == V2:
        assert selected.call_args.kwargs == {
            "native_point_tolerance_mm": 2e-5,
            "contact_policy": ContactPolicy.STRICT,
        }
    manifest = json.loads(destination.read_text())
    assert manifest["solvers"][0]["procedure"] == version
    assert not (tmp_path / "route.json").exists()
    numerical = json.loads((tmp_path / "numerical-result.json").read_text())
    assert numerical["material_metric_cache"] == {
        "hits": 0,
        "misses": 0,
        "maxsize": 64,
        "currsize": 0,
    }


def test_v2_reproduces_measured_gym_branch_and_toggle_without_hidden_postpass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve the actual examined gym regression and avoid repeating its accepted contact certificate.
    """
    scene = generate(Config(2026110208, 5, 0.5, 600, 400))

    def forbidden(*args: Any, **kwargs: Any) -> None:
        """
        Fail on redundant final contact work when no aesthetic geometry changed.
        """
        del args, kwargs
        raise AssertionError("Unchanged first pass already certified")

    monkeypatch.setitem(vars(solver_v2), "inspect_contact", forbidden)
    lengths: list[float] = []
    for optimization in (False, True):
        result = solver_v2.solve(
            scene.targets, Settings(0, False, optimization), lambda: None, lambda event: None
        )
        route = result.route
        if route is None:
            raise AssertionError("Measured gym control must retain an accepted route")
        accepted_route: FoldRoute = route
        assert accepted_route is result.first_pass
        assert accepted_route.targets == scene.targets
        assert result.detail["contact"] == "separated"
        assert result.detail["cap_error_mm"] < 1e-7
        assert result.detail["material_metric_error"] < 1e-10
        assert result.detail["version"] == V2
        assert result.detail["construction"]["contact_pairs"] <= 2048
        assert result.detail["construction"]["selection"] == (
            "monotonic" if optimization else "midpoint"
        )
        assert result.detail["stages"] == {"smoothing": "disabled"}
        assert result.material_uv is None
        assert result.detail["quality"]["final_length_mm"] == accepted_route.material_length_mm
        lengths.append(accepted_route.material_length_mm)
    assert lengths[1] < lengths[0]


def test_v2_uv_metadata_retains_material_coordinates_without_appearance_work() -> None:
    """
    Keep optional coordinates tied to the accepted v2 route rather than a v1 replacement.
    """
    scene = generate(Config(2026110202, 3, 1.0, 400, 300))
    result = solver_v2.solve(scene.targets, Settings(0, True), lambda: None, lambda event: None)
    assert result.route is not None and result.material_uv is not None
    assert result.material_uv["route"]["case"] == asdict(scene.targets)
    assert result.material_uv["schema"] == "ribbon-material-coordinates-v1"
    assert result.detail["material_uv_seconds"] >= 0


@pytest.mark.parametrize("tolerance", (None, True, 0, -1, float("nan")))
def test_v2_rejects_bad_native_tolerance_before_numerical_work(tolerance: Any) -> None:
    """
    Do not guess a chart/geometry tolerance from malformed host metadata.
    """
    with pytest.raises(ValueError, match="tolerance"):
        solver_v2.solve(
            generate().targets,
            Settings(0),
            lambda: None,
            lambda event: None,
            native_point_tolerance_mm=tolerance,
        )
