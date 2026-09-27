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
    analyze_board_contacts,
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


def _linked_pad_name(pad: BoardPad) -> str:
    """
    Mark an unconnected linked-board pad explicitly instead of omitting its net.
    """
    return f"{pad.label} ({pad.signal or 'NC'})"


def preview_interface_contact_names(
    application: adsk.core.Application,
    harness_id: UUID,
    interface_id: UUID,
    pads: list[BoardPad],
) -> dict[str, object]:
    """
    Prepare only actionable pad conflicts without editing unmatched contacts.
    """
    design = _require_active_design(application)
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    interface = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if interface is None:
        raise ValueError("Selected Interface no longer exists.")
    analysis = analyze_board_contacts(_contact_footprints(design, interface), pads)
    auto_names = []
    unresolved = []
    for index, contact in enumerate(interface.contacts, start=1):
        contact_id = str(contact.contact_id)
        matched = analysis.matches.get(contact_id)
        if matched is not None:
            label = _linked_pad_name(matched)
            if len(label) <= 80:
                auto_names.append({"contactId": contact_id, "name": label})
                continue
        suggestions = list(
            dict.fromkeys(
                label
                for pad in analysis.suggestions.get(contact_id, ())
                if len(label := _linked_pad_name(pad)) <= 80
            )
        )
        if not suggestions:
            continue
        unresolved.append(
            {
                "contactId": contact_id,
                "label": f"Contact {index}",
                "currentName": contact.name,
                "suggestions": suggestions,
            }
        )
    return {"autoNames": auto_names, "unresolved": unresolved}


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
) -> list[ContactFootprint]:
    """
    Project copper faces or circular edges into the selected board occurrence.
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
        if contact.kind not in (AttachmentTargetKind.FACE, AttachmentTargetKind.CIRCULAR_EDGE):
            continue
        candidates = resolve_contact_entities(design, contact.entity_token)
        if not candidates:
            continue
        projected = [
            (
                _through_hole_footprint
                if contact.kind is AttachmentTargetKind.FACE
                else _circular_edge_footprint
            )(entity, str(contact.contact_id), board.fullPathName, origin, axes)
            for entity in candidates
        ]
        first = projected[0]
        if first is None or any(
            item is None or item.layer != first.layer for item in projected[1:]
        ):
            continue
        footprints.extend(item for item in projected if item is not None)
    return footprints


def _circular_edge_footprint(
    edge: object,
    contact_id: str,
    board_path: str,
    origin: list[float],
    axes: list[list[float]],
) -> ContactFootprint | None:
    """
    Use a selected circular copper edge as a board-local pad-center probe.
    """
    path = getattr(getattr(edge, "assemblyContext", None), "fullPathName", "")
    match = re.search(r"(?:^|\+)(1|16)-copper:\d+$", path)
    if not path.startswith(board_path + "+") or match is None:
        return None
    try:
        circle = edge.geometry
        if circle.objectType != "adsk::core::Circle3D":
            return None
        center = _xyz(circle.center)
        diameter = float(circle.radius) * 20
        if center is None or not math.isfinite(diameter) or diameter <= 0:
            return None
        x, y, _ = _board_point(center, origin, axes)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return ContactFootprint(contact_id, x, y, diameter, diameter, int(match.group(1)))


def _through_hole_footprint(
    face: object,
    contact_id: str,
    board_path: str,
    origin: list[float],
    axes: list[list[float]],
) -> ContactFootprint | None:
    """
    Locate a planar pad from its outer circular edge before other geometry.

    Partial outer arcs retain the original pad center when a face is split.
    Other faces use the circular hole or sampled copper outline as a fallback.
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
        loops = _items(face.loops)
        outer = [loop for loop in loops if loop.isOuter]
        if len(outer) == 1:
            circular = _outer_circular_footprint(
                outer[0],
                getattr(face, "assemblyContext", None),
                contact_id,
                int(match.group(1)),
                origin,
                axes,
            )
            if circular is not None:
                return circular
        inner = [loop for loop in loops if not loop.isOuter]
        coedges = _items(inner[0].coEdges) if len(inner) == 1 else []
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


def _outer_circular_footprint(
    loop: object,
    context: object,
    contact_id: str,
    layer: int,
    origin: list[float],
    axes: list[list[float]],
) -> ContactFootprint | None:
    """
    Use concentric circular outer edges, including arcs of a split pad.

    Conflicting centers or radii are not treated as one pad perimeter.
    """
    circles: list[tuple[float, float, float]] = []
    for coedge in _items(getattr(loop, "coEdges", None)):
        try:
            edge = _in_context(coedge.edge, context)
            curve = edge.geometry
            if curve.objectType not in ("adsk::core::Circle3D", "adsk::core::Arc3D"):
                continue
            center = _xyz(curve.center)
            radius = float(curve.radius) * 10
            if center is None or not math.isfinite(radius) or radius <= 0:
                continue
            x, y, _ = _board_point(center, origin, axes)
            if math.isfinite(x) and math.isfinite(y):
                circles.append((x, y, radius))
        except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError):
            continue
    if not circles:
        return None
    x, y, radius = circles[0]
    if any(
        math.hypot(other_x - x, other_y - y) > 0.02 or abs(other_radius - radius) > 0.02
        for other_x, other_y, other_radius in circles[1:]
    ):
        return None
    diameter = 2 * radius
    return ContactFootprint(contact_id, x, y, diameter, diameter, layer)


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
    outline = (
        [loop for loop, native in zip(loops, native_loops) if native.isOuter]
        if len(native_loops) == len(loops)
        else loops
    )
    points = [point for loop in outline for point in loop]
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


def _board_pads(board: object) -> list[BoardPad]:
    """
    Read connected solderable contacts through placed signal references.

    Package-definition contacts do not expose placed pad objects in the live
    API. Signal references do, with board coordinates in 1/320000 mm units.
    Missing or malformed records are skipped.
    """
    pads = []
    for signal in _items(board.signals):
        for reference in _items(getattr(signal, "contactRefs", None)):
            try:
                contact = reference.contact
                native_pad = getattr(contact, "pad", None)
                native_smd = getattr(contact, "smd", None) if native_pad is None else None
                if native_pad is None and native_smd is None:
                    continue
                owner, pin = reference.element.name, contact.name
                if (
                    not isinstance(owner, str)
                    or not owner.strip()
                    or not isinstance(pin, str)
                    or not pin.strip()
                ):
                    continue
                if native_pad is not None:
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
                else:
                    x, y, dx, dy = (
                        float(getattr(native_smd, field)) / _ECAD_UNITS_PER_MM
                        for field in ("x", "y", "dx", "dy")
                    )
                    angle = math.radians(float(native_smd.angle))
                    layer = int(native_smd.layer)
                    if (
                        not all(map(math.isfinite, (x, y, dx, dy, angle)))
                        or min(dx, dy) <= 0
                        or layer not in (1, 16)
                    ):
                        continue
                    width = abs(dx * math.cos(angle)) + abs(dy * math.sin(angle))
                    height = abs(dx * math.sin(angle)) + abs(dy * math.cos(angle))
                    pad = BoardPad(
                        f"{owner}.{pin}",
                        x,
                        y,
                        width,
                        height,
                        layer,
                        str(signal.name or ""),
                    )
            except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError):
                continue
            pads.append(pad)
    if not pads:
        raise ValueError(
            "The linked electronics board exposes no connected pad data for Pos Import."
        )
    return pads


def _live_board_pads(application: adsk.core.Application) -> list[BoardPad]:
    """
    Retain the diagnostic open-board path without using it for palette import.
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
    return _board_pads(boards[0])


def import_interface_contact_names(
    application: adsk.core.Application,
    harness_id: UUID,
    interface_id: UUID,
    source: str,
    prepared_pads: list[BoardPad] | None = None,
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
        picker.title = "Load board for Interface contacts"
        picker.filter = "Board files (*.brd;*.fbrd)"
        if picker.showOpen() != adsk.core.DialogResults.DialogOK:
            return "Board import cancelled."
        pads = read_eagle_board(Path(picker.filename))
    elif source == "live":
        pads = _live_board_pads(application)
    elif source == "linked" and prepared_pads is not None:
        pads = prepared_pads
    else:
        raise ValueError("Unsupported Interface naming source.")
    footprints = _contact_footprints(design, interface)
    matches = match_board_contacts(footprints, pads)
    labels = {
        contact_id: f"{pad.label} ({pad.signal})"
        if source in ("live", "linked") and pad.signal
        else pad.label
        for contact_id, pad in matches.items()
    }
    names = {UUID(contact_id): label for contact_id, label in labels.items() if len(label) <= 80}
    if names:
        name_interface_contacts(harness_id, interface_id, names, gateway)
    return (
        f"Named {len(names)} of {len(interface.contacts)} Interface contacts; "
        f"{len(interface.contacts) - len(names)} unchanged."
    )
