"""
Verify strict return evidence, complete-profile guidance and shared remaining feasibility work.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Literal
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.runner import restore
from experiments.experiment_ribbon_feature_insertion import depth_evidence
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_route.contact import ContactResult, ProbeResult
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware import (
    incident_recovery,
    return_contact,
    return_recovery,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_separation import (
    FlatSeparation,
    ProfileExtent,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from tests.test_ribbon_aesthetic import _route


@pytest.fixture(scope="module")
def routes() -> dict[str, FoldRoute]:
    """
    Load two dependent numerical snapshots from the documented case80 boundary.
    """
    raw = json.loads(
        Path(__file__).with_name("fixtures").joinpath("ribbon_return_contact.json").read_text()
    )
    return {key: restore(raw[key]) for key in ("depth_source", "reflected_source")}


def test_depth_ambiguity_can_yield_strict_crossing_evidence_without_moving_material(
    routes: dict[str, FoldRoute],
) -> None:
    """
    Find the actual nonlocal return and verify both original strict inverse maps.
    """
    source = routes["depth_source"]
    original = ContactResult("unresolved", 362, limit="depth")
    probe = FlatProbe()
    events: list[dict[str, Any]] = []
    actual = depth_evidence.screen(source, original, 1179, probe, lambda: None, events.append)
    assert actual.status == "penetration" and actual.witness is not None
    assert actual.witness.pieces == (0, 3)
    assert actual.pairs_checked == probe.comparisons == 5
    assert probe.supports <= 2048 and events[-1]["remaining_pairs"] == 1174
    for index in actual.witness.pieces:
        assert (
            occupied_coordinates(
                source.pieces[index],
                actual.witness.point,
                source.targets.lines,
                source.targets.diameter_mm,
            )
            is not None
        )
    assert original.status == "unresolved" and original.witness is None


@pytest.mark.parametrize("limit", (None, "supports"))
def test_negative_screen_miss_or_limit_keeps_the_original_incomplete_result(
    monkeypatch: pytest.MonkeyPatch, routes: dict[str, FoldRoute], limit: Literal["supports"] | None
) -> None:
    """
    Exhaust the supplied one-pair pool without granting clearance or starting fresh probe work.
    """

    def miss(
        probe: FlatProbe,
        route: FoldRoute,
        first: int,
        second: int,
        remaining_pairs: int,
        checkpoint: Callable[[], None] | None,
    ) -> ProbeResult:
        """
        Spend one accounted comparison and deliberately establish no crossing.
        """
        assert remaining_pairs == 1
        probe.comparisons += 1
        return ProbeResult(1, limit=limit)

    monkeypatch.setattr(FlatProbe, "__call__", miss)
    original = ContactResult("unresolved", 362, limit="depth")
    probe = FlatProbe()
    actual = depth_evidence.screen(
        routes["depth_source"], original, 1, probe, lambda: None, lambda e: None
    )
    assert actual is original and probe.comparisons == 1


def test_caller_cancellation_is_not_a_missed_contact_probe(routes: dict[str, FoldRoute]) -> None:
    """
    Preserve hard caller failures instead of converting them into an optional unresolved result.
    """
    checkpoint = Mock(side_effect=RuntimeError("source changed"))
    with pytest.raises(RuntimeError, match="source changed"):
        depth_evidence.screen(
            routes["depth_source"],
            ContactResult("unresolved", 1, limit="depth"),
            5,
            FlatProbe(),
            checkpoint,
            lambda e: None,
        )


def test_only_the_actual_nonadjacent_return_fold_is_reflected(
    monkeypatch: pytest.MonkeyPatch, routes: dict[str, FoldRoute]
) -> None:
    """
    Select material incidence without a case identity, terminal proxy fiction or sign candidate bank.
    """
    source = routes["depth_source"]
    witness = FlatProbe()(source, 0, 3, 64, None).witness
    assert witness is not None
    stopped = Recovery(None, None, 0, 0, 0, {"status": "unresolved", "iterations": 0})
    attempt = Mock(return_value=stopped)
    monkeypatch.setitem(vars(incident_recovery), "_recover_selected", attempt)
    options = dict(
        maximum_length_mm=222.54626858607466,
        minimum_straight_mm=1e-5,
        remaining_pairs=610,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1.0,
    )
    gate = Mock(spec=Gate)
    assert (
        incident_recovery.recover_return(
            source, witness, gate, lambda: None, lambda e: None, **options
        )
        is stopped
    )
    assert attempt.call_args.args[1] == 2
    assert (
        attempt.call_args.kwargs["completion"]
        is incident_recovery.ContactCompletion.REMAINING_JOINT
    )
    attempt.reset_mock()
    for pair in ((0, 1), (1, 3), (0, 0)):
        changed = replace(witness, pieces=pair)
        if pair == (0, 0):
            with pytest.raises(ValueError):
                incident_recovery.recover_return(
                    source, changed, gate, lambda: None, lambda e: None, **options
                )
        else:
            assert (
                incident_recovery.recover_return(
                    source, changed, gate, lambda: None, lambda e: None, **options
                )
                is None
            )
    attempt.assert_not_called()


def test_complete_profile_guidance_includes_neighboring_conductors(
    routes: dict[str, FoldRoute],
) -> None:
    """
    Enclose both complete straight profiles instead of repairing one conductor arc at a time.
    """
    source = routes["reflected_source"]
    hit = FlatProbe()(source, 0, 4, 64, None).witness
    assert hit is not None
    model = SignedJoints(source)
    arc = FlatSeparation.create(model, source, hit)
    full = FlatSeparation.create(model, source, hit, extent=ProfileExtent.COMPLETE)
    assert arc is not None and full is not None
    assert any(part.high_q - part.low_q < source.half_width_mm for part in arc.parts)
    assert all(
        (part.low_q, part.high_q) == (-source.half_width_mm, source.half_width_mm)
        for part in full.parts
    )
    assert full.gap(model.initial, Side.BEFORE) >= full.gap(model.initial, Side.AFTER)
    invalid: Any = True
    with pytest.raises(ValueError, match="profile extent"):
        FlatSeparation.create(model, source, hit, extent=invalid)


def test_end_terminal_incidence_is_selected_even_when_the_other_fold_is_piece_zero(
    monkeypatch: pytest.MonkeyPatch, routes: dict[str, FoldRoute]
) -> None:
    """
    Check selection symmetry on a recomposed chain; the mocked correction asserts no clearance.
    """
    original = routes["depth_source"]
    rebuilt = _route(tuple(piece.geometry for piece in reversed(original.pieces)))
    source = replace(
        rebuilt,
        targets=replace(
            rebuilt.targets, lines=original.targets.lines, diameter_mm=original.targets.diameter_mm
        ),
        radius_mm=original.radius_mm,
    )
    measured = FlatProbe()(original, 0, 3, 64, None).witness
    assert measured is not None
    witness = replace(measured, pieces=(0, len(source.pieces) - 1))
    stopped = Recovery(None, None, 0, 0, 0, {"status": "unresolved", "iterations": 0})
    attempt = Mock(return_value=stopped)
    monkeypatch.setitem(vars(incident_recovery), "_recover_selected", attempt)
    incident_recovery.recover_return(
        source,
        witness,
        Mock(spec=Gate),
        lambda: None,
        lambda e: None,
        maximum_length_mm=222.54626858607466,
        minimum_straight_mm=1e-5,
        remaining_pairs=610,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1,
    )
    assert attempt.call_args.args[1] == 0


def test_joint_continuation_deducts_probe_pairs_and_preparation_before_its_only_solver_call(
    monkeypatch: pytest.MonkeyPatch, routes: dict[str, FoldRoute]
) -> None:
    """
    Carry genuinely unused updates and reduced CPU/pairs through one simultaneous correction.
    """
    source = routes["reflected_source"]
    witness = FlatProbe()(source, 0, 4, 64, None).witness
    assert witness is not None

    def screen(
        route: FoldRoute,
        measurement: ContactResult,
        remaining_pairs: int,
        probe: FlatProbe,
        checkpoint: Callable[[], None],
        record: Callable[[dict[str, Any]], None],
    ) -> ContactResult:
        """
        Retain a measured preparation cost without invoking geometry motion.
        """
        probe.comparisons = 6
        return ContactResult("penetration", 6, witness=witness)

    clock = iter(i * 0.001 for i in range(100))
    monkeypatch.setitem(vars(return_contact), "process_time", lambda: next(clock))
    monkeypatch.setitem(vars(return_contact), "screen", screen)
    certificate = ContactResult("separated", 337)
    result = Result(
        source,
        certificate,
        dict(
            status="separated",
            iterations=1,
            newton_steps=4,
            contacts=1,
            contact_pairs=337,
            contact_seconds=0.04,
        ),
    )
    attempt = Mock(return_value=result)
    monkeypatch.setitem(vars(return_contact), "recover_joint", attempt)
    actual = return_contact.recover(
        source,
        ContactResult("unresolved", 437, limit="depth"),
        Mock(spec=Gate),
        lambda: None,
        lambda e: None,
        maximum_length_mm=222.54626858607466,
        minimum_straight_mm=1e-5,
        remaining_pairs=737,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1.0,
        maximum_updates=2,
    )
    assert actual.route is source and actual.contact is certificate
    assert actual.pairs == 343 and actual.detail["remaining_pair_budget"] == 394
    attempt.assert_called_once()
    assert attempt.call_args.args[1] is witness
    assert attempt.call_args.kwargs["remaining_pairs"] == 731
    assert attempt.call_args.kwargs["maximum_updates"] == 2
    assert 0 < attempt.call_args.kwargs["maximum_cpu_seconds"] < 0.2


@pytest.mark.parametrize(
    "field,value",
    (
        ("remaining_pairs", 0),
        ("remaining_pairs", 2049),
        ("maximum_cpu_seconds", 0.36),
        ("maximum_cpu_seconds", True),
        ("maximum_seconds", 2.1),
        ("maximum_length_mm", float("nan")),
    ),
)
@pytest.mark.parametrize("entry", ("return_recovery", "return_contact"))
def test_preparation_cannot_start_with_disabled_or_renewed_limits(
    routes: dict[str, FoldRoute],
    field: str,
    value: Any,
    entry: str,
) -> None:
    """
    Enforce the same limits before negative probing as before joint correction.
    """
    options: dict[str, Any] = dict(
        maximum_length_mm=222.54626858607466,
        minimum_straight_mm=1e-5,
        remaining_pairs=610,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1.0,
    )
    if entry == "return_contact":
        options["maximum_updates"] = 2
    options[field] = value
    with pytest.raises(ValueError):
        if entry == "return_contact":
            return_contact.recover(
                routes["depth_source"],
                ContactResult("unresolved", 1, limit="depth"),
                Mock(spec=Gate),
                lambda: None,
                lambda e: None,
                **options,
            )
        else:
            return_recovery.recover(
                routes["depth_source"],
                ContactResult("unresolved", 1, limit="depth"),
                Mock(spec=Gate),
                lambda: None,
                lambda e: None,
                **options,
            )
