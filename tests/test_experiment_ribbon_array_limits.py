"""
Check certificate-only fixture authoring and bounded diagnostic scheduling.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_ribbon_cap_transition import array_limits
from experiments.experiment_ribbon_cap_transition.array_fixtures import array_fixtures
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon


@pytest.mark.parametrize("index", (0, 1, 2))
def test_uniform_authoring_preserves_material_orientation_and_order(index: int) -> None:
    """
    Tightening moves every ordered position by one scale without shrinking material.
    """
    parent = array_fixtures()[index].case
    case = array_limits.scaled_case(parent, 0.7)
    assert case.lines == parent.lines and case.diameter_mm == parent.diameter_mm
    assert case.end_boundary == parent.end_boundary
    assert case.start_width == parent.start_width and case.end_width == parent.end_width
    center = parent.end_boundary.center
    for old, new in zip(parent.route.points, case.route.points):
        assert magnitude(difference(new, center)) == pytest.approx(
            0.7 * magnitude(difference(old, center))
        )
    for old, new in zip(parent.route.curves, case.route.curves):
        for parameter in (0.0, 0.5, 1.0):
            assert magnitude(difference(new.point(parameter), center)) == pytest.approx(
                0.7 * magnitude(difference(old.point(parameter), center))
            )


def test_certificate_search_is_bounded_and_retains_both_bracket_sides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Mock certification, ensuring no ribbon solve or native outcome controls authoring.
    """
    parent = array_fixtures()[2].case
    original = magnitude(difference(parent.route.curves[0].start, parent.end_boundary.center))
    calls: list[float] = []

    def certify(route: object, _reach: float) -> SimpleNamespace:
        """
        Reject only below the synthetic certificate scale boundary.
        """
        scale = magnitude(difference(route.curves[0].start, parent.end_boundary.center)) / original
        calls.append(scale)
        if scale < 0.65:
            raise UnsafeRibbon("synthetic rejection")
        return SimpleNamespace(maximum_ratio=0.52 / scale)

    monkeypatch.setitem(array_limits.__dict__, "certify_curvature", certify)
    selection = array_limits.select_scale(parent)
    assert len(calls) == len(selection.checks) == 24
    assert selection.rejected_scale < 0.65 <= selection.scale
    assert selection.scale - selection.rejected_scale == pytest.approx(2**-23)
    assert selection.maximum_ratio <= 0.8
    assert any(not check.passed for check in selection.checks)


@pytest.mark.parametrize("failure", ("none", "findings", "incomplete", "error"))
def test_limit_runner_proceeds_on_findings_but_never_retries_incomplete_builds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    """
    Exercise three fixed native schedules using synthetic reports and no Fusion calls.
    """
    calls: list[dict[str, object]] = []
    fake = ModuleType("experiments.experiment_ribbon_cap_transition.native")
    fake.NativeProcedure = SimpleNamespace(MASTER_TUBE_FULL_TURN="full-turn")
    fake.NativeGeometryPolicy = SimpleNamespace(OBSERVE_REJECTIONS="observe")

    def build(_case: object, _name: str, previous: object, **kwargs: object) -> Path:
        """
        Record each attempt and synthesize incomplete/diagnostic host dispositions.
        """
        assert previous is None
        calls.append(kwargs)
        if failure == "error":
            raise RuntimeError("synthetic host error")
        path = tmp_path / str(len(calls))
        path.mkdir()
        result = {
            "built": int(failure != "incomplete"),
            "preflight": {"failures": ["warning"] if failure == "findings" else []},
            "native_result": {
                "status": "audit_failed" if failure == "findings" else "built_and_audited"
            },
        }
        (path / "report.json").write_text(json.dumps(result), encoding="utf-8")
        return path

    fake._run_case = build
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments/experiment_ribbon_cap_transition/array_limit_native.py"
    )
    spec = importlib.util.spec_from_file_location(
        "experiments.experiment_ribbon_cap_transition._test_limit_native", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    state = module.ArrayBatch(
        tmp_path,
        array_fixtures(),
        {"code": "same"},
        {"production": "same"},
        [{"case_id": item.case.name, "status": "not_attempted"} for item in array_fixtures()],
        module.perf_counter(),
    )
    monkeypatch.setitem(module.__dict__, "_freeze", lambda: state)
    monkeypatch.setitem(module.__dict__, "_checkpoint", lambda _state: None)
    monkeypatch.setitem(module.__dict__, "_fingerprints", lambda: {"code": "same"})
    monkeypatch.setitem(module.__dict__, "verify_sources", lambda: {"production": "same"})
    if failure == "error":
        with pytest.raises(RuntimeError, match="synthetic"):
            module.run_next(None)
    else:
        module.run_next(None)
    if failure in ("error", "incomplete"):
        with pytest.raises(RuntimeError):
            module.run_next(None)
        assert len(calls) == 1
        assert all(row["status"] == "not_attempted" for row in state.rows[1:])
    else:
        module.run_next(None)
        module.run_next(None)
        with pytest.raises(RuntimeError, match="exhausted"):
            module.run_next(None)
        assert len(calls) == 3 and state.stop_reason is None
    assert all(
        call["geometry_policy"] == "observe" and call["budget"].maximum_seconds <= 120
        for call in calls
    )
