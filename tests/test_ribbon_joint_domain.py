"""
Reject invalid joint proposals before geometry placement without weakening exact material bounds.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import run_translation
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.incident_model import IncidentJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.radius_model import RadiusJoints
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from tests.test_ribbon_aesthetic import _route


@pytest.fixture
def source() -> FoldRoute:
    """
    Author asymmetric folds and internal runway without a saved layout or solver seed.
    """
    return _route(
        (
            Straight(3),
            fold(2, 1.2, 1.1, 0.2, 0),
            Straight(4),
            fold(3, 1.2, -0.9, -0.3, 0),
            Straight(5),
        )
    )


@pytest.fixture(params=("signed", "incident", "radius", "straight"))
def model(request: pytest.FixtureRequest, source: FoldRoute) -> SignedJoints:
    """
    Cover every policy sharing the domain predicate, including reduced straight-only coordinates.
    """
    if request.param == "incident":
        return IncidentJoints(source, 1)
    if request.param == "radius":
        return RadiusJoints(source, 1)
    if request.param == "straight":
        return StraightSlots(source)
    return SignedJoints(source)


@pytest.mark.parametrize("value", (-math.ulp(0.0), -1e-16, math.nan, math.inf))
def test_invalid_runway_returns_false_before_placement(
    model: SignedJoints,
    value: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reject even a one-float negative runway; neither geometry placement nor snapping is allowed.
    """
    invalid = list(model.initial)
    invalid[model.straight_indices[0]] = value
    placement = Mock(side_effect=AssertionError("Do not place an invalid proposal"))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_fold_relaxation.model.Model.route", placement
    )
    assert not model.admissible(tuple(invalid))
    placement.assert_not_called()


def test_vector_size_and_specialized_bounds_are_checked_before_expansion(
    model: SignedJoints,
) -> None:
    """
    Reduced models must not silently ignore extra coordinates or restore missing ones from the source.
    """
    assert not model.admissible(model.initial[:-1])
    assert not model.admissible(model.initial + (0.0,))
    for index in range(len(model.initial)):
        low, high = model.bounds(index)
        for invalid in (math.nextafter(low, -math.inf), math.nextafter(high, math.inf)):
            values = list(model.initial)
            values[index] = invalid
            assert not model.admissible(tuple(values))
    assert model.admissible(model.initial)


def test_valid_domain_does_not_hide_placement_errors(
    model: SignedJoints,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Valid-input implementation failures still propagate instead of becoming an unresolved proposal.
    """
    monkeypatch.setattr(
        "experiments.experiment_ribbon_fold_relaxation.model.Model.route",
        Mock(side_effect=RuntimeError("placement failure")),
    )
    with pytest.raises(RuntimeError, match="placement failure"):
        model.admissible(model.initial)


def test_translation_declines_an_out_of_bounds_projection_without_aborting(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exercise real feature equations and derivatives with an invalid vector from the mocked projector.
    """
    model = StraightSlots(source)
    delta = tuple(-value - 1e-12 if i == 0 else 0.0 for i, value in enumerate(model.initial))
    projection = Mock(return_value=delta)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.run_translation.shortest_run_step",
        projection,
    )
    evidence = Report("blocked", 1, Witness("end", 2, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0)))
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    assert run_translation.translate(source, evidence, hardware, lambda: None) is None
    projection.assert_called_once()
