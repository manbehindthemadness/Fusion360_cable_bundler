"""
Verify fixed-width examples, explicit search excerpts and current-path bend evidence.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

import pytest

from devtools.ribbon_analysis.contracts import RibbonPath, Targets
from devtools.ribbon_analysis.inspection.archive import write_document
from devtools.ribbon_analysis.inspection.bends import inspect, radius
from devtools.ribbon_analysis.inspection.capture import read_history
from devtools.ribbon_analysis.inspection.geometry import freeze_path
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_cap_transition.shooting_telemetry import Trial
from experiments.experiment_ribbon_diagnostic_viewer import adapters, examples, interactive_worker
from experiments.experiment_ribbon_diagnostic_viewer.procedures import demonstration, selections
from experiments.experiment_ribbon_route_discovery import broad_chart


def test_ribbon_reference_attains_material_guide_limit_without_map_folding() -> None:
    """
    Check the authored analytic lane bound independently of solver or cubic acceptance.
    """
    path, targets = examples.ribbon(lambda: None)
    assert Targets.capture(targets).lines == 3
    half = path.field.half_width_mm
    peak, minimum_progress = 0.0, 1.0
    for index in range(4097):
        k, _, eta_s = path.field.sample(index / 4096)
        for offset in (-half, 0, half):
            progress = 1 + offset * eta_s
            minimum_progress = min(minimum_progress, progress)
            peak = max(peak, abs(k) / progress)
    assert minimum_progress > 0.8
    assert peak * 4.5 == pytest.approx(1.0, abs=1e-6)
    assert path.field.sample(0)[1] == 0
    assert abs(path.field.sample(1)[1]) < 1e-14


def test_bend_evidence_follows_selected_section_and_exposes_both_actual_edges() -> None:
    """
    Keep local guide radii and curvature plots tied to the displayed frozen geometry.
    """
    path, _ = examples.ribbon(lambda: None)
    snapshot = freeze_path("ribbon", path, intervals=512, sections=33)
    data = inspect(snapshot, 8)
    assert data["has_edges"] and len(data["samples"]) == 65
    assert data["selected"]["u"] == 0.25
    assert data["selected"]["radii_mm"]["centre"] == pytest.approx(
        path.field.length_mm / (2 * math.pi), rel=1e-4
    )
    assert data["selected"]["centre_edge_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert inspect(snapshot, 4)["selected"] != data["selected"]
    with pytest.raises(ValueError):
        radius(snapshot.guides[0], float("nan"))
    json.dumps(data, allow_nan=False)


def test_examples_keep_separate_inputs_and_all_nine_demo_selections_are_bounded(
    tmp_path: Path,
) -> None:
    """
    Preserve original single geometry and a separately identified ribbon configuration.
    """
    single = Session(examples.create(tmp_path / "single", "single", lambda: None))
    ribbon = Session(examples.create(tmp_path / "ribbon", "ribbon", lambda: None))
    assert (single.targets.lines, ribbon.targets.lines) == (1, 3)
    assert single.targets != ribbon.targets
    assert ribbon.snapshot is not None
    assert all(section.kind == "material_ruling" for section in ribbon.snapshot.sections)
    configured = demonstration()
    assert len(configured) == 9
    assert all(
        0 < method["settings"]["excerpt"] < method["settings"]["paths"] for method in configured
    )
    assert sum(method["settings"]["seconds"] for method in configured) == 72
    with pytest.raises(ValueError, match="before the hard"):
        selections([{"id": "ordinary", "settings": {"excerpt": 16, "paths": 16}}])


def test_declared_excerpts_continue_other_methods_without_claiming_completed_solves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A planned search prefix ends normally; resource errors remain covered separately.
    """
    reference = examples.create(tmp_path / "reference", "single", lambda: None)
    (tmp_path / "input.json").write_bytes(reference.read_bytes())
    write_document(
        tmp_path / "plan.json",
        {
            "run_id": "demo",
            "procedures": selections(
                [
                    {"id": identifier, "settings": {"excerpt": 2, "paths": 16}}
                    for identifier in ("ordinary", "tightening")
                ]
            ),
            "sources": {"test": "fixed"},
            "minimum_radius_mm": 4.5,
        },
    )
    monkeypatch.setattr(interactive_worker.procedures, "source_pins", lambda: {"test": "fixed"})
    monkeypatch.setattr(interactive_worker.budget, "resident_kib", lambda: 10000)
    calls: list[str] = []

    def execute(
        identifier: str,
        case: EndpointCase,
        settings: dict[str, Any],
        checkpoint: Callable[[], None],
    ) -> tuple[RibbonPath, dict[str, Any]]:
        """
        Produce real transports; the excerpt must end before a fictional final return.
        """
        assert settings["excerpt"] == 2
        calls.append(identifier)
        for _ in range(5):
            broad_chart.integrate(case, (0.0,) * 9 + (1.2,), 64, checkpoint)
        raise AssertionError("An excerpt must not finish the procedure.")

    monkeypatch.setattr(interactive_worker.adapters, "execute", execute)
    result = json.loads(interactive_worker.run(tmp_path).read_text())
    assert calls == ["ordinary", "tightening"]
    assert result["stopped"] is None
    assert all(method["status"] == "recorded" for method in result["solvers"])
    assert all(not method["metrics"]["procedure_completed"] for method in result["solvers"])
    assert all(len(read_history(tmp_path / f"{name}.jsonl")) == 2 for name in calls)
    assert all(method["has_result"] for method in Session(tmp_path / "manifest.json").methods)


def test_completed_compatible_trials_preserve_decisions_in_finite_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve actual dataclass trial telemetry when a procedure finishes before its excerpt.
    """
    path, case = examples.ribbon(lambda: None)
    trial = Trial(64, 0, 0.5, (1.0,), (2.0,), (1.5,), {"position": 2.0}, {"position": 3.0}, False)
    monkeypatch.setattr(
        adapters.compatible_shooting, "solve", lambda *args, **kwargs: (path, {"trials": (trial,)})
    )
    settings = selections([{"id": "compatible", "settings": {}}])[0]["settings"]
    result, metrics = adapters.execute("compatible", case, settings, lambda: None)
    assert result is path
    saved = json.loads(json.dumps(metrics, allow_nan=False))["trials"][0]
    assert not saved["accepted"] and saved["proposed"] == [1.5]
