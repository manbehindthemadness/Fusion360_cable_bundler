"""
Check continuous-angle factorization, exact dimensional closure and opt-in isolation.
"""

import math

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import ZERO, Pose, extend, pose_error
from experiments.experiment_ribbon_fold_route.lateral import halfturn_pair, lateral_pair
from experiments.experiment_ribbon_fold_route.orientation import orient
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold
from experiments.experiment_ribbon_fold_route.solver import (
    FoldStrategy,
    SelfContactError,
    connect,
    construct_candidate,
)
from tests.test_fold_route import CASES

START = Pose(ZERO, Vector3(1, 0, 0), Vector3(0, 1, 0))


@pytest.mark.parametrize(
    "angle,bank", [(73.0, 27.0), (-41.0, -13.0), (117.0, 63.0), (-178.0, 12.0), (0.1, -60.0)]
)
def test_arbitrary_single_fold_orientation_is_recovered(angle: float, bank: float) -> None:
    """
    Retain a non-grid crease/turn, including a crease beyond the old45degree axes.
    """
    original = fold(0.76, 4.8, math.radians(angle), math.radians(bank), 0.0)
    target = extend(START, (original,))
    pieces = orient(START, target, 0.76, 4.8, 0.0)
    actual = extend(START, pieces)
    assert max(pose_error(actual, Pose(actual.origin, target.tangent, target.width))) < 1e-9
    assert len(pieces) == 1
    assert pieces[0].angle_radians == pytest.approx(original.angle_radians, abs=1e-10)
    assert pieces[0].bank_radians == pytest.approx(original.bank_radians, abs=1e-10)


@pytest.mark.parametrize("roll", [-37.0, 37.0, 90.0, 180.0])
def test_longitudinal_roll_uses_three_regular_derived_bends(roll: float) -> None:
    """
    Avoid a forbidden longitudinal crease without adding180degree return bends.
    """
    angle = math.radians(roll)
    target = Pose(ZERO, START.tangent, Vector3(0, math.cos(angle), math.sin(angle)))
    pieces = orient(START, target, 0.76, 4.8, 0.0)
    actual = extend(START, pieces)
    assert max(pose_error(actual, Pose(actual.origin, target.tangent, target.width))) < 1e-9
    assert len(pieces) == 3
    assert all(abs(piece.angle_radians) <= math.pi / 2 + 1e-12 for piece in pieces)


@pytest.mark.parametrize("distance", [-20.0, -2.6, -0.2, 0.2, 2.6, 20.0])
@pytest.mark.parametrize("runway", [0.0, 0.8])
def test_variable_lateral_pair_closes_and_does_not_increase_local_material(
    distance: float,
    runway: float,
) -> None:
    """
    Keep exact displacement and improve or match the original pair's material cost.
    """
    radius = 0.75 / 0.996 * (1 + 1e-9)
    pieces = lateral_pair(distance, distance, radius, 4.8, runway)
    target = extend(START, pieces)
    assert target.origin.y == pytest.approx(distance, abs=1e-9)
    assert pose_error(target, Pose(target.origin, START.tangent, START.width))[1] < 1e-9
    assert math.copysign(1, target.origin.z) == -math.copysign(1, distance)
    baseline = halfturn_pair(distance, distance, radius, 4.8, runway)
    assert (
        sum(p.material_length_mm for p in pieces)
        <= sum(p.material_length_mm for p in baseline) + 1e-9
    )
    if abs(distance) < 1:
        bends = [p for p in pieces if isinstance(p, CylindricalFold)]
        assert all(abs(p.angle_radians) < math.pi - 0.05 for p in bends)


def test_continuous_mode_is_optional_and_retains_the_contact_gate() -> None:
    """
    Preserve the measured baseline while allowing the new geometry to be inspected.
    """
    baseline = connect(CASES[0])
    assert baseline.material_length_mm == pytest.approx(50.114071270778965, abs=1e-8)
    events = []
    candidate = connect(CASES[0], strategy=FoldStrategy.CONTINUOUS, record=events.append)
    assert len(events) == 2 and events[-1].report is not None
    assert events[-1].report.status == "separated"
    assert sum(isinstance(p.geometry, CylindricalFold) for p in candidate.pieces) == 6
    with pytest.raises(SelfContactError) as error:
        connect(CASES[4], strategy=FoldStrategy.CONTINUOUS)
    assert error.value.report is not None
    assert error.value.report.status == "unresolved"


def test_every_recorded_algebraic_branch_closes_the_original_targets() -> None:
    """
    Retain exact factorization branches rather than relying on route initializations.
    """
    records: list[tuple[tuple[Piece, ...], float]] = []

    def record(geometries: tuple[Piece, ...], material_length: float) -> None:
        """
        Preserve every root's complete ordered primitive sequence and material cost.
        """
        records.append((geometries, material_length))

    case = CASES[0]
    candidate = construct_candidate(case, strategy=FoldStrategy.CONTINUOUS, record_candidate=record)
    assert len(records) == 2
    start = Pose(case.start, case.start_tangent, case.start_width)
    target = Pose(case.end, case.end_tangent, case.end_width)
    for pieces, length in records:
        assert max(pose_error(extend(start, pieces), target)) < 1e-8
        assert length == pytest.approx(sum(p.material_length_mm for p in pieces))
    assert candidate.material_length_mm == min(length for _, length in records)
