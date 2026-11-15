"""
Retain full terminal protection while exposing the opposite flat's usable motion margin.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import cross, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_feature_insertion.separation import locate
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase, region
from experiments.experiment_ribbon_paired_return import allocation
from experiments.experiment_ribbon_paired_return.ledger import Ledger
from experiments.experiment_ribbon_paired_return.native_model import NativeJoints
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware, Terminal
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from experiments.experiment_ribbon_terminal_hardware.terminal_phase import MatingPhase
from experiments.experiment_ribbon_terminal_hardware.terminal_protection import Protection, prepare
from tests.test_ribbon_terminal_protection import _two_folds


@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
@pytest.mark.parametrize("sign", (-1.0, 1.0))
def test_both_terminal_phase_bounds_enclose_actual_full_width_and_thickness(
    scale: float, sign: float
) -> None:
    """
    Protect start-exit and end-entry material without allowing the fixed cap to hide their slack.
    """
    source = _two_folds(scale, sign, 0.0)
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    phases = [MatingPhase.create(guard) for guard in prepare(model, hardware, [], lambda: None)]
    phases = [phase for phase in phases if phase is not None]
    assert len(phases) == 2
    for phase in phases:
        plane = phase.protection.plane
        assert phase.part.phase is (
            FlatPhase.AFTER if plane.box.terminal is Terminal.START else FlatPhase.BEFORE
        )
        values = model.initial
        piece = locate(source, model.pieces(values), plane.reference)
        assert isinstance(piece.geometry, CylindricalFold)
        flat = region(piece, phase.part.phase, -source.half_width_mm, source.half_width_mm)
        axis = plane.separation_direction(values)
        box_high = max(dot(corner, axis) for corner in plane.corners)
        for distance, q in flat.polygon:
            material_q = max(-piece.geometry.width_mm / 2, min(piece.geometry.width_mm / 2, q))
            center, forward, width, _ = piece.surface(
                distance / piece.geometry.material_length_mm, material_q
            )
            normal = unit(cross(forward, width))
            for height in (-source.targets.diameter_mm / 2, source.targets.diameter_mm / 2):
                point = center.translated(normal, height)
                actual_gap = (dot(point, axis) - box_high) / model.scale
                assert phase.protection.minimum_gap - actual_gap <= phase(values) + 1e-10
        assert phase(values) < phase.protection.residual(values) - 1e-3
    assert model.original is source


@pytest.mark.parametrize("sign", (-1.0, 1.0))
def test_separate_mating_straights_keep_ordinary_full_fold_protection(sign: float) -> None:
    """
    Existing terminal runways remove the permanently touching fold support; do not add phase rows there.
    """
    source = _two_folds(1.0, sign, 2.0)
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    assert all(
        MatingPhase.create(guard) is None for guard in prepare(model, hardware, [], lambda: None)
    )


def test_paired_rows_retain_original_protections_and_add_both_phase_bounds() -> None:
    """
    Supplemental guidance cannot replace either whole-member row or change its original physical gap.
    """
    source = _two_folds(1.0, 1.0, 0.0)
    model = NativeJoints(source, 1e-5)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    rows = allocation.constraints(
        model,
        source,
        (),
        (),
        hardware,
        1e-5,
        Ledger(Work(1, 2048, 0.35, 2, 6), 0, lambda: None),
    )
    assert rows is not None and len(rows) == 6
    phases = [row for row in rows if isinstance(row, MatingPhase)]
    originals = [row for row in rows if isinstance(row, Protection)]
    assert len(phases) == 2
    assert all(phase.protection in originals for phase in phases)
    assert all(isinstance(owner, Protection) for owner in originals[:4])


def test_complete_phase_bundle_declines_at_physical_row_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Over-capacity preparation cannot silently drop original guards or supplemental phase identities.
    """
    source = _two_folds(1.0, 1.0, 0.0)
    model = NativeJoints(source, 1e-5)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    guard = prepare(model, hardware, [], lambda: None)[0]
    assert MatingPhase.create(guard) is not None
    monkeypatch.setitem(vars(allocation), "prepare", Mock(return_value=(guard,) * 7))
    assert (
        allocation.constraints(
            model,
            source,
            (),
            (),
            hardware,
            1e-5,
            Ledger(Work(1, 2048, 0.35, 2, 6), 0, lambda: None),
        )
        is None
    )
