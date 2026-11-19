"""
Verify live endpoint derivation capture, unchanged numerical decisions and explicit missing placement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devtools.ribbon_analysis.construction.journal import Journal, load
from experiments.experiment_ribbon_constrained_construction.disjunction import Work
from experiments.experiment_ribbon_constrained_construction.envelopes import Exclusion
from experiments.experiment_ribbon_constrained_construction.frontier import Case, Frontier
from experiments.experiment_ribbon_constrained_construction.linear import Problem, Row
from experiments.experiment_ribbon_constrained_construction.terminal_approaches import chains
from experiments.experiment_ribbon_construction_diagnostic import origin_run
from experiments.experiment_ribbon_construction_diagnostic.origin import OriginTrace
from experiments.experiment_ribbon_joint_route.allocation import Model
from tests.test_ribbon_terminal_approaches import boundary, checkpoint


def test_derivation_starts_at_targets_and_links_placements_to_rotation_factors(
    tmp_path: Path,
) -> None:
    """
    A fresh trace records actual endpoint-derived roots without restoring any saved route.
    """
    source = boundary()
    journal = Journal(tmp_path / "trace.jsonl", "analytical origin", {})
    observer = OriginTrace(journal, source)
    try:
        observed = chains(source, checkpoint, trace=observer)
        assert observed == chains(source, checkpoint)
        model = Model(source, observed[0].topology)
        columns, right = model.straight_equations()
        problem = Problem(
            (1.0,) * len(columns),
            tuple(
                Row(axis, tuple(column[i] for column in columns), right[i])
                for i, axis in enumerate("xyz")
            ),
            (),
        )
        observer.prepared(model, problem, ())
    finally:
        journal.close()
    packet = load(journal.path)
    steps, features = packet["steps"], packet["features"]
    assert [step["phase"] for step in steps[:3]] == ["input", "preplot", "preplot"]
    assert {value["feature"] for value in steps[0]["scene"]} == {"End A", "End B"}
    assert all(step["basis"] == "observed" for step in steps)
    bend = next(step for step in steps if step["phase"] == "bend")
    assert bend["scene"][0]["space"] == "local"
    assert bend["scene"][0]["details"]["world_placement_not_chosen"]
    root = observed[0].topology.identifier
    assert all(parent.startswith("rotation-") for parent in features[root]["parents"])
    assert features[root + "/F1"]["parents"] == [root]
    assert "not a complete or accepted route" in steps[-1]["details"]["warning"]


def test_endpoint_only_runner_refuses_saved_route_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A route-shaped payload cannot silently become a supposedly from-scratch capture.
    """
    directory = tmp_path / "artifacts/verification"
    directory.mkdir(parents=True)
    source, output = directory / "input.json", directory / "output"
    source.write_text(json.dumps({"route": {"pieces": []}}), encoding="utf-8")
    monkeypatch.setattr(origin_run, "ROOT", tmp_path)
    monkeypatch.setattr(
        origin_run.sys, "argv", ["origin_run", "--input", str(source), "--output", str(output)]
    )
    with pytest.raises(ValueError, match="Endpoint-only"):
        origin_run.main()
    assert not output.exists()


def test_live_frontier_capture_preserves_decisions_and_records_why_lengths_change() -> None:
    """
    An observer sees actual branch constraints while leaving best/root/work accounting unchanged.
    """
    case = Case(
        "derived",
        Problem((1, 1), (Row("closure", (1, 0.5), 10),), ()),
        (Exclusion("separate", ((Row("detour", (0, 1), 12),),)),),
        1.0,
        0.0,
    )
    events: list[dict[str, Any]] = []
    observed, plain = Frontier((case,), Work(), trace=events.append), Frontier((case,), Work())
    observed.run(checkpoint)
    plain.run(checkpoint)
    assert (observed.best, observed.inspection, observed.work, observed.status) == (
        plain.best,
        plain.inspection,
        plain.work,
        plain.status,
    )
    assert events[0]["unsatisfied_exclusions"] == ["separate"]
    branch = next(event for event in events if event["stage"] == "separation_branch")
    assert branch["exclusion"]["alternatives"][0][0]["name"] == "detour"
    assert events[-1]["unsatisfied_exclusions"] == []
    assert events[-1]["best_length_mm"] == pytest.approx(16)


def test_observer_failure_preserves_prefix_and_stops_instead_of_losing_origin(
    tmp_path: Path,
) -> None:
    """
    Capture errors propagate before any later bend/placement can be misrepresented as fully traced.
    """
    events: list[dict[str, Any]] = []

    def fail(event: dict[str, Any]) -> None:
        """
        Model an exhausted recorder after the endpoint record.
        """
        events.append(event)
        if event["stage"] == "handles":
            raise OSError("recorder stopped")

    with pytest.raises(OSError, match="recorder stopped"):
        chains(boundary(), checkpoint, trace=fail)
    assert [event["stage"] for event in events] == ["targets", "handles"]
    journal = Journal(tmp_path / "unknown.jsonl", "unknown origin", {})
    try:
        with pytest.raises(ValueError, match="Unknown origin"):
            OriginTrace(journal, boundary())({"stage": "invented"})
    finally:
        journal.close()
