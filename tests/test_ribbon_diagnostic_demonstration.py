"""
Verify authored references and current-path evidence after discovery retirement.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.inspection.bends import inspect, radius
from devtools.ribbon_analysis.inspection.geometry import freeze_path
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_diagnostic_viewer import adapters, examples, runner
from experiments.experiment_ribbon_diagnostic_viewer.procedures import demonstration


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


def test_examples_keep_separate_inputs_without_scheduling_discovery(
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
    assert demonstration() == []


@pytest.mark.parametrize("identifier", ("compatible", "ordinary", "director", "broad", "discovery"))
def test_direct_adapter_cannot_bypass_removed_discovery(identifier: str) -> None:
    """
    Refuse direct adapter calls before checkpoint, seed or transport work.
    """
    _, case = examples.ribbon(lambda: None)

    def forbidden() -> None:
        """
        Expose any attempted numerical work after retirement.
        """
        raise AssertionError("No discovery work is allowed")

    with pytest.raises(ValueError, match="have been removed"):
        adapters.execute(identifier, case, {"path_rules": "historical"}, forbidden)


def test_reference_runner_authors_only_and_preserves_historical_inventory(tmp_path: Path) -> None:
    """
    The former batch entry point can author a reference but cannot run a search.
    """
    manifest = runner.run(tmp_path / "reference")
    data = json.loads(manifest.read_text())
    assert data["search_evaluations"] == 0
    assert data["independent_cases"]["numerically_evaluated"] == 0
    assert data["independent_cases"]["native_attempted"] == 0
    assert data["discovery_available"] is False
    assert all(item["status"] == "not_run" for item in data["solvers"][1:])
    assert not list(manifest.parent.glob("*.jsonl"))
    session = Session(manifest)
    assert session.snapshot is not None
    assert len(session.methods) == 13
