"""
Verify finite feature grouping, fixed turn directions and route-bound fold-recovery dispatch.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Literal
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_feature_insertion.separation import Region, regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import fold_recovery, recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.straight_quality import StraightQuality
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("runway", (False, True))
def test_fold_group_contains_only_existing_terminalward_runway(runway: bool) -> None:
    """
    Do not turn an absent slot's synthetic analysis slab into an extra feature constraint.
    """
    source = _route(
        (
            fold(2, 1.2, 1, 0.2, 0),
            *((Straight(2),) if runway else ()),
            fold(3, 1.2, -1, -0.3, 0),
            Straight(4),
        )
    )
    index = 2 if runway else 1
    witness = Witness("start", index, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0))
    model = SignedJoints(source)
    plane = FeaturePlane.create(
        model,
        source,
        Report("blocked", 1, witness),
        Hardware.create(source.targets, Dimensions.scaled(source.targets)),
        model.initial,
    )
    assert plane is not None
    assert len(plane.members) == (2 if runway else 1)
    assert plane.members[0] == regions(source)[index]


def test_straight_group_keeps_away_fold_and_bounded_pose_cache_is_model_owned() -> None:
    """
    Include the previously missed neighboring fold without adding the separate mating fold.
    """
    source = _route((fold(2, 1.2, 1, 0.2, 0), Straight(2), fold(3, 1.2, -1, -0.3, 0), Straight(4)))
    model = SignedJoints(source)
    witness = Witness("end", 1, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0))
    plane = FeaturePlane.create(
        model,
        source,
        Report("blocked", 1, witness),
        Hardware.create(source.targets, Dimensions.scaled(source.targets)),
        model.initial,
    )
    assert plane is not None and plane.members == (regions(source)[1], regions(source)[0])
    assert model.pieces(model.initial) is model.pieces(model.initial)
    assert model.preserves(source)
    for i, full in enumerate(model.indices):
        if full % 4 == 1:
            assert model.bounds(i)[0] == 0 if model.initial[i] > 0 else model.bounds(i)[1] == 0


def test_actual_fold_witness_dispatches_with_only_remaining_caller_allowance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Actual fold intrusion selects early reflection using only the caller's remaining work.
    """
    source = _route((fold(2, 1.2, 1, 0.2, 0), Straight(3)))
    evidence = Report("blocked", 1, Witness("start", 0, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0)))
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = evidence
    answer = Result(source, None, {})
    direct = Mock(return_value=answer)
    monkeypatch.setitem(vars(recovery), "reverse_terminal_fold", direct)
    result = recovery.recover(
        source,
        terminal,
        lambda: None,
        lambda e: None,
        maximum_length_mm=20,
        minimum_straight_mm=1e-5,
        remaining_pairs=700,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1,
    )
    assert result is answer
    assert direct.call_args.args[1] is evidence
    assert 0 < direct.call_args.kwargs["maximum_cpu_seconds"] <= 0.2
    assert direct.call_args.kwargs["remaining_pairs"] == 700


@pytest.mark.parametrize("contact_status", ("separated", "penetrating"))
def test_native_slot_cleanup_recloses_caps_before_hardware_and_contact_certificates(
    monkeypatch: pytest.MonkeyPatch, contact_status: str
) -> None:
    """
    Neither physical certificate should spend work on a runway that cannot be built natively.
    """
    source = _route(
        (
            Straight(3),
            fold(2, 1.2, 1, 0.2, 0),
            Straight(5e-7),
            fold(3, 1.2, -1, -0.3, 0),
            Straight(4),
        )
    )
    model = SignedJoints(source)
    plane = SimpleNamespace(gap=lambda values: 1e-7 / model.scale)
    monkeypatch.setattr(FeaturePlane, "create", Mock(return_value=plane))
    terminal = Mock(spec=Gate)
    terminal.hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))

    def qualified(candidate: FoldRoute) -> None:
        """
        Require closed, ordered, native-sized geometry at both physical certificate boundaries.
        """
        assert candidate.targets == source.targets
        assert cap_error(candidate) < 1e-7
        assert model.preserves(candidate)
        assert all(
            p.geometry.material_length_mm > 1e-5
            for p in candidate.pieces
            if isinstance(p.geometry, Straight)
        )

    def hardware_certificate(candidate: FoldRoute, stage: str) -> Report:
        """
        Inspect the actual route before allowing terminal clearance to pass.
        """
        qualified(candidate)
        assert stage == "coupled_feature_candidate"
        return Report("clear", 1)

    terminal.certify.side_effect = hardware_certificate

    def certificate(candidate: FoldRoute, **options: object) -> ContactResult:
        """
        Preserve the independent final self-contact measurement after hardware certification.
        """
        qualified(candidate)
        assert options["maximum_pairs"] == 700
        return ContactResult(contact_status, 1)

    contact = Mock(side_effect=certificate)
    monkeypatch.setitem(vars(fold_recovery), "inspect_contact", contact)
    evidence = Report("blocked", 1, Witness("start", 1, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0)))
    result = fold_recovery.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm + 1,
        minimum_straight_mm=1e-5,
        remaining_pairs=700,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
    )
    assert result is not None
    terminal.certify.assert_called_once()
    contact.assert_called_once()
    assert result.detail["contacts"] == 1
    if contact_status == "separated":
        assert result.detail["status"] == "separated" and result.route is not source
    else:
        assert result.route is source and result.contact is None


@pytest.mark.parametrize(
    "hardware_status,contact_status,accepted",
    (
        ("clear", "separated", True),
        ("clear", "penetrating", False),
        ("unresolved", "separated", False),
    ),
)
def test_stalled_length_quality_can_yield_but_physical_certificates_remain_mandatory(
    monkeypatch: pytest.MonkeyPatch,
    hardware_status: Literal["clear", "unresolved"],
    contact_status: Literal["separated", "penetrating"],
    accepted: bool,
) -> None:
    """
    Allow a longer closed route after a failed quality projection without bypassing hardware or contact.
    """
    source = _route((Straight(3), fold(2, 1.2, 1, 0.2, 0), Straight(4)))
    model = SignedJoints(source)
    plane = SimpleNamespace(gap=lambda values: 1e-7 / model.scale)
    monkeypatch.setattr(FeaturePlane, "create", Mock(side_effect=(plane, None)))
    monkeypatch.setitem(vars(fold_recovery), "projected", Mock(return_value=None))
    contact = Mock(return_value=ContactResult(contact_status, 1))
    monkeypatch.setitem(vars(fold_recovery), "inspect_contact", contact)
    terminal = Mock(spec=Gate)
    terminal.hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    terminal.certify.return_value = Report(hardware_status, 1)
    events: list[dict[str, Any]] = []
    ceiling = source.material_length_mm - 0.1
    result = fold_recovery.recover(
        source,
        Report("blocked", 1),
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=ceiling,
        minimum_straight_mm=1e-5,
        remaining_pairs=700,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        quality=StraightQuality(ceiling, 1),
        maximum_updates=1,
    )
    assert result is not None and (result.contact is not None) is accepted
    releases = [event for event in events if event["status"] == "length_released"]
    assert len(releases) == 1 and releases[0]["remaining_newton"] == 6
    assert result.detail["length_ceiling_released"]
    assert result.detail["iterations"] <= 1 and result.detail["newton_steps"] <= 6
    terminal.certify.assert_called_once()
    assert contact.call_count == int(hardware_status == "clear")
    if accepted:
        assert result.route.targets == source.targets
        assert cap_error(result.route) < 1e-7 and model.preserves(result.route)
        assert result.detail["length_goal_excess_mm"] == pytest.approx(0.1)
    else:
        assert result.route is source


@pytest.mark.parametrize("terminal,index", (("start", 1), ("end", 3)))
def test_fold_correction_does_not_demand_positive_gap_from_its_attached_mating_runway(
    terminal: str, index: int
) -> None:
    """
    Preserve the witnessed fold while leaving its intentionally attached cap straight to final certification.
    """
    source = _route(
        (Straight(3), fold(2, 1.2, 1, 0.2, 0), Straight(2), fold(2, 1.2, -1, -0.3, 0), Straight(4))
    )
    model = SignedJoints(source)
    witness = Witness(terminal, index, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0))
    plane = FeaturePlane.create(
        model,
        source,
        Report("blocked", 1, witness),
        Hardware.create(source.targets, Dimensions.scaled(source.targets)),
        model.initial,
    )
    assert plane is not None and plane.members == (regions(source)[index],)
    assert len(source.pieces) == 5 and model.original is source


@pytest.mark.parametrize("terminal,index,slot", (("start", 0, 0), ("end", 4, 2)))
def test_an_actual_witnessed_terminal_straight_is_never_discarded(
    terminal: str, index: int, slot: int
) -> None:
    """
    An explicit intrusion report remains authoritative even for the special mating slot.
    """
    source = _route(
        (Straight(3), fold(2, 1.2, 1, 0.2, 0), Straight(2), fold(2, 1.2, -1, -0.3, 0), Straight(4))
    )
    model = SignedJoints(source)
    witness = Witness(terminal, index, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0))
    plane = FeaturePlane.create(
        model,
        source,
        Report("blocked", 1, witness),
        Hardware.create(source.targets, Dimensions.scaled(source.targets)),
        model.initial,
    )
    assert plane is not None and plane.reference == Region(slot, True)
    assert plane.reference in plane.members


@pytest.mark.parametrize("family", range(15))
def test_selected_feature_axis_matches_the_complete_sat_family_exactly(family: int) -> None:
    """
    Omit unused directions without changing box, local or cross-family axis arithmetic.
    """
    source = _route((Straight(2), fold(2, 1.2, 1, 0.2, 0), Straight(3)))
    model = SignedJoints(source)
    witness = Witness("end", 1, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0))
    plane = FeaturePlane.create(
        model,
        source,
        Report("blocked", 1, witness),
        Hardware.create(source.targets, Dimensions.scaled(source.targets)),
        model.initial,
    )
    assert plane is not None
    selected = FeaturePlane(model, plane.reference, plane.members, plane.box, family, plane.side)
    piece = source.pieces[1]
    assert selected._selected_axis(piece) == selected._axes(piece)[family]
