"""
Distinguish accepted route closure from the stricter precondition of analytic terminal mating.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_terminal_hardware.check import inspect, mating_frame
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("diameter", (0.75, 1.0, 10.0))
def test_route_closure_can_pass_while_analytic_mating_is_ineligible(diameter: float) -> None:
    """
    Independently authored fixed targets expose the proof gap without relaxing any geometry check.

    Two analytical straight geometries share exactly the same declared targets.
    The displaced endpoint lies inside ordinary route closure but outside mating
    accuracy. Neither this comparison nor the exact control runs a repair or
    gives fresh-layout/native geometry coverage.
    """
    length = 10 * diameter
    authored = _route((Straight(length),))
    targets = replace(authored.targets, diameter_mm=diameter)
    exact = FoldRoute(targets, authored.pieces, diameter)
    displaced = FoldRoute(
        targets,
        (
            PlacedPiece(
                authored.pieces[0].pose, Straight(length + 6e-10), "authored precision control"
            ),
        ),
        diameter,
    )
    hardware = Hardware.create(targets, Dimensions.scaled(targets))
    end = hardware.boxes[1]
    assert 1e-10 < cap_error(displaced) < 1e-7
    assert not mating_frame(displaced, end)
    assert inspect(displaced, hardware, maximum_cells=64).status == "unresolved"
    assert exact.targets is displaced.targets and cap_error(exact) == 0
    assert mating_frame(exact, end)
    report = inspect(exact, hardware, maximum_cells=64)
    assert report.status == "clear" and report.cells_checked == 2


@pytest.mark.parametrize("offset", (0.0, 5e-11, 1e-10, 2e-10))
def test_shared_mating_predicate_preserves_original_finite_frame_criterion(offset: float) -> None:
    """
    Extract the same strict actual-pose decision, including its unchanged equality boundary.
    """
    from cable_bundler.routing.geometry import Vector3
    from experiments.experiment_ribbon_fold_route.geometry import Pose, pose_error
    from experiments.experiment_ribbon_fold_route.mating import matching_frame

    expected = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    actual = Pose(Vector3(offset, 0, 0), expected.tangent, expected.width)
    assert matching_frame(actual, expected) is (max(pose_error(actual, expected)) < 1e-10)


@pytest.mark.parametrize("invalid", (float("nan"), float("inf")))
def test_nonfinite_pose_cannot_be_an_analytic_mating_certificate(invalid: float) -> None:
    """
    A nonfinite error must not disappear inside a maximum reduction and authorize positive support.
    """
    from cable_bundler.routing.geometry import Vector3
    from experiments.experiment_ribbon_fold_route.geometry import Pose
    from experiments.experiment_ribbon_fold_route.mating import matching_frame

    expected = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    actual = Pose(Vector3(invalid, 0, 0), expected.tangent, expected.width)
    assert not matching_frame(actual, expected)
