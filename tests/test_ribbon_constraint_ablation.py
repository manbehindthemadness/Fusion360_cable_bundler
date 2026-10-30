"""
Verify effective rule ablations, immutable field policies and matched archived evidence.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from devtools.ribbon_analysis.inspection.archive import snapshot_payload, write_document
from devtools.ribbon_analysis.inspection.capture import SearchRecorder, read_history
from devtools.ribbon_analysis.inspection.geometry import freeze_path
from devtools.ribbon_analysis.inspection.measurements import observations
from devtools.ribbon_analysis.inspection.panels import build
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
)
from experiments.experiment_ribbon_cap_transition.constraint_policy import (
    FULL,
    ConstraintPolicy,
    Rule,
    current,
    parse,
    scope,
)
from experiments.experiment_ribbon_cap_transition.director_route_objective import routing_penalties
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.director_shooting import (
    endpoint_metrics,
    residual,
)
from experiments.experiment_ribbon_diagnostic_viewer import ablation, examples
from experiments.experiment_ribbon_route_discovery import broad_chart


@pytest.mark.parametrize("lines,rule", ((3, Rule.LANE_BEND), (19, Rule.CENTRE_BEND)))
def test_disabling_an_active_bend_bound_changes_the_actual_field(lines: int, rule: Rule) -> None:
    """
    Remove the binding geometric cap rather than merely zeroing a displayed measurement.
    """
    raw = RoutingField("tight", 4, (50, 0, 0, 0), (0, 0, 0, 0), lines, 1.5)
    full = CompatibleField(raw, BendMapping.NEAR_LIMIT)
    with scope(ConstraintPolicy(frozenset((rule,)))):
        disabled = CompatibleField(raw, BendMapping.NEAR_LIMIT)
    assert disabled.carrier(0.5).turn > full.carrier(0.5).turn
    assert disabled.constraints.disabled == frozenset((rule,))
    assert current() == FULL
    with scope(ConstraintPolicy(frozenset((Rule.CENTRE_BEND, Rule.LANE_BEND)))):
        unrestricted = CompatibleField(raw, BendMapping.NEAR_LIMIT)
    assert unrestricted.carrier(0.5).turn == 50
    assert unrestricted.ruling_scale == full.ruling_scale


@pytest.mark.parametrize(
    "rule,block", ((Rule.END_POSITION, 0), (Rule.END_TANGENT, 1), (Rule.END_WIDTH, 2))
)
def test_pose_ablation_changes_only_its_objective_block_and_keeps_measurements(
    rule: Rule,
    block: int,
) -> None:
    """
    Preserve fixed targets and reported errors when omitting one search objective.
    """
    _, case = examples.ribbon(lambda: None)
    values = (0.0,) * 9 + (1.2,)
    full = broad_chart.integrate(case, values, 64, lambda: None)
    with scope(ConstraintPolicy(frozenset((rule,)))):
        disabled = broad_chart.integrate(case, values, 64, lambda: None)
    original, changed = residual(case, full), residual(case, disabled)
    for index, value in enumerate(changed):
        assert value == (0 if index // 3 == block else original[index])
    assert full.states == disabled.states
    assert endpoint_metrics(case, full) == endpoint_metrics(case, disabled)
    measured = observations(freeze_path("disabled", disabled, intervals=64), case, 4.5)
    position = next(item for item in measured if item.name == "Fixed endpoint position")
    assert position.status == "failed" and position.value is not None and position.value > 0.75


def test_default_policy_preserves_exact_geometry_and_context_restores_after_failure() -> None:
    """
    Keep all existing callers on the unchanged complete policy, including nested failures.
    """
    _, case = examples.ribbon(lambda: None)
    values = (0.1,) * 9 + (1.2,)
    first = broad_chart.integrate(case, values, 64, lambda: None)
    with scope(FULL):
        second = broad_chart.integrate(case, values, 64, lambda: None)
    assert snapshot_payload(freeze_path("same", first, intervals=64)) == snapshot_payload(
        freeze_path("same", second, intervals=64)
    )
    with pytest.raises(RuntimeError):
        with scope(parse(["centre_bend"])):
            raise RuntimeError("Expected scope exit")
    assert current() == FULL


def test_disabled_bend_penalties_do_not_hide_independent_radius_failures() -> None:
    """
    Retain violated reference rules on an uncapped transport with zeroed search slots.
    """
    _, case = examples.ribbon(lambda: None)
    values = (8.0, 0, 0, 0, 0, 0, 0, 0, 0, 1.0)
    with scope(parse(["centre_bend", "lane_bend"])):
        path = broad_chart.integrate(case, values, 64, lambda: None)
    errors = routing_penalties(case, path)
    assert all(value == 0 for value in errors[1::3])
    assert all(value == 0 for value in errors[2::3])
    rules = observations(freeze_path("uncapped", path, intervals=64), case, 4.5)
    assert next(rule for rule in rules if rule.name == "Material-guide bend cap").status == "failed"


@pytest.mark.parametrize("rules", (["bogus"], ["lane_bend", "lane_bend"], [True], None))
def test_malformed_or_unimplemented_controls_reject(rules: Any) -> None:
    """
    Prevent unsupported controls from becoming ineffective or unrecorded flags.
    """
    with pytest.raises(ValueError):
        parse(rules)


def test_workloads_pair_the_same_settings_and_refuse_partial_adapters() -> None:
    """
    Restrict ablations to fully implemented search paths and retain a fresh baseline.
    """
    selected = [{"id": "compatible", "settings": {"excerpt": 16, "bend_model": "legacy"}}]
    work = ablation.workloads(
        selected, {"origin": "old:compatible", "disabled_rules": ["centre_bend", "lane_bend"]}
    )
    assert [item["role"] for item in work] == ["baseline", "ablation"]
    assert work[0]["settings"] == work[1]["settings"] == selected[0]["settings"]
    assert work[0]["disabled_rules"] == []
    with pytest.raises(ValueError):
        ablation.validate("broad", ["centre_bend"])
    with pytest.raises(ValueError):
        ablation.validate("redistribution", ["lane_bend"])
    assert ablation.validate("redistribution", ["end_position"]).disabled


def test_archived_matched_scopes_and_panels_preserve_proposal_provenance(tmp_path: Path) -> None:
    """
    Replay historical paired records without invoking the retired worker or discovery.
    """
    reference = examples.create(tmp_path / "reference", "ribbon", lambda: None)
    data = json.loads(reference.read_text())
    _, case = examples.ribbon(lambda: None)
    methods = []
    for role, disabled in (("baseline", []), ("ablation", ["end_position"])):
        identifier = f"pair:ordinary:{role}"
        recorder = SearchRecorder(tmp_path / f"{role}.jsonl", "ordinary", lambda: None)
        with scope(parse(disabled)), recorder.recording():
            path = broad_chart.integrate(case, (0.0,) * 9 + (1.2,), 64, lambda: None)
        snapshot = freeze_path(identifier, path, intervals=64)
        methods.append(
            {
                "id": identifier,
                "label": role,
                "source": "Frozen historical comparison",
                "detail": "Recorded transport; no physical acceptance.",
                "status": "unresolved",
                "procedure": "ordinary",
                "disabled_rules": disabled,
                "settings": {"bend_model": "legacy", "seconds": 8},
                "comparison": {
                    "role": role,
                    "baseline": "pair:ordinary:baseline",
                    "origin": "original",
                },
                "history": f"{role}.jsonl",
                "snapshot": snapshot_payload(snapshot),
                "rules": [asdict(rule) for rule in observations(snapshot, case, 4.5)],
                "metrics": {"coordinates": (9.0,) * 10, "score": 7.0},
            }
        )
    data["solvers"] = methods
    result = tmp_path / "historical.json"
    write_document(result, data)
    session = Session(result)
    session.select("pair:ordinary:ablation")
    assert session.baseline() is not None
    assert session.methods[0]["settings"] == session.methods[1]["settings"]
    assert session.methods[1]["disabled_rules"] == ["end_position"]
    comparison_state = session.comparison_state()
    assert comparison_state is not None
    position = next(
        row for row in comparison_state["measurements"] if row["name"] == "Fixed endpoint position"
    )
    assert position["current"] > 0.75
    assert session.snapshot is not None
    _, summary, chart = build(session.state(), session.snapshot)
    assert any("end_position" in note for note in summary.notes)
    assert len(chart.strokes) == 4
    session.select("pair:ordinary:ablation", 0)
    assert session.snapshot is not None
    _, proposal_summary, _ = build(session.state(), session.snapshot)
    assert any("Coordinates were not recorded" in note for note in proposal_summary.notes)
    assert not any("c0=9" in note for note in proposal_summary.notes)


def test_older_decisions_keep_unknown_coordinates_instead_of_inventing_final_values(
    tmp_path: Path,
) -> None:
    """
    Retain replay compatibility when an older decision has no coordinate telemetry.
    """
    path, _ = examples.ribbon(lambda: None)
    snapshot = freeze_path("old", path, intervals=16)
    history = tmp_path / "old.jsonl"
    history.write_text(
        json.dumps(
            {"kind": "path", "sequence": 0, "stage": "old", "snapshot": snapshot_payload(snapshot)}
        )
        + "\n"
        + json.dumps({"kind": "decision", "sequence": 0, "score": 1.0, "accepted": True})
        + "\n"
    )
    records = read_history(history)
    assert records[0]["coordinates"] is None
    assert records[0]["accepted"]
