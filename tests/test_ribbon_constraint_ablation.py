"""
Verify effective rule ablations, immutable field policies and matched archived evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from devtools.ribbon_analysis.contracts import RibbonPath
from devtools.ribbon_analysis.inspection.archive import snapshot_payload, write_document
from devtools.ribbon_analysis.inspection.capture import read_history
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
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_diagnostic_viewer import ablation, examples, interactive_worker
from experiments.experiment_ribbon_diagnostic_viewer.procedures import selections
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
    selected = selections([{"id": "compatible", "settings": {"excerpt": 16}}])
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


def test_worker_archives_matched_scopes_and_panels_preserve_proposal_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep both runs, full measurements, matching settings and original evidence immutable.
    """
    reference = examples.create(tmp_path / "reference", "ribbon", lambda: None)
    (tmp_path / "input.json").write_bytes(reference.read_bytes())
    requested = selections([{"id": "ordinary", "settings": {"excerpt": 0}}])
    write_document(
        tmp_path / "plan.json",
        {
            "run_id": "pair",
            "procedures": requested,
            "comparison": {"origin": "original", "disabled_rules": ["end_position"]},
            "sources": {"fixed": "test"},
            "minimum_radius_mm": 4.5,
        },
    )
    monkeypatch.setattr(interactive_worker.procedures, "source_pins", lambda: {"fixed": "test"})
    monkeypatch.setattr(interactive_worker.budget, "resident_kib", lambda: 10000)
    policies: list[ConstraintPolicy] = []

    def execute(
        identifier: str,
        case: EndpointCase,
        settings: dict[str, Any],
        checkpoint: Callable[[], None],
    ) -> tuple[RibbonPath, dict[str, Any]]:
        """
        Observe scoped policies through a real unchanged transported start.
        """
        assert identifier == "ordinary" and settings == requested[0]["settings"]
        policies.append(current())
        path = broad_chart.integrate(case, (0.0,) * 9 + (1.2,), 64, checkpoint)
        return path, {"coordinates": (9.0,) * 10, "score": 7.0}

    monkeypatch.setattr(interactive_worker.adapters, "execute", execute)
    result = interactive_worker.run(tmp_path)
    data = json.loads(result.read_text())
    assert data["stopped"] is None and len(data["solvers"]) == 2
    assert policies == [FULL, parse(["end_position"])] and current() == FULL
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
