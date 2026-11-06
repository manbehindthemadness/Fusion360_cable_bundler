"""
Verify exact archived input coverage, immutable provenance and fail-fast replay accounting.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from experiments.experiment_ribbon_regression import runner
from experiments.experiment_ribbon_regression.corpus import load


def test_corpus_keeps_every_archived_problem_and_retained_control() -> None:
    """
    Keep all21unique problem inputs in the54case union with43retained controls.
    """
    corpus = load()
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
