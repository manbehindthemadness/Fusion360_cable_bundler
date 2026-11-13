"""
Check witnessed interval mobility without saved-layout solves or geometry acceptance claims.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import MaterialGuidance
from experiments.experiment_ribbon_terminal_hardware.incident_model import IncidentJoints
from experiments.experiment_ribbon_terminal_hardware.incident_window import (
    IncidentWindow,
    ReturnCoordinates,
)
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import Difference, jacobian
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate


def _source(count: int, scale: float, bank: float) -> tuple[FoldRoute, Penetration]:
    """
    Author closed material and mocked occupied identities with remote material at both ends.
    """
    pieces: list[Piece] = [Straight(3 * scale)]
    for index in range(count):
        pieces.extend(
            (
                fold(2 * scale, 1.2 * scale, (-1) ** index * 0.9, bank, scale),
                Straight((2 + index) * scale),
            )
        )
    source = _route(tuple(pieces))
    source = replace(source, targets=replace(source.targets, diameter_mm=scale), radius_mm=scale)
    geometry = cast(CylindricalFold, source.pieces[3].geometry)
    _, end = geometry.bend_interval(0)
    witness = Penetration(
        (3, 2 * (count - 2) + 1),
        ((1 + end) / 2, 0, 0),
        (0.5, 0, 0),
        Vector3(0, 0, 0),
    )
    return source, witness


@pytest.mark.parametrize("count", (4, 7, 10))
@pytest.mark.parametrize("scale", (0.01, 1.0, 100.0))
@pytest.mark.parametrize("bank", (-0.4, 0.0, 0.4))
def test_interval_preserves_remote_coordinates_and_has_no_event_count_cap(
    count: int, scale: float, bank: float
) -> None:
    """
    Keep every actual interval event and two boundary slots, with bit-exact remote coordinates.
    """
    source, witness = _source(count, scale, bank)
    model = IncidentWindow(source, 1, witness)
    assert model.window == (1, count - 2)
    assert model.indices == tuple(i for i in range(4, 4 * (count - 1) + 1) if i % 4 != 3)
    assert len(model.initial) == 3 * (count - 2) + 1
    assert len(model.straight_indices) == count - 1
    assert model.admissible(model.initial)
    baseline = model.full.initial
    expanded = model.expanded(model.initial)
    assert expanded == tuple(
        -value if index == 5 else value for index, value in enumerate(baseline)
    )
    values = list(model.initial)
    values[0] += 0.02
    values[2] += 0.01
    changed = tuple(values)
    assert model.admissible(changed)
    expanded = model.expanded(changed)
    for index, value in enumerate(expanded):
        if index not in model.indices:
            assert value == baseline[index]
    route = model.route(changed)
    assert route is not None and route.targets == source.targets and model.preserves(route)
    original = model.full.pieces(baseline)
    assert route.pieces[0].geometry == original[0].geometry
    assert route.pieces[1].geometry == original[1].geometry
    assert route.pieces[1].pose == original[1].pose
    assert route.pieces[-2].geometry == original[-2].geometry
    assert route.pieces[-1].geometry == original[-1].geometry


def test_terminal_straight_and_absent_boundary_slots_keep_ordered_interval_identity() -> None:
    """
    Include the straight's preceding event and retain an absent movable slot without new events.
    """
    source, witness = _source(5, 1, 0.2)
    pieces = tuple(piece.geometry for index, piece in enumerate(source.pieces) if index != 2)
    source = _route(pieces)
    geometry = cast(CylindricalFold, source.pieces[2].geometry)
    _, end = geometry.bend_interval(0)
    witness = replace(witness, pieces=(2, 7), first=((end + 1) / 2, 0, 0))
    model = IncidentWindow(source, 1, witness)
    assert model.window == (1, 3)
    assert model.initial[0] == 0.0 and model.indices[0] == 4
    assert model.indices[-1] == 16 and model.indices[-2] == 14
    assert model.admissible(model.initial)


def test_interval_derivatives_are_exact_columns_of_the_original_global_model() -> None:
    """
    Preserve actual endpoint equations and one-sided arithmetic while avoiding remote coordinate probes.
    """
    source, witness = _source(7, 1, -0.4)
    local = IncidentWindow(source, 1, witness)
    global_model = IncidentJoints(source, 1)
    assert local.residual(local.initial) == global_model.residual(global_model.initial)
    derivatives = []
    for model in (local, global_model):
        derivatives.append(
            jacobian(
                model,
                model.initial,
                model.residual,
                6,
                frozenset(),
                lambda: None,
                admissible=model.admissible,
                difference=Difference.ONE_SIDED,
            )
        )
    columns = [global_model.indices.index(index) for index in local.indices]
    assert derivatives[0] == [[row[index] for index in columns] for row in derivatives[1]]


@pytest.mark.parametrize("invalid", ("open", "before", "other_fold", "policy"))
def test_unsupported_interval_does_not_silently_widen(invalid: str) -> None:
    """
    Reject unsupported selection or untyped mobility before a correction can run.
    """
    source, witness = _source(4, 1, 0.2)
    selected = 1
    if invalid == "open":
        source = replace(source, targets=replace(source.targets, end=Vector3(99, 99, 99)))
    elif invalid == "before":
        witness = replace(witness, first=(0, 0, 0))
    elif invalid == "other_fold":
        selected = 2
    else:
        policy: object = "witnessed_interval"
        with pytest.raises(ValueError, match="return coordinates"):
            MaterialGuidance(1, coordinates=cast(ReturnCoordinates, policy))
        return
    with pytest.raises(ValueError, match="reversal"):
        IncidentWindow(source, selected, witness)


@pytest.mark.parametrize("coordinates", tuple(ReturnCoordinates))
def test_joint_entry_keeps_original_physical_equations_and_one_optimizer(
    monkeypatch: pytest.MonkeyPatch, coordinates: ReturnCoordinates
) -> None:
    """
    Exercise the actual joint entry and derivative dispatch, stopping at its one projection boundary.
    """
    source, witness = _source(5, 1, 0.2)
    models: list[IncidentJoints] = []

    def projection(model: IncidentJoints, *args: Any, **kwargs: Any) -> None:
        """
        Observe supported coordinates without proposing or accepting geometry.
        """
        del args, kwargs
        models.append(model)

    project = Mock(side_effect=projection)
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", project)
    result = joint_contact.recover(
        source,
        witness,
        _gate(source),
        lambda: None,
        lambda event: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
        mode=MaterialGuidance(1, coordinates=coordinates),
    )
    assert result is not None and result.route is source and result.contact is None
    project.assert_called_once()
    assert isinstance(models[0], IncidentWindow) == (
        coordinates is ReturnCoordinates.WITNESSED_INTERVAL
    )
    assert result.detail["flat_constraints"] == 1
    assert result.detail["terminal_protection_constraints"] > 0
    assert result.detail["contact_pairs"] == 0 and result.detail["newton_steps"] == 0
    assert result.detail["return_coordinates"] == coordinates.value
