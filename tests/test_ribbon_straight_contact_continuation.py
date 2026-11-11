"""
Retain one complete flat-contact inequality in the original hardware straight stage.
"""

from __future__ import annotations

from typing import Callable

import pytest

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import jacobian
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from experiments.experiment_ribbon_terminal_hardware.straight_projection import shortest_run_step
from tests.test_ribbon_contact_refinement import _source


@pytest.mark.parametrize("infeasible", (False, True))
def test_original_affine_domain_can_add_a_strict_row_without_new_bends_or_allowance(
    infeasible: bool,
) -> None:
    """
    Compensated runway growth can satisfy a new affine row; incompatible rows decline unchanged.

    This independently authored cap system exercises actual placement, Jacobian
    and projector. Its affine inequality is an analytical mechanism control,
    not a physical contact certificate or independent geometry coverage.
    """
    source = _source(0.0)
    model = StraightSlots(source)
    initial = model.initial
    target = initial[0] + 0.25 / model.scale

    def terms(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Keep fixed caps and a quarter-millimeter strict separating translation.
        """
        inequalities = (target - values[0],)
        if infeasible:
            inequalities += (values[0] - initial[0],)
        return model.residual(values) + inequalities

    equations: Callable[[tuple[float, ...]], tuple[float, ...]] = terms
    residual = equations(initial)
    rows = jacobian(
        model,
        initial,
        equations,
        len(residual),
        set(),
        lambda: None,
        admissible=model.admissible,
    )
    delta = shortest_run_step(model, initial, rows, residual, lambda: None)
    if infeasible:
        assert delta is None and model.initial == initial
        return
    assert delta is not None
    proposed = tuple(a + b for a, b in zip(initial, delta))
    route = model.route(proposed)
    assert route is not None and model.admissible(proposed)
    assert cap_error(route) < 1e-7 and max(terms(proposed)[6:]) <= 1e-12
    assert route.material_length_mm >= source.material_length_mm + 0.499999
    assert tuple(
        p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold)
    ) == tuple(p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold))
    assert route.targets is source.targets


@pytest.mark.parametrize(
    "outcome",
    (
        "default",
        "accept",
        "decline",
        "stale",
        "repeat",
        "capacity",
        "unresolved",
        "budget",
        "late",
        "cancel",
    ),
)
def test_real_joint_entry_retains_one_affine_flat_row_without_renewing_work(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    """
    Exercise actual placement and projection, mocking physical reports only to test protocol ordering.

    The synthetic row requires compensated growth after initial hardware motion.
    These checker-boundary dispositions do not establish real contact coverage;
    independent occupied-material controls exercise the actual preparation below.
    """
    from typing import Any, cast
    from unittest.mock import Mock

    from cable_bundler.routing.geometry import Vector3
    from experiments.experiment_ribbon_feature_insertion.separation import Region, Side
    from experiments.experiment_ribbon_fold_route.contact import ContactResult
    from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
    from experiments.experiment_ribbon_terminal_hardware import joint_contact
    from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
    from experiments.experiment_ribbon_terminal_hardware.contact_addition import Addition
    from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
        ContactGuidance,
        ContactMotion,
        FeatureEvidence,
    )
    from experiments.experiment_ribbon_terminal_hardware.flat_continuation import (
        ClosedFlatContinuation,
        ContactContinuation,
    )
    from experiments.experiment_ribbon_terminal_hardware.flat_separation import FlatPart
    from experiments.experiment_ribbon_terminal_hardware.joint_handoff import JointHandoff
    from experiments.experiment_ribbon_terminal_hardware.material_constraint import (
        MaterialConstraint,
    )
    from tests.test_ribbon_contact_refinement import _gate
    from tests.test_ribbon_material_return import _witness

    source = _source(0.0)
    terminal = _gate(source)
    report = Report("blocked", 1, Witness("start", 1, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0)))
    clock, cancelled = [0.0], [False]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(joint_contact), name, lambda: clock[0])

    def hardware(_planes: Any, model: Any, _values: Any) -> list[Any]:
        """
        Require initial real cap-compensated hardware motion before any synthetic crossing report.
        """
        plane = Mock()
        target = model.initial[0] + 0.1 / model.scale
        plane.gap.side_effect = lambda values: values[0] - target
        return [plane] * (13 if outcome == "capacity" else 1)

    monkeypatch.setitem(vars(joint_contact), "member_planes", hardware)
    monkeypatch.setitem(vars(joint_contact), "prepare_terminal_protection", lambda *_args: ())
    crossing = ContactResult("penetration", 4, _witness(0, 2))
    final = ContactResult("unresolved" if outcome == "unresolved" else "separated", 5)
    contact = Mock(side_effect=[crossing, crossing if outcome == "repeat" else final])
    monkeypatch.setitem(vars(joint_contact), "inspect_contact", contact)
    prepared: list[Any] = []

    def prepare(model: Any, route: Any, evidence: Any, values: Any) -> Any:
        """
        Bind one analytical full-profile row to the actual current cap-closed pose.
        """
        prepared.append(route)
        assert cap_error(route) < 1e-7 and evidence is crossing
        bound = Mock(spec=MaterialConstraint)
        bound.pair = (Region(0, True), Region(1, True))
        bound.parts = (FlatPart(FlatPhase.STRAIGHT, -0.5, 0.5, 0.5),) * 2
        target = values[0] + 0.25 / model.scale
        bound.gap.side_effect = (
            (lambda coordinates, side: model.initial[0] - coordinates[0])
            if outcome in ("decline", "late")
            else (lambda coordinates, side: coordinates[0] - target)
        )
        addition = Addition(
            cast(MaterialConstraint, bound), Side.AFTER, (bound.pair, bound.parts), crossing.witness
        )
        return ClosedFlatContinuation(values, JointHandoff(route, evidence), addition)

    monkeypatch.setattr(ClosedFlatContinuation, "prepare", staticmethod(prepare))
    original = joint_contact.shortest_run_step
    projects = [0]

    def project(*args: Any, **kwargs: Any) -> Any:
        """
        A partial real affine step then decline makes the original occupied point stale.
        """
        projects[0] += 1
        if outcome == "stale" and projects[0] == 3:
            return None
        delta = original(*args, **kwargs)
        return (
            tuple(value * 0.5 for value in delta)
            if outcome == "stale" and projects[0] == 2 and delta is not None
            else delta
        )

    monkeypatch.setitem(vars(joint_contact), "shortest_run_step", project)
    yielded: list[JointHandoff] = []

    def record(event: dict[str, Any]) -> None:
        """
        Keep preparation and recording overhead inside the same original guard.
        """
        if event["status"] == "straight_contact_retained":
            if outcome == "budget":
                clock[0] = 0.36
            cancelled[0] = outcome == "cancel"
        if event["status"] == "straight_contact_fallback_prepared" and outcome == "late":
            clock[0] = 0.36

    def checkpoint() -> None:
        """
        Preserve the caller's original source/cancellation exception.
        """
        if cancelled[0]:
            raise InterruptedError("original source guard")

    def run() -> Any:
        """
        Use only original work; no native geometry is attempted by this boundary control.
        """
        return joint_contact.recover(
            source,
            report,
            terminal,
            checkpoint,
            record,
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
            remaining_pairs=123,
            maximum_cpu_seconds=0.35,
            maximum_seconds=2,
            maximum_updates=4,
            mode=ContactGuidance(
                (FeatureEvidence(source, report),),
                ContactMotion.ADAPTIVE_HARDWARE,
                ContactContinuation.HANDOFF
                if outcome == "default"
                else ContactContinuation.FIRST_FLAT,
            ),
            on_blocked=yielded.append,
        )

    if outcome == "cancel":
        with pytest.raises(InterruptedError, match="source guard"):
            run()
        assert not yielded
        return
    result = run()
    assert result is not None and result.detail["contact_pairs"] <= 9
    if outcome == "accept":
        assert result.contact is final and not yielded and contact.call_count == 2
        assert result.route.material_length_mm > source.material_length_mm + 0.69
        assert cap_error(result.route) < 1e-7 and terminal.certify.call_count == 2
        assert [
            p.geometry for p in result.route.pieces if isinstance(p.geometry, CylindricalFold)
        ] == [p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold)]
    elif outcome in ("default", "decline", "repeat", "capacity"):
        assert result.contact is None and len(yielded) == 1
        assert result.detail["stop_reason"] == "material_handoff"
        assert result.detail["straight_contact_fallbacks"] == int(outcome == "decline")
        assert len(prepared) == int(outcome != "default")
        assert contact.call_count == (2 if outcome == "repeat" else 1)
        if outcome == "decline":
            assert yielded[0].route is prepared[0]
    else:
        assert result.contact is None and not yielded
        if outcome in ("budget", "late"):
            assert result.detail["stop_reason"] == "phase_budget"
        if outcome == "stale":
            assert result.detail["stop_reason"] == "linear_projection_infeasible"


@pytest.mark.parametrize("invalid", ("valid", "miss", "limit", "point", "pose"))
def test_actual_occupied_flat_regions_require_current_pose_and_both_inverse_maps(
    invalid: str,
) -> None:
    """
    Bind a real authored strict crossing to complete flat profiles, never uncertain or stale evidence.
    """
    from dataclasses import replace

    from cable_bundler.routing.geometry import Vector3
    from experiments.experiment_ribbon_terminal_hardware.flat_continuation import (
        ClosedFlatContinuation,
    )
    from tests.test_ribbon_aesthetic import _route
    from tests.test_ribbon_restoration_handoff import _contact
    from tests.test_ribbon_restoration_handoff import _source as crossing_source

    source = _route(tuple(piece.geometry for piece in crossing_source().pieces))
    model = StraightSlots(source)
    values = model.initial
    contact = _contact(source)
    assert contact.witness is not None
    if invalid == "miss":
        contact = replace(contact, status="unresolved")
    elif invalid == "limit":
        contact = replace(contact, limit="pairs")
    elif invalid == "point":
        contact = replace(contact, witness=replace(contact.witness, point=Vector3(999, 999, 999)))
    elif invalid == "pose":
        values = (values[0] + 0.001,) + values[1:]
    retained = ClosedFlatContinuation.prepare(model, source, contact, values)
    if invalid != "valid":
        assert retained is None
        return
    assert retained is not None and retained.state.evidence is contact
    assert len(retained.addition.bound.parts) == 2
    assert all(
        part.low_q == -source.half_width_mm and part.high_q == source.half_width_mm
        for part in retained.addition.bound.parts
    )
    assert retained.unchanged(values, source)
    assert not retained.unchanged((values[0] + 0.001,) + values[1:], source)
    assert not retained.unchanged(
        values, replace(source, targets=replace(source.targets, name="other"))
    )


def test_curved_preparation_and_nonadaptive_policy_do_not_enter_flat_retention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A supported whole-piece constraint is still not a complete-flat continuation or a new motion policy.
    """
    from typing import cast
    from unittest.mock import Mock

    from experiments.experiment_ribbon_feature_insertion.separation import Separation, Side
    from experiments.experiment_ribbon_terminal_hardware import flat_continuation
    from experiments.experiment_ribbon_terminal_hardware.contact_addition import Addition
    from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
        ContactGuidance,
        ContactMotion,
    )
    from experiments.experiment_ribbon_terminal_hardware.flat_continuation import (
        ClosedFlatContinuation,
        ContactContinuation,
    )
    from experiments.experiment_ribbon_terminal_hardware.material_constraint import (
        MaterialConstraint,
    )
    from tests.test_ribbon_aesthetic import _route
    from tests.test_ribbon_restoration_handoff import _contact
    from tests.test_ribbon_restoration_handoff import _source as crossing_source

    source = _route(tuple(piece.geometry for piece in crossing_source().pieces))
    model = StraightSlots(source)
    contact = _contact(source)
    curved = MaterialConstraint(cast(Separation, Mock(spec=Separation)))
    monkeypatch.setitem(
        vars(flat_continuation),
        "prepare_addition",
        Mock(return_value=Addition(curved, Side.BEFORE, (), contact.witness)),
    )
    assert ClosedFlatContinuation.prepare(model, source, contact, model.initial) is None
    with pytest.raises(ValueError, match="adaptive"):
        ContactGuidance((), ContactMotion.BEND_JOINTS, ContactContinuation.FIRST_FLAT)


def test_join_tagged_metadata_does_not_invent_strict_occupied_material() -> None:
    """
    A synthetic boundary report lacking strict interior occupancy never grants retained guidance.
    """
    from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
    from experiments.experiment_ribbon_fold_route.geometry import Straight
    from experiments.experiment_ribbon_fold_route.primitives import fold
    from experiments.experiment_ribbon_terminal_hardware.flat_continuation import (
        ClosedFlatContinuation,
    )
    from tests.test_ribbon_aesthetic import _route

    source = _route((fold(2, 1.2, 1, 0, 0), Straight(3)))
    model = StraightSlots(source)
    current = model.route(model.initial)
    assert current is not None
    source = current
    witness = Penetration((0, 1), (0.0, 0.0, 0.0), (0.5, 0.0, 0.0), source.targets.start)
    contact = ContactResult("penetration", 1, witness)
    assert ClosedFlatContinuation.prepare(model, source, contact, model.initial) is None
