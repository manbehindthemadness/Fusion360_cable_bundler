"""
Exercise bounded native scheduling with a fake Fusion construction boundary.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.mark.parametrize("built", (0, 1, -1))
def test_tube_batch_retains_documents_and_never_retries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, built: int
) -> None:
    """
    Freeze three inputs, launch one case per call and latch construction failure.
    """
    calls: list[tuple[object, ...]] = []
    fake = ModuleType("experiments.experiment_ribbon_cap_transition.native")
    fake.NativeProcedure = SimpleNamespace(MASTER_TUBE=SimpleNamespace(value="test-tube"))

    def build(case: object, name: str, previous: object, **kwargs: object) -> Path:
        """
        Capture retention and budget arguments without importing Fusion.
        """
        calls.append((case, name, previous, kwargs))
        if built == -1:
            raise ValueError("simulated host error")
        directory = tmp_path / str(len(calls))
        directory.mkdir()
        (directory / "report.json").write_text(json.dumps({"built": built}), encoding="utf-8")
        return directory

    fake._run_case = build
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments/experiment_ribbon_cap_transition/tube_native.py"
    )
    spec = importlib.util.spec_from_file_location(
        "experiments.experiment_ribbon_cap_transition._test_tube_native", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(module.__dict__, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(module.__dict__, "_fingerprints", lambda: {"code": "frozen"})
    monkeypatch.setitem(module.__dict__, "verify_sources", lambda: {"production": "frozen"})
    if built == -1:
        with pytest.raises(ValueError, match="simulated host error"):
            module.run_next(None)
        with pytest.raises(RuntimeError, match="harness error"):
            module.run_next(None)
        assert len(calls) == 1 and module._state["cases"][0]["status"] == "error"
        return
    module.run_next(None)
    assert len(calls) == 1 and calls[0][2] is None
    assert calls[0][3]["budget"].maximum_seconds <= 120
    state = module._state
    assert len(state["plan"]["inputs"]) == 3
    assert [row["status"] for row in state["cases"]] == [
        "completed",
        "not_attempted",
        "not_attempted",
    ]
    if built == 0:
        with pytest.raises(RuntimeError, match="construction failed"):
            module.run_next(None)
        assert len(calls) == 1
    else:
        module.run_next(None)
        module.run_next(None)
        with pytest.raises(RuntimeError, match="exhausted"):
            module.run_next(None)
        assert len(calls) == 3
    assert all(call[2] is None for call in calls)
