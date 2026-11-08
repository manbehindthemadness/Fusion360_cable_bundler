"""
Verify exact archived input coverage, immutable provenance and fail-fast replay accounting.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from devtools.ribbon_analysis.gym.placement import adjacent
from experiments.experiment_ribbon_regression import runner
from experiments.experiment_ribbon_regression.corpus import CORPUS, load


def test_corpus_keeps_every_archived_problem_and_retained_control() -> None:
    """
    Keep all21unique problem inputs in the54case union with43retained controls.
    """
    corpus = load(CORPUS.with_name("gym-v1.json"))
    cases = corpus["cases"]
    assert len(cases) == 54
    controls = [
        c for c in cases if any(h["disposition"] == "retained_control" for h in c["history"])
    ]
    failures = [
        c for c in cases if any(h["disposition"] != "retained_control" for h in c["history"])
    ]
    assert len(controls) == 43 and len(failures) == 21
    assert len({case["signature"] for case in cases}) == 54
    assert {h["disposition"] for c in failures for h in c["history"]} >= {
        "numerical_unresolved",
        "native_or_fidelity",
        "boundary",
        "other_problem",
    }


def test_v2_corpus_preserves_v1_and_enrolls_trigger_with_three_passed_controls() -> None:
    """
    Keep every earlier case unchanged while retaining the current intersection and pre-fix collateral inputs.
    """
    original = load(CORPUS.with_name("gym-v1.json"))
    current = load(CORPUS.with_name("gym-v2.json"))
    for earlier, retained in zip(original["cases"], current["cases"][:54]):
        assert {k: v for k, v in earlier.items() if k != "history"} == {
            k: v for k, v in retained.items() if k != "history"
        }
        assert retained["history"][: len(earlier["history"])] == earlier["history"]
    added = current["cases"][54:57]
    assert len(added) == 3 and [case["targets"]["lines"] for case in added] == [9, 3, 4]
    assert [case["history"][0]["disposition"] for case in added] == [
        "retained_control",
        "retained_control",
        "numerical_unresolved",
    ]
    assert added[-1]["gym"]["config"]["seed"] == 321914440
    assert [case["lines"] for case in current["enrollment"]["cases"]] == [5, 9, 3, 4]
    assert current["enrollment"]["aliases_not_independent"][0]["retained_id"] == "range5fe-case-161"


def test_late_terminal_failure_keeps_three_preceding_controls_without_alias_inflation() -> None:
    """
    Retain the new N2/N10 controls and N7 failure; N8 remains the existing exact prior-case01.
    """
    corpus = load(CORPUS.with_name("gym-v2.json"))
    added = corpus["cases"][57:60]
    assert [c["targets"]["lines"] for c in added] == [2, 10, 7]
    assert [c["history"][0]["disposition"] for c in added] == [
        "retained_control",
        "retained_control",
        "numerical_unresolved",
    ]
    assert added[-1]["gym"]["config"]["seed"] == 3079315550


def test_fold_clearance_failure_retains_three_passed_controls_and_existing_alias() -> None:
    """
    Keep prior60inputs and add only the two genuinely new passed layouts plus current N4 failure.
    """
    corpus = load(CORPUS.with_name("gym-v2.json"))
    added = corpus["cases"][60:63]
    assert [c["id"] for c in added] == ["rangebec-case-5", "rangebec-case-6", "rangebec-case-7"]
    assert [c["history"][0]["disposition"] for c in added] == [
        "retained_control",
        "retained_control",
        "numerical_unresolved",
    ]
    assert added[-1]["gym"]["config"]["seed"] == 251693499


def test_measurement_failure_keeps_new_control_and_two_existing_aliases() -> None:
    """
    Preserve the prior 63 inputs, adding only a new passed N8 control and the N6 stop.
    """
    corpus = load(CORPUS.with_name("gym-v2.json"))
    added = corpus["cases"][63:65]
    assert [c["id"] for c in added] == ["range3887-case-9", "range3887-case-12"]
    assert [c["history"][0]["disposition"] for c in added] == [
        "retained_control",
        "numerical_unresolved",
    ]
    assert added[-1]["gym"]["config"]["seed"] == 626433965


def test_straight_quality_failure_keeps_preceding_controls_and_existing_alias() -> None:
    """
    Preserve prior 65 inputs and add only two new passed controls plus the N3 stop.
    """
    corpus = load(CORPUS.with_name("gym-v2.json"))
    added = corpus["cases"][65:68]
    assert [c["id"] for c in added] == [
        "range510-case-14",
        "range510-case-15",
        "range510-case-16",
    ]
    assert [c["history"][0]["disposition"] for c in added] == [
        "retained_control",
        "retained_control",
        "numerical_unresolved",
    ]
    assert added[-1]["gym"]["config"]["seed"] == 1104480256


def test_fold_quality_failure_keeps_all_three_preceding_passes() -> None:
    """
    Preserve the prior 68 inputs and retain all four distinct monitored boundary configurations.
    """
    corpus = load(CORPUS.with_name("gym-v2.json"))
    added = corpus["cases"][68:72]
    assert [c["id"] for c in added] == [f"ranged9c-case-{i}" for i in range(53, 57)]
    assert [c["history"][0]["disposition"] for c in added] == [
        "retained_control",
        "retained_control",
        "retained_control",
        "numerical_unresolved",
    ]
    assert added[-1]["gym"]["config"]["seed"] == 975394730


def test_completed_recovery_failure_keeps_three_alias_controls_and_one_new_input() -> None:
    """
    Retain the N1 stop without inflating the three preceding, already enrolled boundary inputs.
    """
    corpus = load(CORPUS.with_name("gym-v2.json"))
    assert len(corpus["cases"]) == 73
    case = corpus["cases"][-1]
    assert case["id"] == "range4c57-case-57"
    assert case["gym"]["config"]["seed"] == 2580358241
    assert case["history"][0]["disposition"] == "numerical_unresolved"
    for retained in corpus["cases"][69:72]:
        assert len(retained["history"]) == 2
        assert retained["history"][-1]["disposition"] == "retained_control"


def test_active_corpus_excludes_adjacent_inputs_without_changing_archived_cases() -> None:
    """
    Scope current QA to separated cells while preserving every retained record and historical failure.
    """
    archived = load(CORPUS.with_name("gym-v2.json"))
    current = load()
    expected = [
        case
        for case in archived["cases"]
        if not adjacent(case["gym"]["a"]["zone"], case["gym"]["b"]["zone"])
    ]
    assert current["revision"] == 3 and current["placement_policy"] == "separated_cubicles"
    assert len(current["cases"]) == 65 and current["cases"] == expected
    excluded = {case["id"] for case in current["exclusions"]}
    assert len(excluded) == 8
    assert excluded == {case["id"] for case in archived["cases"]} - {
        case["id"] for case in current["cases"]
    }
    assert {"historical-32e26c5c88b5", "historical-e03a89e210af"} <= excluded


@pytest.mark.parametrize("corruption", ("adjacent", "missing_gym", "zone", "policy"))
def test_active_placement_policy_rejects_invalid_enrollment(
    tmp_path: Path, corruption: str
) -> None:
    """
    Stop inadmissible or unidentified placement before it can create another false solver failure.
    """
    corpus = load()
    if corruption == "adjacent":
        archived = load(CORPUS.with_name("gym-v2.json"))
        corpus["cases"].append(
            next(case for case in archived["cases"] if case["id"] == "historical-32e26c5c88b5")
        )
    elif corruption == "missing_gym":
        corpus["cases"][0].pop("gym")
    elif corruption == "zone":
        corpus["cases"][0]["gym"]["a"]["zone"] = True
    else:
        corpus["placement_policy"] = "seperated_cubicles"
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus))
    with pytest.raises(ValueError, match="cubicle|placement"):
        load(path)


@pytest.mark.parametrize("corruption", ("duplicate", "target", "provenance", "settings"))
def test_corpus_rejects_changed_or_unidentified_inputs(tmp_path: Path, corruption: str) -> None:
    """
    Never silently regenerate, merge or normalize malformed historical inputs.
    """
    corpus = load()
    if corruption == "duplicate":
        corpus["cases"].append(corpus["cases"][0])
    elif corruption == "target":
        corpus["cases"][0]["targets"]["start"]["x"] += 0.001
    elif corruption == "provenance":
        corpus["cases"][0]["history"] = []
    else:
        corpus["cases"][0]["settings"] = None
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus))
    with pytest.raises(ValueError):
        load(path)


def test_candidate_regression_stops_before_next_case_and_keeps_unattempted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A lost accepted route halts execution while preserving all planned denominators.
    """
    cases = load()["cases"][:3]
    monkeypatch.setitem(vars(runner), "load", lambda: {"cases": cases})
    monkeypatch.setitem(vars(runner), "_pins", lambda: {"source": "fixed"})
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    (baseline / "plan.json").write_text(json.dumps({"cases": cases}))
    (baseline / "result.json").write_text(json.dumps({"stop": None}))
    for case in cases:
        (baseline / f"{case['id']}.json").write_text(
            json.dumps({"route": {"material_length_mm": 10}})
        )
    calls: list[str] = []

    def worker(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """
        Supply a controlled rejection without running geometry in this harness contract test.
        """
        del kwargs
        directory, identity = Path(command[-2]), command[-1]
        calls.append(identity)
        (directory / f"{identity}.json").write_text(json.dumps({"route": None, "detail": {}}))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(runner.subprocess, "run", worker)
    output = tmp_path / "candidate"
    result = runner.run(output, baseline)
    assert calls == [cases[0]["id"]]
    assert result["evaluated"] == 1 and result["accepted"] == 0
    assert result["rows"][0]["regression"]
    assert result["unattempted"] == [case["id"] for case in cases[1:]]
    assert "representative regression" in result["stop"]
    assert json.loads((output / "result.json").read_text()) == result


@pytest.mark.parametrize("value", (True, None, 0, -1, "12", float("nan"), float("inf")))
def test_malformed_result_lengths_cannot_become_quality_passes(value: Any) -> None:
    """
    Treat nonphysical or missing lengths as harness errors before numerical comparison.
    """
    with pytest.raises(ValueError, match="positive finite"):
        runner._length({"material_length_mm": value})
    assert runner._length(None) is None
    assert runner._length({"material_length_mm": 12}) == 12.0
