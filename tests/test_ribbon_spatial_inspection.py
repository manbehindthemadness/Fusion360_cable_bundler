"""
Verify actual material geometry and precommitted, nonrepeatable spatial probes on synthetic inputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_spatial_inspection.geometry import capture, physical, stations
from experiments.experiment_ribbon_spatial_inspection.ledger import Ledger, create, digest
from experiments.experiment_ribbon_spatial_inspection.probe import execute
from tests.test_ribbon_aesthetic import _route


@pytest.fixture
def route() -> FoldRoute:
    """
    Author a synthetic ordered two-fold strip with fixed caps, without replaying a gym specimen.
    """
    return _route(
        (
            Straight(5),
            fold(2, 1.2, 1.0, 0.0, 0),
            Straight(3),
            fold(2, 1.2, -1.0, 0.0, 0),
            Straight(5),
        )
    )


@pytest.fixture
def packet(route: FoldRoute) -> dict[str, Any]:
    """
    Measure one analytical route with no external geometry or native builders.
    """
    return capture(route, lambda: None)


@pytest.fixture
def ledger(tmp_path: Path, packet: dict[str, Any]) -> Ledger:
    """
    Freeze a fresh inspection packet and its exact content fingerprint.
    """
    create(tmp_path / "baseline.json", packet)
    create(
        tmp_path / "inspection-plan.json", {"baseline_fingerprint": digest(packet), "sources": {}}
    )
    return Ledger(tmp_path)


@pytest.fixture
def prediction(packet: dict[str, Any]) -> dict[str, Any]:
    """
    Predict an interior material landmark before its movement is evaluated.
    """
    section = next(
        i for i, s in enumerate(packet["sections"]) if s["piece"] == 1 and s["label"] == "middle"
    )
    return {
        "coordinate": 0,
        "delta": 0.01,
        "section": section,
        "expected_displacement_mm": [0.01, 0, 0],
        "tolerance_mm": 0.001,
        "explanation": "The requested leading runway motion is projected onto fixed-cap closure; the interior fold should advance while other slots compensate.",
    }


def test_sections_follow_exact_material_map_and_bracket_diagonal_edges() -> None:
    """
    Resolve width-dependent fold entry rather than assuming a fixed seventeen-section grid.
    """
    original = _route((fold(2, 1.2, 1.1, 0.3, 1),))
    rows = stations(original)
    assert len(rows) > 17
    labels = {label for _, _, label in rows}
    assert all(
        f"{edge} entry {bracket}" in labels
        for edge in ("A", "B", "center")
        for bracket in ("before", "at", "after")
    )
    captured = capture(original, lambda: None)
    for section in captured["sections"]:
        assert section["frame"]["origin"] == [
            getattr(original.pieces[0].surface(section["u"], 0)[0], axis) for axis in "xyz"
        ]
    assert physical(original.pieces[0], 0.5, 0, 0) == original.pieces[0].surface(0.5, 0)[0]


def test_probe_requires_prediction_and_cannot_run_twice(
    ledger: Ledger, prediction: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Observe a flushed, sealed prediction before computation and consume even a blocked attempt once.
    """
    calls = []

    def measured(*args: Any) -> dict[str, Any]:
        """
        Verify evidence persistence at the execution boundary.
        """
        assert (ledger.directory / "prediction-seal.json").exists()
        assert (ledger.directory / "probe-started.json").exists()
        calls.append(args)
        return {"status": "blocked", "reason": "Synthetic zero direction"}

    monkeypatch.setattr("experiments.experiment_ribbon_spatial_inspection.probe.execute", measured)
    with pytest.raises(FileNotFoundError):
        ledger.run_probe()
    ledger.commit(prediction)
    with pytest.raises(FileExistsError):
        ledger.commit(prediction)
    assert ledger.run_probe()["status"] == "blocked"
    with pytest.raises(FileExistsError):
        ledger.run_probe()
    assert len(calls) == 1


def test_tampered_prediction_and_baseline_are_refused(
    ledger: Ledger, prediction: dict[str, Any]
) -> None:
    """
    Refuse post-commit edits instead of scoring a prediction rewritten after observation.
    """
    ledger.commit(prediction)
    path = ledger.directory / "prediction.json"
    record = json.loads(path.read_text())
    record["prediction"]["expected_displacement_mm"] = [99, 0, 0]
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="modified"):
        ledger.run_probe()
    assert not (ledger.directory / "probe-started.json").exists()
    (ledger.directory / "baseline.json").write_text("{}")
    with pytest.raises(ValueError, match="baseline changed"):
        ledger.run_probe()


def test_budget_stop_is_persisted_without_retry(
    ledger: Ledger, prediction: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Retain an incomplete probe's disposition and prevent a second allowance.
    """

    def exhausted(*args: Any) -> dict[str, Any]:
        """
        Model a hard diagnostic resource stop at the numerical boundary.
        """
        del args
        raise TimeoutError("Synthetic budget stop")

    monkeypatch.setattr("experiments.experiment_ribbon_spatial_inspection.probe.execute", exhausted)
    ledger.commit(prediction)
    assert ledger.run_probe()["status"] == "stopped"
    with pytest.raises(FileExistsError):
        ledger.run_probe()


@pytest.mark.parametrize(
    "change",
    [
        {"coordinate": True},
        {"delta": 100},
        {"expected_displacement_mm": [float("nan"), 0, 0]},
        {"explanation": "guess"},
    ],
)
def test_invalid_predictions_cannot_consume_geometry_work(
    ledger: Ledger, prediction: dict[str, Any], change: dict[str, Any]
) -> None:
    """
    Reject malformed indices, nonfinite measurements and unbounded or unexplained motions.
    """
    with pytest.raises(ValueError):
        ledger.commit({**prediction, **change})
    assert not (ledger.directory / "prediction.json").exists()


def test_single_actual_probe_preserves_caps_original_geometry_and_records_proposal(
    route: FoldRoute, packet: dict[str, Any], prediction: dict[str, Any]
) -> None:
    """
    Exercise the real geometric step without granting routing or native acceptance.
    """
    original = snapshot(route)
    proposals = []
    result = execute(packet, prediction, lambda: None, proposals.append, lambda: None)
    assert result["status"] == "measured"
    assert len(proposals) == 1
    assert result["after"]["measurements"]["cap_position_error_mm"] < 1e-10
    assert result["after"]["measurements"]["cap_frame_vector_error"] < 1e-10
    assert result["after"]["targets"] == packet["targets"]
    assert snapshot(route) == original
    assert "prediction_matched" in result and "native" not in result


def test_open_caps_remain_inspectable_but_cannot_be_repaired_by_a_probe(
    tmp_path: Path, packet: dict[str, Any], prediction: dict[str, Any]
) -> None:
    """
    Keep an open baseline diagnostic instead of using the experiment to repair target closure.
    """
    packet["measurements"]["cap_position_error_mm"] = 0.1
    create(tmp_path / "baseline.json", packet)
    create(
        tmp_path / "inspection-plan.json", {"baseline_fingerprint": digest(packet), "sources": {}}
    )
    ledger = Ledger(tmp_path)
    assert ledger.state()["baseline"]["measurements"]["cap_position_error_mm"] == 0.1
    with pytest.raises(ValueError, match="already closed"):
        ledger.commit(prediction)
    assert not (tmp_path / "prediction.json").exists()


def test_landmarks_follow_fold_order_across_appearing_and_merged_runways() -> None:
    """
    Keep material identity when representation changes, while refusing a genuinely removed fold.
    """
    from experiments.experiment_ribbon_spatial_inspection.landmarks import identify, locate

    first = fold(2, 1.2, 0.9, 0.2, 0)
    second = fold(2, 1.2, -0.8, -0.2, 0)
    before = _route((first, second, Straight(2), Straight(3)))
    expanded = _route((Straight(1), first, Straight(0.5), second, Straight(10)))
    fold_point = identify(before, 1, 0.4)
    assert locate(expanded, fold_point) == (3, 0.4)
    straight_point = identify(before, 3, 0.5)
    assert locate(expanded, straight_point) == (4, 0.7)
    missing = _route((first, Straight(3)))
    assert locate(missing, fold_point) is None
