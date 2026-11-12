"""
Keep compact selected-case diagnostics immutable and isolated from fresh validation.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.inspection.archive import read_document, targets_payload
from experiments.experiment_ribbon_case_library.library import CaseLibrary
from experiments.experiment_ribbon_case_library.recipe import from_plan
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_regression.fresh import FreshRegistry


def _recipe() -> dict[str, Any]:
    """
    Author new endpoint controls without reading a saved solver layout or invoking geometry search.
    """
    scene = Scene(Config(7, 3, 0.75), Goal.from_degrees(0, 0, 15), Goal.from_degrees(25, 4, 280))
    return {
        "config": asdict(scene.config),
        "a": scene.a.payload(),
        "b": scene.b.payload(),
        "targets": targets_payload(scene.targets),
        "solver_version": "guide-material-v2",
        "settings": asdict(Settings()),
        "policy": {
            "native_point_tolerance_mm": 1e-5,
            "contact_measurement_policy": "require_separation",
            "limits": {
                "launch_rss_kib": 3984588,
                "native_seconds": 120,
                "numerical_seconds": 120,
                "rss_bytes": 4294967296,
            },
        },
    }


def _provenance() -> dict[str, Any]:
    """
    Supply small original-evidence metadata without a route, kernel object or acceptance claim.
    """
    return {
        "run_id": "authored-control",
        "run_seed": 7,
        "ordinal": 1,
        "original_outcome": "unresolved",
        "sources_sha256": "a" * 64,
        "evidence": "artifacts/authored-control",
    }


def test_exact_values_immutable_records_and_endpoint_only_export(tmp_path: Path) -> None:
    """
    Preserve exact targets and settings while labelling reconstruction as nonfresh and unexecuted.
    """
    library = CaseLibrary(tmp_path / "selected.sqlite3")
    recipe, provenance = _recipe(), _provenance()
    exact = json.loads(json.dumps(recipe))
    library.save("control", recipe, provenance)
    recipe["targets"]["start"]["x"] += 1
    stored = library.load("control")
    assert stored["recipe"] == exact and stored["fresh_validation"] is False
    stored["recipe"]["config"]["seed"] = 999
    assert library.load("control")["recipe"] == exact
    with pytest.raises(sqlite3.IntegrityError):
        library.save("control", exact, provenance)
    assert library.identifiers() == ("control",)
    destination = tmp_path / "replay.json"
    library.export("control", destination)
    replay = read_document(destination)
    assert replay["targets"] == exact["targets"] == replay["gym"]["targets"]
    assert replay["gym"]["config"] == exact["config"]
    assert replay["diagnostic_replay"]["fresh_validation"] is False
    assert replay["solvers"][0]["status"] == "not_run"
    assert "route" not in replay and "pieces" not in replay
    before = destination.read_bytes()
    with pytest.raises(FileExistsError):
        library.export("control", destination)
    assert destination.read_bytes() == before
    with pytest.raises(KeyError):
        library.load("absent")


def test_fresh_novelty_and_statistics_remain_byte_identical(tmp_path: Path) -> None:
    """
    Catalogue operations cannot write fresh reservations/statistics, even when pointed at that database.
    """
    fresh = FreshRegistry(tmp_path / "novelty.sqlite3")
    fresh.remember(("a" * 64,), seed=123)
    fresh.record("previous", {"population": "authored"}, {"attempted": 7, "failed": 2})
    baseline = fresh.path.read_bytes()
    statistics = fresh.statistics()
    library = CaseLibrary(tmp_path / "selected.sqlite3")
    library.save("known-failure", _recipe(), _provenance())
    library.export("known-failure", tmp_path / "replay.json")
    assert fresh.statistics() == statistics and fresh.path.read_bytes() == baseline
    with pytest.raises(ValueError, match="foreign databases remain untouched"):
        CaseLibrary(fresh.path)
    assert fresh.path.read_bytes() == baseline
    assert fresh.statistics() == statistics


@pytest.mark.parametrize(
    "change",
    ("route", "missing", "nonfinite", "seed", "goals", "settings", "policy", "limits", "tolerance"),
)
def test_incomplete_or_geometry_payloads_are_rejected_before_storage(
    tmp_path: Path, change: str
) -> None:
    """
    Do not turn saved solids/routes, malformed controls or incomplete inputs into a case recipe.
    """
    recipe = _recipe()
    if change == "route":
        recipe["route"] = {"pieces": []}
    elif change == "missing":
        del recipe["targets"]
    elif change == "nonfinite":
        recipe["targets"]["start"]["x"] = math.nan
    elif change == "seed":
        recipe["config"]["seed"] = True
    elif change == "goals":
        recipe["b"] = recipe["a"]
    elif change == "settings":
        recipe["settings"]["terminal_hardware"] = "yes"
    elif change == "policy":
        recipe["policy"]["contact_measurement_policy"] = "accept_anything"
    elif change == "limits":
        recipe["policy"]["limits"]["rss_bytes"] = -1
    else:
        recipe["policy"]["native_point_tolerance_mm"] = 0
    library = CaseLibrary(tmp_path / "selected.sqlite3")
    with pytest.raises(ValueError):
        library.save("invalid", recipe, _provenance())
    assert library.identifiers() == ()


def test_generator_drift_cannot_move_saved_targets_to_fit_a_new_layout(tmp_path: Path) -> None:
    """
    Recreate no document when seed-derived input poses no longer match the original fixed targets.
    """
    recipe = _recipe()
    recipe["targets"]["start"]["x"] += 0.01
    library = CaseLibrary(tmp_path / "selected.sqlite3")
    library.save("drift", recipe, _provenance())
    destination = tmp_path / "drift.json"
    with pytest.raises(ValueError, match="disagrees"):
        library.export("drift", destination)
    assert not destination.exists()


def test_integrity_and_record_size_are_guarded(tmp_path: Path) -> None:
    """
    Reject accidentally embedded large data and corrupted SQLite records instead of silently replaying them.
    """
    library = CaseLibrary(tmp_path / "selected.sqlite3")
    provenance = _provenance()
    provenance["evidence"] = "x" * 32768
    with pytest.raises(ValueError, match="below32KiB"):
        library.save("large", _recipe(), provenance)
    library.save("control", _recipe(), _provenance())
    with sqlite3.connect(library.path) as connection:
        # noinspection SqlNoDataSourceInspection
        connection.execute("UPDATE cases SET record='{}' WHERE identifier='control'")
    with pytest.raises(ValueError, match="integrity mismatch"):
        library.load("control")


def test_original_plan_extraction_discards_generated_geometry_and_source_inventory() -> None:
    """
    Keep only values needed for selected recreation, never a second archive of CAD or solver output.
    """
    expected = _recipe()
    original = {
        "gym": {**expected, "drawing": {"large": "not retained"}, "solids": []},
        "targets": expected["targets"],
        "version": expected["solver_version"],
        "settings": expected["settings"],
        "sources": {"path.py": "unused listing"},
        "route": {"pieces": []},
        **expected["policy"],
    }
    assert from_plan(original) == expected


def test_finished_case_import_is_explicit_and_checks_original_run_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Import one authored finished ordinal without scheduling or mutating any campaign.
    """
    from experiments.experiment_ribbon_case_library import __main__ as command

    monkeypatch.setattr(command, "ROOT", tmp_path)
    run, journal, job = (tmp_path / name for name in ("run", "journal", "job"))
    for directory in (run, journal, job):
        directory.mkdir()
    recipe = _recipe()
    sources = {"authored.py": "b" * 64}
    (run / "plan.json").write_text(
        json.dumps({"identifier": "run", "specification": {"seed": 7}, "sources": sources})
    )
    (run / "started.json").write_text(json.dumps({"identifier": "run", "journal": str(journal)}))
    (journal / "cases.jsonl").write_text(
        json.dumps({"event": "case_finished", "case": 1, "job": str(job), "problem": "unresolved"})
        + "\n"
    )
    (job / "plan.json").write_text(
        json.dumps(
            {
                "gym": recipe,
                "targets": recipe["targets"],
                "version": recipe["solver_version"],
                "settings": recipe["settings"],
                "sources": sources,
                **recipe["policy"],
            }
        )
    )
    (job / "numerical-result.json").write_text(json.dumps({"status": "unresolved"}))
    library = CaseLibrary(tmp_path / "selected.sqlite3")
    command.save_finished(library, "chosen", run, 1)
    stored = library.load("chosen")
    assert stored["recipe"] == recipe
    assert stored["provenance"]["original_outcome"] == "unresolved"
    assert stored["provenance"]["ordinal"] == 1 and stored["provenance"]["evidence"] == "job"
    with pytest.raises(ValueError, match="finished original"):
        command.save_finished(library, "unattempted", run, 2)
    (run / "started.json").write_text(json.dumps({"identifier": "other", "journal": str(journal)}))
    with pytest.raises(ValueError, match="identity disagrees"):
        command.save_finished(library, "wrong-run", run, 1)
    assert library.identifiers() == ("chosen",)
