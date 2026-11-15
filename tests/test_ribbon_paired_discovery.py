"""
Verify moving-hardware evidence, row ownership and nonrenewable paired accounting.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.separation import Region, regions
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_paired_return import discovery
from experiments.experiment_ribbon_paired_return.allocation import HardwareRow, MaterialRow
from experiments.experiment_ribbon_paired_return.discovery import Discovery
from experiments.experiment_ribbon_paired_return.ledger import Ledger
from experiments.experiment_ribbon_paired_return.native_model import NativeJoints
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import FeatureEvidence
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware, Terminal
from experiments.experiment_ribbon_terminal_hardware.probe_domain import ProbeDomain
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_pair_family_motion import _route


@dataclass(frozen=True)
class MovingScene:
    """
    Share real open placement and accounting with explicitly doubled negative discovery.
    """

    model: NativeJoints
    current: FoldRoute
    values: tuple[float, ...]
    gate: Mock
    ledger: Ledger
    report: Report
    domain: ProbeDomain


@pytest.fixture
def moving_scene(monkeypatch: pytest.MonkeyPatch) -> MovingScene:
    """
    Charge one actual correction and prepare one source-bound synthetic hardware report.

    The report/probe boundary is doubled; this fixture proves no intrusion.
    Complete material placement and later guidance preparation remain real.
    """
    source = _route(1, 1)
    model = NativeJoints(source, 1e-5)
    moved = list(model.initial)
    moved[0] += 0.01
    values = tuple(moved)
    current = model.route(values)
    assert current is not None
    domain = ProbeDomain(current, ((Terminal.START, 2),))
    monkeypatch.setitem(vars(discovery), "moving_domain", Mock(return_value=domain))
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    report = Report("blocked", 1, Witness("start", 2, (0.5, 0, 0), Vector3(0, 0, 0), (0, 0, 0)))
    gate = Mock(hardware=hardware)
    gate.probe.return_value = report
    ledger = Ledger(Work(1, 2048, 0.35, 2, 6), 2, lambda: None)
    ledger.start_action()
    ledger.start_newton()
    return MovingScene(model, current, values, gate, ledger, report, domain)


@pytest.mark.parametrize("capacity", [False, True])
def test_measured_open_pose_retains_all_rows_and_final_material_suffix(
    moving_scene: MovingScene, capacity: bool
) -> None:
    """
    Keep exact evidence and decline whole on capacity, without a new action or projection.
    """
    scene = moving_scene
    features: dict[tuple[object, ...], FeatureEvidence] = {}
    events = []
    context = Discovery(scene.gate, features, scene.ledger, events.append)
    context.begin(scene.model, scene.ledger)
    material = MaterialRow(Mock(), scene.model.scale)
    original = tuple([lambda coordinates: -1.0] * (12 if capacity else 1)) + (material,)
    result = context.scan(scene.model, scene.current, scene.values, original)
    assert context.latest is not None and context.latest.route is scene.current
    assert (
        context.latest.report is scene.report
        and scene.gate.probe.call_args.args[0] is scene.current
    )
    assert scene.gate.probe.call_args.kwargs["domain"] is scene.domain
    assert (scene.ledger.updates, scene.ledger.newton_steps, scene.ledger.roots) == (1, 1, 0)
    if capacity:
        assert result.stop == "hardware_row_capacity" and result.rows is original
        assert not features and not events
    else:
        assert result.stop is None and result.rows[-1] is material
        assert result.rows[0] is original[0] and len(result.rows) > len(original)
        assert all(isinstance(row, HardwareRow) for row in result.rows[1:-1])
        key = ("start", regions(scene.current)[2])
        assert features[key] is context.latest
        assert events[-1]["newton"] == 1
        context.scan(scene.model, scene.current, scene.values, result.rows)
        assert scene.gate.probe.call_count == 1


def test_feature_capacity_and_external_errors_preserve_failure_evidence(
    moving_scene: MovingScene,
) -> None:
    """
    Do not drop a fourth blocker or hide source/cancellation failures as optional declines.
    """
    scene = moving_scene
    features = {
        ("end", Region(i, False)): FeatureEvidence(
            scene.model.original,
            Report(
                "blocked", 1, Witness("end", 2 * i + 1, (0.5, 0, 0), Vector3(0, 0, 0), (0, 0, 0))
            ),
        )
        for i in range(3)
    }
    context = Discovery(scene.gate, features, scene.ledger, Mock())
    context.begin(scene.model, scene.ledger)
    rows = (lambda coordinates: -1.0,)
    result = context.scan(scene.model, scene.current, scene.values, rows)
    assert result.rows is rows and result.stop == "hardware_feature_capacity"
    assert (
        context.latest is not None and context.latest.route is scene.current and len(features) == 3
    )
    context.begin(scene.model, scene.ledger)
    failure = RuntimeError("source changed")
    scene.gate.probe.side_effect = failure
    with pytest.raises(RuntimeError, match="source changed") as caught:
        context.scan(scene.model, scene.current, scene.values, rows)
    assert caught.value is failure
    with pytest.raises(ValueError, match="original ledger"):
        context.begin(scene.model, Ledger(scene.ledger.work, 2, lambda: None))
    with pytest.raises(ValueError, match="exact correction model"):
        context.scan(
            NativeJoints(replace(scene.model.original), 1e-5), scene.current, scene.values, rows
        )


@pytest.mark.parametrize("limited", [False, True])
@pytest.mark.parametrize("steps", [1, 2])
@pytest.mark.parametrize("proof_clear", [False, True])
def test_closed_mating_proposal_requires_guidance_or_actual_hardware_proof(
    monkeypatch: pytest.MonkeyPatch,
    limited: bool,
    steps: int,
    proof_clear: bool,
) -> None:
    """
    Spend the next original Newton slot on a newly measured inequality, without accepting stale guidance.

    Actual mating geometry remains active; discovery and the declining angular
    projector are boundary doubles, so no hardware-clearance claim is made.
    """
    from experiments.experiment_ribbon_paired_return import continuation

    original = _route(1, 1)
    source = replace(
        original,
        targets=replace(
            original.targets,
            end=original.targets.end.translated(original.targets.start_tangent, 4e-6),
        ),
    )
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    monkeypatch.setitem(
        vars(continuation), "constraints", Mock(return_value=(lambda values: -1.0,))
    )
    projected = Mock(return_value=None)
    monkeypatch.setitem(vars(continuation), "redistributed_step", projected)
    ledger = Ledger(Work(1, 2048, 0.35, 2, steps), 0, lambda: None)
    ledger.start_action()
    context = Mock(spec=Discovery)
    context.certify_stalled.return_value = proof_clear

    def discover(
        model: NativeJoints,
        route: FoldRoute,
        values: tuple[float, ...],
        rows: tuple[discovery.Equation, ...],
    ) -> discovery.Refresh:
        """
        Make the newly closed proposal fail its newly observed physical inequality.
        """
        assert ledger.newton_steps == 1 and values != model.initial
        assert route.targets is model.original.targets
        return (
            discovery.Refresh(rows, "hardware_row_capacity")
            if limited
            else discovery.Refresh((*rows, lambda coordinates: 1.0))
        )

    context.scan.side_effect = discover
    result = continuation.correct_started(
        source, source, (), (), (), hardware, 1e-5, ledger, Mock(), discovery=context
    )
    assert (result is not None) == (steps == 2 and not limited and proof_clear)
    assert context.scan.call_count == 1 and not projected.called
    assert context.certify_stalled.call_count == int(steps == 2 and not limited)
    assert (ledger.updates, ledger.newton_steps, ledger.roots) == (
        1,
        2 if steps == 2 and not limited else 1,
        0,
    )


@pytest.mark.parametrize("status", ["unresolved", "clear"])
def test_no_intrusion_report_cannot_create_guidance_or_finish_the_solver(
    moving_scene: MovingScene, status: Literal["unresolved", "clear"]
) -> None:
    """
    Preserve all equations and work when discovery supplies no actual negative witness.
    """
    scene = moving_scene
    scene.gate.probe.return_value = Report(status, 1)
    features: dict[tuple[object, ...], FeatureEvidence] = {}
    context = Discovery(scene.gate, features, scene.ledger, Mock())
    context.begin(scene.model, scene.ledger)
    rows = (lambda coordinates: -1.0,)
    result = context.scan(scene.model, scene.current, scene.values, rows)
    assert result.rows is rows and result.stop is None
    assert context.latest is None and not features
    assert (scene.ledger.updates, scene.ledger.newton_steps, scene.ledger.roots) == (1, 1, 0)


@pytest.mark.parametrize("status", ["clear", "blocked", "unresolved"])
def test_stalled_hardware_proof_preserves_exact_pose_and_never_grants_self_contact(
    moving_scene: MovingScene, status: Literal["clear", "blocked", "unresolved"]
) -> None:
    """
    Require closed caps, retain negative/incomplete reports, and return only hardware eligibility.
    """
    scene = moving_scene
    report = Report(status, 3)
    scene.gate.certify.return_value = report
    context = Discovery(scene.gate, {}, scene.ledger, Mock())
    context.begin(scene.model, scene.ledger)
    closed = scene.model.original
    assert context.certify_stalled(closed) == (status == "clear")
    assert context.last_proof is not None and context.last_proof[0] is closed
    assert context.last_proof[1] is report
    assert (scene.ledger.updates, scene.ledger.newton_steps, scene.ledger.roots) == (1, 1, 0)
    with pytest.raises(ValueError, match="closed proposal"):
        context.certify_stalled(scene.current)
    assert scene.gate.certify.call_count == 1
