"""
Author independent occupied hardware members for adaptive scheduling protocol controls.
"""

from __future__ import annotations

import math
from dataclasses import replace

from cable_bundler.routing.geometry import cross, difference, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route


def _turn(angle: float) -> CylindricalFold:
    """
    Retain one authored radius/profile across planar material turns.
    """
    return CylindricalFold(1, angle, 0, 1.2, 0, 0)


def _report(route: FoldRoute, hardware: Hardware, member: int, offset: float) -> Report:
    """
    Construct and independently verify a point strictly occupied by one straight and the end proxy.
    """
    piece = route.pieces[member]
    u = (route.targets.end.x + offset - piece.pose.origin.x) / (
        piece.end_pose().origin.x - piece.pose.origin.x
    )
    assert 0 < u < 1
    point, forward, across, _ = piece.surface(u, 0)
    point = point.translated(unit(cross(forward, across)), 0.4)
    material = occupied_coordinates(piece, point, route.targets.lines, route.targets.diameter_mm)
    assert material is not None
    box = hardware.boxes[1]
    displacement = difference(point, box.pose.origin)
    coordinates = (
        dot(displacement, box.axes[0]),
        dot(displacement, box.axes[1]),
        dot(displacement, box.axes[2]),
    )
    assert all(span.low < value < span.high for span, value in zip(box.bounds, coordinates))
    return Report("blocked", 1, Witness("end", member, material, point, coordinates))


def adjacent() -> tuple[FoldRoute, Hardware, Report, Report]:
    """
    Put a real occupied point in each of two adjacent straight workspace members.
    """
    route = _route(
        (
            Straight(20),
            Straight(13.1),
            _turn(math.pi),
            Straight(10),
            *(_turn(a) for a in (0.1, 0.1, -0.2, 0.1, -0.1)),
            Straight(2),
        )
    )
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    return route, hardware, _report(route, hardware, 0, -1), _report(route, hardware, 1, -0.25)


def disjoint() -> tuple[FoldRoute, Hardware, Report, Report]:
    """
    Put real occupied points in separated straight members of an authored seven-fold hairpin.
    """
    route = _route(
        (
            Straight(20),
            _turn(math.pi),
            Straight(20),
            _turn(math.pi),
            Straight(10),
            *(_turn(a) for a in (0.1, 0.1, -0.2, 0.1, -0.1)),
            Straight(2),
        )
    )
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    return route, hardware, _report(route, hardware, 0, 0.5), _report(route, hardware, 2, 0.5)


def retained(route: FoldRoute, member: PlacedPiece, report: Report) -> Report:
    """
    Update only the ordinal of an exact surviving member, retaining its strictly occupied world point.
    """
    assert report.witness is not None
    index = next(i for i, piece in enumerate(route.pieces) if piece is member)
    assert (
        occupied_coordinates(
            member, report.witness.point, route.targets.lines, route.targets.diameter_mm
        )
        is not None
    )
    return replace(report, witness=replace(report.witness, piece=index))
