"""
Check connector-focused ordering and negative-only evidence without saved layout inputs.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_terminal_hardware import hardware_contact_discovery as discovery
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from tests.test_ribbon_restoration_handoff import _contact, _source


def _observed() -> tuple[FoldRoute, Report]:
    """
    Supply real intersecting material and a mocked hardware report on its strictly occupied carrier.
    """
    route = _source()
    witness = _contact(route).witness
    assert witness is not None
    report = Report(
        "blocked",
        1,
        Witness("end", witness.pieces[0], witness.first, witness.point, (-0.1, 0.0, 0.0)),
    )
    return route, report


def _transform(route: FoldRoute, report: Report, scale: float) -> tuple[FoldRoute, Report]:
    """
    Apply one rigid quarter-turn/translation and uniform physical scale to an analytical model.
    """

    def direction(vector: Vector3) -> Vector3:
        """
        Rotate every frame with exact signed coordinate permutations.
        """
        return Vector3(-vector.y, vector.x, vector.z)

    def point(vector: Vector3) -> Vector3:
        """
        Transform physical points without introducing a preferred world direction.
        """
        return Vector3(-vector.y * scale + 7, vector.x * scale - 13, vector.z * scale + 5)

    pieces = []
    for piece in route.pieces:
        geometry = piece.geometry
        if isinstance(geometry, Straight):
            geometry = replace(geometry, material_length_mm=geometry.material_length_mm * scale)
        else:
            geometry = replace(
                geometry,
                radius_mm=geometry.radius_mm * scale,
                width_mm=geometry.width_mm * scale,
                before_mm=geometry.before_mm * scale,
                after_mm=geometry.after_mm * scale,
            )
        pose = Pose(
            point(piece.pose.origin), direction(piece.pose.tangent), direction(piece.pose.width)
        )
        pieces.append(PlacedPiece(pose, geometry, piece.label))
    target = replace(
        route.targets,
        start=point(route.targets.start),
        end=point(route.targets.end),
        start_tangent=direction(route.targets.start_tangent),
        end_tangent=direction(route.targets.end_tangent),
        start_width=direction(route.targets.start_width),
        end_width=direction(route.targets.end_width),
        diameter_mm=route.targets.diameter_mm * scale,
    )
    assert report.witness is not None
    return FoldRoute(target, tuple(pieces), route.radius_mm * scale), replace(
        report,
        witness=replace(report.witness, point=point(report.witness.point)),
    )


@pytest.mark.parametrize("scale", (0.1, 1.0, 20.0))
def test_focus_finds_actual_crossings_under_rigid_motion_and_scale(scale: float) -> None:
    """
    Every supplied witness must still pass both original inverses under transformed physical inputs.
    """
    original, report = _observed()
    route, report = _transform(original, report, scale)
    priority = discovery.focus(route, report, lambda: None)
    assert priority is not None and priority.source is route and report.witness is not None
    assert len(priority.priority) == len(set(priority.priority)) <= 32
    incident = {report.witness.piece - 1, report.witness.piece, report.witness.piece + 1}
    assert all(b >= a + 2 and (a in incident or b in incident) for a, b in priority.priority)
    context = discovery.HardwareContacts()
    found = context.inspect(route, report, 32, lambda: None)
    assert found is not None and found.status == "penetration" and found.witness is not None
    assert 0 < found.pairs_checked <= 32
    for member in found.witness.pieces:
        assert (
            occupied_coordinates(
                route.pieces[member],
                found.witness.point,
                route.targets.lines,
                route.targets.diameter_mm,
            )
            is not None
        )
    assert context.inspect(route, report, 32, lambda: None) is None


def test_misses_stale_points_and_capacity_never_supply_clearance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep one visit per exact route, four total owners and the supplied comparison ceiling.
    """
    route, report = _observed()
    assert report.witness is not None
    stale = replace(report, witness=replace(report.witness, point=Vector3(1e6, 1e6, 1e6)))
    assert discovery.focus(route, stale, Mock()) is None
    assert discovery.focus(route, Report("unresolved", 0), Mock()) is None
    query = Mock(return_value=ContactResult("unresolved", 3))
    monkeypatch.setitem(vars(discovery), "screen", query)
    context = discovery.HardwareContacts()
    assert context.inspect(route, report, 0, Mock()) is None
    for _ in range(4):
        current = replace(route)
        result = context.inspect(current, report, 3, Mock())
        assert result is not None and result.status == "unresolved"
        assert query.call_args.args[2] == 3
    assert context.inspect(replace(route), report, 3, Mock()) is None
    assert context.statistics()["completed_pairs"] == 12 and query.call_count == 4


def test_cancellation_and_invalid_negative_results_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A negative accelerator cannot swallow caller stops or masquerade as a full material proof.
    """
    route, report = _observed()
    with pytest.raises(TimeoutError, match="source stop"):
        discovery.HardwareContacts().inspect(
            route, report, 32, Mock(side_effect=TimeoutError("source stop"))
        )
    monkeypatch.setitem(vars(discovery), "screen", Mock(return_value=ContactResult("separated", 1)))
    with pytest.raises(ArithmeticError, match="cannot supply clearance"):
        discovery.HardwareContacts().inspect(route, report, 32, Mock())
