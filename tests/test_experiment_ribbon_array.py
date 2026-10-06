"""
Protect fixed array boundaries and bounded scheduling without real ribbon solves.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from experiments.experiment_ribbon_cap_transition.array_fixtures import array_fixtures
from experiments.experiment_ribbon_cap_transition.full_turn import FullTurnDiagnostic
from experiments.experiment_ribbon_cap_transition.master_frames import master_scaffold, sampled_roll
from experiments.experiment_ribbon_diagnosis.spatial import spatial_cases


def test_array_fixtures_preserve_material_and_author_full_turn_boundary_before_solving() -> None:
    """
    Check deterministic authoring and scaffold winding, not native/material compliance.
    """
    fixtures = array_fixtures()
    assert fixtures == array_fixtures()
    assert len({fixture.case.name for fixture in fixtures}) == 3
    assert fixtures[1].case.route.curves == spatial_cases(4.0)[-2].route.curves
    for fixture in fixtures:
        case = fixture.case
        assert case.lines == 19 and case.diameter_mm == 1.5
        assert case.end_boundary.diameter_mm == 114
        scaffold = master_scaffold(
            case.route, case.start_width, case.end_width, 28.5, twist=FullTurnDiagnostic()
        )
        assert sampled_roll(scaffold.frames)["net_roll_degrees"] == pytest.approx(360)
        assert scaffold.frames[-1].width == case.end_width


@pytest.mark.parametrize("failure", ("none", "incomplete", "hard", "audit", "error"))
@pytest.mark.parametrize("diagnostic", (False, True))
def test_array_runner_freezes_all_inputs_and_latches_failure_without_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str, diagnostic: bool
) -> None:
    """
    Mock Fusion construction while exercising retention, coverage and stopping rules.
    """
    calls: list[dict[str, object]] = []
    fake = ModuleType("experiments.experiment_ribbon_cap_transition.native")
    fake.NativeProcedure = SimpleNamespace(MASTER_TUBE_FULL_TURN=SimpleNamespace(value="full-turn"))
    fake.NativeGeometryPolicy = SimpleNamespace(
        STOP_ON_KNOWN_FINDINGS="stop-known-findings", OBSERVE_REJECTIONS="observe"
    )

    def build(_case: object, name: str, previous: object, **kwargs: object) -> Path:
        """
        Write synthetic evidence without any geometry or Fusion calls.
        """
        assert previous is None
        calls.append({"name": name, **kwargs})
        if failure == "error":
            raise ValueError("simulated host error")
        directory = tmp_path / str(len(calls))
        directory.mkdir()
        result = {
            "built": 0 if failure == "incomplete" else 1,
            "preflight": {"failures": ["hard finding"] if failure == "hard" else []},
            "native_result": {"status": "failed" if failure == "audit" else "built_and_audited"},
        }
        (directory / "report.json").write_text(json.dumps(result), encoding="utf-8")
        return directory

    fake._run_case = build
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments/experiment_ribbon_cap_transition/array_native.py"
    )
    spec = importlib.util.spec_from_file_location(
        "experiments.experiment_ribbon_cap_transition._test_array_native", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setitem(module.__dict__, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(module.__dict__, "_fingerprints", lambda: {"code": "frozen"})
    monkeypatch.setitem(module.__dict__, "verify_sources", lambda: {"production": "frozen"})
    if diagnostic:
        diagnostic_path = path.with_name("array_diagnostic.py")
        monkeypatch.setitem(
            sys.modules, "experiments.experiment_ribbon_cap_transition.array_native", module
        )
        diagnostic_spec = importlib.util.spec_from_file_location(
            "experiments.experiment_ribbon_cap_transition._test_diagnostic", diagnostic_path
        )
        assert diagnostic_spec is not None and diagnostic_spec.loader is not None
        diagnostic_module = importlib.util.module_from_spec(diagnostic_spec)
        monkeypatch.setitem(sys.modules, diagnostic_spec.name, diagnostic_module)
        diagnostic_spec.loader.exec_module(diagnostic_module)
        original_module = module

        def renew() -> object:
            """
            Isolate diagnostic scheduling from historical artifact lookup.
            """
            state = original_module._freeze()
            state.fixtures = state.fixtures[1:]
            state.rows = state.rows[1:]
            return state

        monkeypatch.setitem(diagnostic_module.__dict__, "_renew", renew)
        monkeypatch.setitem(diagnostic_module.__dict__, "_fingerprints", lambda: {"code": "frozen"})
        monkeypatch.setitem(
            diagnostic_module.__dict__, "verify_sources", lambda: {"production": "frozen"}
        )
        module = diagnostic_module
    if failure == "error":
        with pytest.raises(ValueError, match="simulated"):
            module.run_next(None)
    else:
        module.run_next(None)
    state = module._state
    plan = json.loads((state.directory / "plan.json").read_text(encoding="utf-8"))
    assert len(plan["inputs"]) == 3
    assert len(calls) == 1 and calls[0]["sphere_diameter_widths"] == 4
    assert calls[0]["budget"].maximum_seconds <= 120
    assert calls[0]["geometry_policy"] == ("observe" if diagnostic else "stop-known-findings")
    if failure in ("incomplete", "error") or (not diagnostic and failure != "none"):
        with pytest.raises(RuntimeError):
            module.run_next(None)
        assert len(calls) == 1
        assert all(row["status"] == "not_attempted" for row in state.rows[1:])
    else:
        module.run_next(None)
        if not diagnostic:
            module.run_next(None)
        with pytest.raises(RuntimeError, match="exhausted"):
            module.run_next(None)
        assert len(calls) == (2 if diagnostic else 3)
        assert state.stop_reason is None
        assert all(row["status"] == "completed" for row in state.rows)
