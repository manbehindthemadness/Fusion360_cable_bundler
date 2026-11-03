"""
Verify stage logs distinguish request rejection, worker failure, unresolved routing and native results.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym import generate
from experiments.experiment_ribbon_locked_solver import controller, progress, worker
from experiments.experiment_ribbon_locked_solver.lock import ROOT
from experiments.experiment_ribbon_locked_solver.settings import VERSION


def _finished_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[controller.Controller, Mock]:
    """
    Supply a completed owned subprocess without launching Fusion or a numerical search.
    """
    native = Mock()
    runner = controller.Controller(ROOT / ".venv/bin/python", tmp_path, "owned", native)
    runner._job = tmp_path
    process = Mock(returncode=0)
    process.poll.return_value = 0
    runner._process = process
    runner._seconds = float("inf")
    monkeypatch.setattr(
        "experiments.experiment_ribbon_diagnostic_viewer.controller.budget.resident_kib", lambda: 0
    )
    return runner, native


def _manifest(directory: Path) -> None:
    """
    Record a minimal completed disposition for controller collection tests.
    """
    (directory / "manifest.json").write_text(
        json.dumps({"solvers": [{"id": "test", "status": "recorded", "rules": []}]})
    )


def test_progress_tail_is_bounded_and_tolerates_incomplete_records(tmp_path: Path) -> None:
    """
    Keep polling reliable under partial writes while bounding retained UI text.
    """
    for index in range(120):
        progress.append(tmp_path, "numerical", str(index))
    with (tmp_path / "build-progress.jsonl").open("a") as stream:
        stream.write('{"partial":')
    entries = progress.read(tmp_path)
    assert len(entries) == 100 and entries[0]["message"] == "20" and entries[-1]["message"] == "119"
    assert progress.read(None) == []
    assert len(progress.tail(tmp_path / "build-progress.jsonl", 100).encode()) <= 100


def test_worker_exit_without_manifest_exposes_its_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Show a crashed worker's retained output rather than claiming numerical or native success.
    """
    runner, native = _finished_worker(tmp_path, monkeypatch)
    (tmp_path / "worker.log").write_text("Traceback\nValueError: malformed input\n")
    assert runner.poll() is None
    state = runner.state()
    assert state["status"] == "stopped"
    assert "ValueError: malformed input" in state["build_log"][-1]["message"]
    native.assert_not_called()


def test_no_route_is_unresolved_and_skips_native_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Distinguish exhausted routing from a control failure or a successfully built body.
    """
    runner, native = _finished_worker(tmp_path, monkeypatch)
    _manifest(tmp_path)
    assert runner.poll() == tmp_path / "manifest.json"
    assert runner.state()["status"] == "unresolved"
    assert "native construction was not attempted" in runner.state()["build_log"][-1]["message"]
    native.assert_not_called()


@pytest.mark.parametrize(
    "native_status",
    (
        "built_and_named_fidelity_checks_pass",
        "built_with_precision_warning",
        "stopped",
        "exception",
    ),
)
def test_native_collection_records_completion_or_failure_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, native_status: str
) -> None:
    """
    Retain named native disposition and stop safely on failures outside the native adapter.
    """
    runner, native = _finished_worker(tmp_path, monkeypatch)
    _manifest(tmp_path)
    (tmp_path / "route.json").write_text("{}")
    if native_status == "exception":
        native.side_effect = RuntimeError("native inputs unavailable")
        with pytest.raises(RuntimeError, match="native inputs unavailable"):
            runner.poll()
    else:
        native.return_value = {"status": native_status, "error": "Native gate failed"}
        assert runner.poll() == tmp_path / "native-manifest.json"
    state = runner.state()
    expected = {
        "built_and_named_fidelity_checks_pass": "completed",
        "built_with_precision_warning": "completed_with_warning",
    }
    assert state["status"] == expected.get(native_status, "stopped")
    if native_status == "built_with_precision_warning":
        method = json.loads((tmp_path / "native-manifest.json").read_text())["solvers"][0]
        assert method["rules"][-1]["status"] == "warning"
        assert "strict accuracy findings retained" in method["detail"]
    assert any("starting native" in entry["message"] for entry in state["build_log"])
    assert runner.poll() is None
    native.assert_called_once_with(tmp_path)


def test_unresolved_worker_records_no_geometry_without_a_native_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Exercise actual worker serialization with an explicitly unresolved numerical boundary.
    """
    scene = generate()
    pins = {"source": "digest"}
    (tmp_path / "plan.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "result_id": "run:test",
                "targets": asdict(scene.targets),
                "gym": scene.payload(),
                "settings": {
                    "smoothing_percent": 0,
                    "material_uv": False,
                    "first_pass_optimization": True,
                },
                "sources": pins,
            }
        )
    )
    monkeypatch.setitem(vars(worker), "verify", lambda: pins)
    monkeypatch.setitem(
        vars(worker),
        "solve",
        lambda *args: SimpleNamespace(route=None, detail={"status": "unresolved"}),
    )
    worker.run(tmp_path)
    assert not (tmp_path / "route.json").exists()
    assert any("No route accepted" in entry["message"] for entry in progress.read(tmp_path))
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["solvers"][0]["status"] == "unresolved"
    assert all(rule["status"] == "unmeasured" for rule in manifest["solvers"][0]["rules"])


@pytest.mark.parametrize(
    "native_status", ("built_and_named_fidelity_checks_pass", "built_with_precision_warning")
)
def test_native_fidelity_success_does_not_erase_temporary_contact_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, native_status: str
) -> None:
    """
    Keep numerical contact explicitly unmeasured after a successful native build.
    """
    runner, native = _finished_worker(tmp_path, monkeypatch)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "solvers": [
                    {
                        "id": "warning",
                        "status": "recorded",
                        "contact_warning": True,
                        "rules": [{"name": "Contact measurement", "status": "unmeasured"}],
                    }
                ]
            }
        )
    )
    (tmp_path / "route.json").write_text("{}")
    native.return_value = {"status": native_status}
    manifest = runner.poll()
    assert manifest is not None
    method = json.loads(manifest.read_text())["solvers"][0]
    assert runner.state()["status"] == "completed_with_warning"
    assert "contact measurement" in method["detail"].lower()
    assert "unmeasured" in method["detail"]
    assert (
        next(rule for rule in method["rules"] if rule["name"] == "Contact measurement")["status"]
        == "unmeasured"
    )
