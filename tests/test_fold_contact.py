"""
Challenge thick-volume contact decisions, including adjacency and near-clearance.
"""

import math

import pytest

from cable_bundler.routing.geometry import Vector3, cross, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.contact_inverse import (
    occupied_coordinates,
    profile_height,
)
from experiments.experiment_ribbon_fold_route.contact_solve import resolve_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.solver import (
    SelfContactError,
    connect,
    construct_candidate,
)
from tests.test_fold_route import CASES

X, Y, Z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)


def _route(first: PlacedPiece, second: PlacedPiece) -> FoldRoute:
    """
    Assemble an intentionally diagnostic pair without claiming cap connectivity.
    """
    return FoldRoute(CASES[1], (first, second), 0.75 / 0.996 * (1 + 1e-9))


@pytest.mark.parametrize(
    "gap,status", [(1.51, "separated"), (0.9, "penetration"), (0.0, "penetration")]
)
def test_full_thickness_is_checked_when_centerlines_do_not_cross(gap: float, status: str) -> None:
    """
    Reject overlapping parallel profiles rather than inspecting only guide crossings.
    """
    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), Straight(10), "first")
    second = PlacedPiece(Pose(Vector3(0, 0, gap), X, Y), Straight(10), "second")
    result = inspect_contact(_route(first, second))
    assert result.status == status
    if status == "penetration":
        assert result.witness is not None
        for piece in (first, second):
            coordinates = occupied_coordinates(piece, result.witness.point, 3, 1.5)
            assert coordinates is not None


def test_actual_width_not_just_centerline_clearance() -> None:
    """
    Find intersection near a ribbon edge even with centerline separation>D.
    """
    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), Straight(10), "first")
    second = PlacedPiece(Pose(Vector3(0, 3, 0), X, Y), Straight(10), "second")
    assert inspect_contact(_route(first, second)).status == "penetration"


def test_adjacent_straights_share_a_cap_without_being_exempted_wholesale() -> None:
    """
    Admit a normal shared cap while detecting a closed two-half-turn self-return.
    """
    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), Straight(5), "first")
    second = PlacedPiece(first.end_pose(), Straight(5), "second")
    assert inspect_contact(_route(first, second)).status == "separated"
    fold = CylindricalFold(0.75 / 0.996, math.pi, 0.0, 4.8, 0.0, 0.0)
    a = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), fold, "first half")
    b = PlacedPiece(a.end_pose(), fold, "second half")
    # The two halves only meet at their common cap and end caps; strict separation
    # cannot be claimed for this closed volume even without an interior witness.
    assert inspect_contact(_route(a, b), maximum_pairs=1000).status != "separated"


def test_no_clearance_claim_when_budget_is_exhausted() -> None:
    """
    Keep ambiguous contact unresolved rather than treating missing witnesses as safe.
    """
    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), Straight(10), "first")
    second = PlacedPiece(Pose(Vector3(0, 0, 1.5), X, Y), Straight(10), "touch")
    result = inspect_contact(_route(first, second), maximum_pairs=1)
    assert result.status == "unresolved"


@pytest.mark.parametrize(
    "bank,angle", [(0.0, math.pi), (math.pi / 4, math.pi / 2), (-math.pi / 4, -math.pi)]
)
def test_analytic_bounds_contain_actual_thick_fold_points(bank: float, angle: float) -> None:
    """
    Independently sample a placed material cell against every projected enclosure.
    """
    half = 2.4
    lead = half * abs(math.tan(bank))
    fold = CylindricalFold(0.76, angle, bank, 4.8, lead, lead)
    pose = Pose(Vector3(10, -4, 7), Y, Z)
    piece = PlacedPiece(pose, fold, "placed fold")
    cell = Cell(0, Span(0.11, 0.83), Span(-1.7, 2.0), Span(-0.75, 0.75))
    axes = (X, Y, Z, unit(Vector3(1, 2, -3)))
    for axis in axes:
        bound = projection(piece, cell, axis)
        for u in (0.11, 0.25, 0.5, 0.83):
            for q in (-1.7, 0.1, 2.0):
                p, v, w, _ = piece.surface(u, q)
                for b in (-0.75, 0.0, 0.75):
                    point = p.translated(unit(cross(v, w)), b)
                    value = point.x * axis.x + point.y * axis.y + point.z * axis.z
                    assert bound.low <= value <= bound.high
                    if b == 0:
                        inverse = occupied_coordinates(piece, point, 3, 1.5)
                        assert inverse is not None
                        assert inverse == pytest.approx((u, q, b), abs=1e-10)


def test_joined_profile_uses_original_lobe_and_cap_dimensions() -> None:
    """
    Preserve peak, valley and outer side-cap geometry for strict witnesses.
    """
    assert profile_height(0, 3, 1.5) == pytest.approx(0.75)
    assert profile_height(0.75, 3, 1.5) == pytest.approx(0.45)
    assert profile_height(2.25, 3, 1.5) == pytest.approx(0.45)
    assert profile_height(2.4, 3, 1.5) == pytest.approx(0.0, abs=1e-7)
    assert profile_height(2.5, 3, 1.5) == 0


def test_public_connection_constructs_the_gym_without_the_inward_fold() -> None:
    """
    Clear the same gym through outward construction without contact repair trials.
    """
    events = []
    route = connect(CASES[0], record=events.append)
    assert route.material_length_mm < 58.11
    assert len(events) == 2
    assert events[-1].report is not None
    assert events[-1].report.status == "separated"


def test_opt_in_runway_attempts_are_retained_when_they_fail() -> None:
    """
    Retain every attempted material change without converting exhaustion to a pass.
    """
    events = []
    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), Straight(10), "first")

    def build(runway: float) -> FoldRoute:
        """
        Retain visibly distinct but still penetrating candidates in a failed repair.
        """
        second = PlacedPiece(Pose(Vector3(0, 0, 0.5 + 0.01 * runway), X, Y), Straight(10), "second")
        return _route(first, second)

    with pytest.raises(SelfContactError) as error:
        resolve_contact(
            build,
            1.0,
            maximum_corrections=1,
            maximum_pairs=1000,
            maximum_depth=36,
            checkpoint=None,
            record=events.append,
        )
    assert len(error.value.history) == 2
    assert [event.report is not None for event in events] == [False, True, False, True]
    assert all(
        trial.report is not None and trial.report.status != "separated"
        for trial in error.value.history
    )


def test_public_connection_keeps_clear_controls() -> None:
    """
    Preserve the straight and planar control routes under the mandatory contact gate.
    """
    assert connect(CASES[1]).material_length_mm == pytest.approx(60.0)
    assert connect(CASES[2]).material_length_mm == pytest.approx(39.676804462624766)


def test_runway_deformation_preserves_caps_and_common_material_length() -> None:
    """
    Change real fold separation while retaining all ordered endpoint material paths.
    """
    case = CASES[0]
    original = construct_candidate(case)
    changed = construct_candidate(case, runway_mm=6.3)
    assert changed.material_length_mm > original.material_length_mm
    assert changed.radius_mm == original.radius_mm
    for u, p, t, w in (
        (0.0, case.start, case.start_tangent, case.start_width),
        (1.0, case.end, case.end_tangent, case.end_width),
    ):
        for q in (-changed.half_width_mm, 0.0, changed.half_width_mm):
            point, velocity, across, _ = changed.surface(u, q)
            assert (point.x, point.y, point.z) == pytest.approx(
                (p.x + q * w.x, p.y + q * w.y, p.z + q * w.z), abs=1e-9
            )
            assert (unit(velocity).x, unit(velocity).y, unit(velocity).z) == pytest.approx(
                (t.x, t.y, t.z), abs=1e-9
            )
            assert (across.x, across.y, across.z) == pytest.approx((w.x, w.y, w.z), abs=1e-9)
