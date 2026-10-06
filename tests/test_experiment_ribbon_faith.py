"""
Protect signed roll, frozen six-case scheduling, timing and archive-close sequencing.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_ribbon_cap_transition.array_limits import ScaleCheck, ScaleSelection
from experiments.experiment_ribbon_cap_transition.faith_fixtures import faith_fixtures
from experiments.experiment_ribbon_cap_transition.master_frames import master_scaffold, sampled_roll
from experiments.experiment_ribbon_cap_transition.native_budget import NativeBudget
from experiments.experiment_ribbon_cap_transition.prescribed_twist import PrescribedTwistDiagnostic


@pytest.mark.parametrize("index", tuple(range(6)))
def test_six_distinct_layouts_retain_material_and_signed_winding(index: int) -> None:
    """
    Check authored scaffold/cap contracts without solves or certificate searches.
    """
    fixtures = faith_fixtures()
    assert fixtures == faith_fixtures()
    assert len({item.case.route.curves for item in fixtures}) == 6
    assert (
        len(
            {(item.case.route.curves[0].start, item.case.route.curves[-1].end) for item in fixtures}
        )
        == 6
    )
    item = fixtures[index]
    case = item.case
    assert case.lines == 19 and case.diameter_mm == 1.5
    assert case.end_boundary.diameter_mm == 114
    scaffold = master_scaffold(
        case.route,
        case.start_width,
        case.end_width,
        28.5,
        twist=PrescribedTwistDiagnostic(item.twist_degrees),
    )
    assert sampled_roll(scaffold.frames)["net_roll_degrees"] == pytest.approx(item.twist_degrees)
    assert magnitude(difference(scaffold.frames[-1].width, case.end_width)) <= 1e-12


@pytest.mark.parametrize("degrees", (0, 90, -90, 180, -180, -360))
def test_signed_quintic_matches_end_orientation_without_collapsing_winding(degrees: float) -> None:
    """
    Match the modular guide roll while preserving the prescribed signed revolution.
    """
    roll = math.radians(degrees)
    principal = math.atan2(math.sin(roll), math.cos(roll))
    angles = PrescribedTwistDiagnostic(degrees).angles((0, 1, 5, 9, 10), principal)
    assert angles[0] == 0 and angles[-1] == roll
    assert angles[2] == pytest.approx(roll / 2)
    with pytest.raises(ValueError, match="orientation"):
        PrescribedTwistDiagnostic(degrees).angles((0, 5, 10), principal + 0.01)


@pytest.mark.parametrize("failure", ("none", "findings", "incomplete", "error"))
def test_faith_runner_freezes_six_inputs_records_times_and_never_retries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    """
    Mock native/display boundaries, proving findings proceed and failed builds stop.
    """
    calls: list[dict[str, object]] = []
    copies: list[str] = []
    fake = ModuleType("experiments.experiment_ribbon_cap_transition.native")
    fake.NativeProcedure = SimpleNamespace(MASTER_TUBE_SHARED_CAPS="shared")
    fake.NativeGeometryPolicy = SimpleNamespace(OBSERVE_REJECTIONS="observe")

    def build(_case: object, name: str, previous: object, **kwargs: object) -> Path:
        """
        Require upfront inputs and emit synthetic per-stage timing evidence.
        """
        assert previous is None and len(module._state.plan["inputs"]) == 6
        calls.append({"name": name, **kwargs})
        if failure == "error":
            raise RuntimeError("synthetic host error")
        directory = tmp_path / str(len(calls))
        directory.mkdir()
        report = {
            "built": int(failure != "incomplete"),
            "timings_seconds": {"search_shape": 0.01, "native_trunk": 2, "native_endings": 3},
            "timing_groups_seconds": {"native_construction": 5, "diagnostic_audits": 8},
            "overall_seconds": 15,
            "preflight": {"failures": ["recorded finding"] if failure == "findings" else []},
        }
        (directory / "report.json").write_text(json.dumps(report), encoding="utf-8")
        return directory

    fake._run_case = build
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    display = ModuleType("experiments.experiment_ribbon_cap_transition.faith_display")
    display.start_array = lambda _budget: None

    def append(
        name: str, _center: object, _index: int, _directory: Path, _budget: object
    ) -> dict[str, object]:
        """
        Record display import and owned scratch closure without Fusion operations.
        """
        copies.append(name)
        return {"source": name, "solids": 39, "scratch_closed": True}

    display.append_and_close = append
    monkeypatch.setitem(sys.modules, display.__name__, display)
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments/experiment_ribbon_cap_transition/faith_native.py"
    )
    spec = importlib.util.spec_from_file_location(
        "experiments.experiment_ribbon_cap_transition._test_faith", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setitem(module.__dict__, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(module.__dict__, "_fingerprints", lambda: {"code": "frozen"})
    monkeypatch.setitem(module.__dict__, "verify_sources", lambda: {"production": "frozen"})

    def budget(*, maximum_seconds: float) -> NativeBudget:
        """
        Use deterministic mocked host memory at the unit-test boundary.
        """
        return NativeBudget(maximum_seconds=maximum_seconds, memory=lambda: 1024)

    monkeypatch.setitem(module.__dict__, "NativeBudget", budget)
    monkeypatch.setitem(
        module.__dict__,
        "select_scale",
        lambda _case: ScaleSelection(
            0.8, 0.79, 0.799, (ScaleCheck(0.8, True, 0.799, None),), 0.001
        ),
    )
    if failure == "error":
        with pytest.raises(RuntimeError, match="synthetic"):
            module.run_next(None)
    else:
        module.run_next(None)
    state = module._state
    assert len(state.plan["inputs"]) == len(state.plan["selections"]) == 6
    assert state.prepared
    if failure in ("incomplete", "error"):
        with pytest.raises(RuntimeError):
            module.run_next(None)
        assert len(calls) == 1 and not copies
        assert all(row["status"] == "not_attempted" for row in state.rows[1:])
    else:
        for _index in range(5):
            module.run_next(None)
        with pytest.raises(RuntimeError, match="exhausted"):
            module.run_next(None)
        assert len(calls) == len(copies) == 6
        assert state.stop_reason is None
        assert state.rows[0]["individual_times_seconds"]["shape_solve"] == 0.01
        assert state.rows[0]["individual_times_seconds"]["native_build"] == 5
    assert all(
        call["geometry_policy"] == "observe" and call["budget"].maximum_seconds <= 120
        for call in calls
    )
