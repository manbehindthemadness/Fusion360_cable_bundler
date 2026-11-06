"""
Verify finite feature grouping, fixed turn directions and route-bound fold-recovery dispatch.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_feature_insertion.separation import regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import fold_recovery, recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
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
    Fold clearance gets measured direct constraints instead of an unconditional reflection.
    """
    source = _route((fold(2, 1.2, 1, 0.2, 0), Straight(3)))
    evidence = Report("blocked", 1, Witness("start", 0, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0)))
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = evidence
    answer = Result(source, None, {})
    direct = Mock(return_value=answer)
    monkeypatch.setitem(vars(recovery), "recover_fold", direct)
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
def test_native_slot_cleanup_recloses_caps_before_the_required_contact_certificate(
    monkeypatch: pytest.MonkeyPatch, contact_status: str
) -> None:
    """
    Zeroing a sub-native runway must retain exact caps and cannot bypass strict final contact.
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
    terminal.measure.return_value = Report("clear", 1)

    def certificate(candidate: FoldRoute, **options: object) -> ContactResult:
        """
        Inspect the actual post-cleanup geometry at the physical acceptance boundary.
        """
        assert candidate.targets == source.targets
        assert cap_error(candidate) < 1e-7
        assert model.preserves(candidate)
        assert all(
            p.geometry.material_length_mm > 1e-5
            for p in candidate.pieces
            if isinstance(p.geometry, Straight)
        )
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
    contact.assert_called_once()
    assert result.detail["contacts"] == 1
    if contact_status == "separated":
        assert result.detail["status"] == "separated" and result.route is not source
    else:
        assert result.route is source and result.contact is None
