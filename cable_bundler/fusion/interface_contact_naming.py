"""
Adapt board-local contact geometry and optional electronics data for naming.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import name_interface_contacts
from ..application.board_contact_import import (
    BoardPad,
    ContactFootprint,
    match_board_contacts,
    read_eagle_board,
)
from ..domain import AttachmentTargetKind, InterfaceDefinition, InterfaceTargetKind, loads
from .interface_contact_cache import resolve_contact_entities
from .interface_contact_projection import _direction, _face_loops, _xyz
from .interface_contact_rows import _in_context
from .interface_targets import resolve_interface_target
from .ui.support import _create_harness_gateway, _require_active_design

_ECAD_UNITS_PER_MM = 320_000.0


def _items(collection: object) -> list[object]:
    """
    Read an indexed Fusion collection without requiring iteration support.
    """
    count = getattr(collection, "count", 0)
    item = getattr(collection, "item", None)
    return [item(index) for index in range(count)] if callable(item) else []


def _frame(occurrence: object) -> tuple[list[float], list[list[float]]]:
    """
    Return an occurrence origin in mm and unit axes in assembly coordinates.
    """
    origin, *vectors = occurrence.transform2.getAsCoordinateSystem()
    center = [float(getattr(origin, axis)) * 10 for axis in ("x", "y", "z")]
    axes = [[float(getattr(vector, axis)) for axis in ("x", "y", "z")] for vector in vectors]
    if not all(math.isfinite(value) for value in center + [v for axis in axes for v in axis]):
        raise ValueError("The board occurrence has an invalid transform.")
    return center, axes


def _board_point(
    point: list[float],
    origin: list[float],
    axes: list[list[float]],
) -> list[float]:
    """
    Express one assembly-space millimeter point in the board occurrence frame.
    """
    offset = [coordinate - center for coordinate, center in zip(point, origin)]
    return [sum(a * b for a, b in zip(offset, axis)) for axis in axes]


def _contact_footprints(
    design: adsk.fusion.Design,
    interface: InterfaceDefinition,
    *,
    through_holes_only: bool = False,
) -> list[ContactFootprint]:
    """
    Project planar copper faces into the explicitly selected board occurrence.
    """
    if (
        len(interface.targets) != 1
        or interface.targets[0].kind is not InterfaceTargetKind.OCCURRENCE
    ):
        raise ValueError("Position naming requires one Interface occurrence as the board frame.")
    board = resolve_interface_target(design, interface.targets[0])
    if board is None:
        raise ValueError("The Interface board occurrence is unavailable.")
    origin, axes = _frame(board)
    footprints = []
    for contact in interface.contacts:
        if contact.kind is not AttachmentTargetKind.FACE:
            continue
        candidates = resolve_contact_entities(design, contact.entity_token)
        if not candidates:
            continue
        projected = [
            (_through_hole_footprint if through_holes_only else _face_footprint)(
                face, str(contact.contact_id), board.fullPathName, origin, axes
            )
            for face in candidates
        ]
        first = projected[0]
        if first is None or any(
            item is None
            or item.layer != first.layer
            or any(
                abs(getattr(item, field) - getattr(first, field)) > 0.02
                for field in ("x", "y", "width", "height", "hole_diameter_mm")
            )
            for item in projected[1:]
        ):
            continue
        footprints.append(first)
    return footprints


def _through_hole_footprint(
    face: object,
    contact_id: str,
    board_path: str,
    origin: list[float],
    axes: list[list[float]],
) -> ContactFootprint | None:
    """
    Measure a planar circular hole analytically, avoiding copper outline tessellation.

    Unusual split-circle loops retain the conservative sampled fallback. Outer
    dimensions are irrelevant to live through-hole matching and use hole diameter.
    """
    path = getattr(getattr(face, "assemblyContext", None), "fullPathName", "")
    match = re.search(r"(?:^|\+)(1|16)-copper:\d+$", path)
    if not path.startswith(board_path + "+") or match is None:
        return None
    try:
        geometry = face.geometry
        normal = _direction(geometry.normal)
        if geometry.objectType != "adsk::core::Plane" or normal is None:
            return None
        if abs(sum(a * b for a, b in zip(normal, axes[2]))) < 0.9999:
            return None
        inner = [loop for loop in _items(face.loops) if not loop.isOuter]
        if len(inner) != 1:
            return None
        coedges = _items(inner[0].coEdges)
        if len(coedges) == 1:
            edge = _in_context(coedges[0].edge, getattr(face, "assemblyContext", None))
            circle = edge.geometry
            if circle.objectType == "adsk::core::Circle3D":
                center = _xyz(circle.center)
                diameter = float(circle.radius) * 20
                if center is not None and math.isfinite(diameter) and diameter > 0:
                    x, y, _ = _board_point(center, origin, axes)
                    return ContactFootprint(
                        contact_id, x, y, diameter, diameter, int(match.group(1)), diameter
                    )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    return _face_footprint(face, contact_id, board_path, origin, axes)


def _face_footprint(
    face: object,
    contact_id: str,
    board_path: str,
    origin: list[float],
    axes: list[list[float]],
) -> ContactFootprint | None:
    """
    Measure a copper outline and, when present, its single circular inner hole.

    Missing/stale Fusion geometry fails closed. Hole centers are authoritative
    for through-hole pads, whose outer copper need not be symmetric.
    """
    path = getattr(getattr(face, "assemblyContext", None), "fullPathName", "")
    match = re.search(r"(?:^|\+)(1|16)-copper:\d+$", path)
    if not path.startswith(board_path + "+") or match is None:
        return None
    try:
        loops = [
            [_board_point(point, origin, axes) for point in loop] for loop in _face_loops(face)
        ]
        native_loops = _items(getattr(face, "loops", None))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    points = [point for loop in loops for point in loop]
    if len(points) < 3 or not all(math.isfinite(value) for point in points for value in point):
        return None
    if max(point[2] for point in points) - min(point[2] for point in points) > 0.15:
        return None
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    if min(width, height) < 0.05:
        return None
    x, y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    hole_diameter = 0.0
    if len(native_loops) == len(loops):
        inner = [loop for loop, native in zip(loops, native_loops) if not native.isOuter]
        if len(inner) == 1 and len(inner[0]) >= 8:
            hx, hy = [point[0] for point in inner[0]], [point[1] for point in inner[0]]
            center_x, center_y = (min(hx) + max(hx)) / 2, (min(hy) + max(hy)) / 2
            radii = [math.hypot(px - center_x, py - center_y) for px, py in zip(hx, hy)]
            if max(radii) - min(radii) <= 0.02:
                hole_diameter = 2 * sum(radii) / len(radii)
                x, y = center_x, center_y
    return ContactFootprint(contact_id, x, y, width, height, int(match.group(1)), hole_diameter)


def _live_board_pads(application: adsk.core.Application) -> list[BoardPad]:
    """
    Read connected through-hole pads through placed signal contact references.

    Package-definition contacts do not expose placed pad objects in the live
    API. Signal references do, with board coordinates in 1/320000 mm units.
    SMDs are intentionally excluded. Missing or malformed records are skipped.
    """
    try:
        import adsk.electron  # type: ignore[import-not-found]
    except ImportError as error:
        raise ValueError("Live electronics data is unavailable in this Fusion build.") from error
    boards = [
        board
        for document in _items(application.documents)
        for product in _items(document.products)
        if (board := adsk.electron.Board.cast(product)) is not None
    ]
    if len(boards) != 1:
        raise ValueError("Open exactly one electronics board for Pos Import.")
    pads = []
    for signal in _items(boards[0].signals):
        for reference in _items(getattr(signal, "contactRefs", None)):
            try:
                contact = reference.contact
                native_pad = getattr(contact, "pad", None)
                if native_pad is None:
                    continue
                owner, pin = reference.element.name, contact.name
                if (
                    not isinstance(owner, str)
                    or not owner.strip()
                    or not isinstance(pin, str)
                    or not pin.strip()
                ):
                    continue
                x, y, diameter, drill = (
                    float(getattr(native_pad, field)) / _ECAD_UNITS_PER_MM
                    for field in ("x", "y", "diameter", "drill")
                )
                if (
                    not all(map(math.isfinite, (x, y, diameter, drill)))
                    or min(diameter, drill) <= 0
                ):
                    continue
                pad = BoardPad(
                    f"{owner}.{pin}",
                    x,
                    y,
                    diameter,
                    diameter,
                    0,
                    str(signal.name or ""),
                    drill,
                )
            except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError):
                continue
            pads.append(pad)
    if not pads:
        raise ValueError(
            "The open electronics board exposes no connected through-hole pad data for Pos Import."
        )
    return pads


def import_interface_contact_names(
    application: adsk.core.Application,
    harness_id: UUID,
    interface_id: UUID,
    source: str,
) -> str:
    """
    Import unique board pad names and report contacts that stayed untouched.
    """
    design = _require_active_design(application)
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    interface = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if interface is None:
        raise ValueError("Selected Interface no longer exists.")
    if source == "file":
        picker = application.userInterface.createFileDialog()
        picker.title = "Load Eagle board for Interface contacts"
        picker.filter = "Eagle board (*.brd)"
        if picker.showOpen() != adsk.core.DialogResults.DialogOK:
            return "Board import cancelled."
        pads = read_eagle_board(Path(picker.filename))
    elif source == "live":
        pads = _live_board_pads(application)
    else:
        raise ValueError("Unsupported Interface naming source.")
    footprints = _contact_footprints(design, interface, through_holes_only=source == "live")
    matches = match_board_contacts(footprints, pads)
    labels = {
        contact_id: f"{pad.label} ({pad.signal})" if source == "live" and pad.signal else pad.label
        for contact_id, pad in matches.items()
    }
    names = {UUID(contact_id): label for contact_id, label in labels.items() if len(label) <= 80}
    if names:
        name_interface_contacts(harness_id, interface_id, names, gateway)
    return (
        f"Named {len(names)} of {len(interface.contacts)} Interface contacts; "
        f"{len(interface.contacts) - len(names)} unchanged."
    )
