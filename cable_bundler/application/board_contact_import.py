"""
Read Eagle board pads and match them conservatively to projected contacts.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class BoardPad:
    """
    Describe a board-local pad; layer zero denotes a plated through-hole pad.
    """

    label: str
    x: float
    y: float
    width: float
    height: float
    layer: int
    signal: str = ""
    drill_diameter_mm: float = 0.0


@dataclass(frozen=True)
class ContactFootprint:
    """
    Describe a selected planar contact in the same board frame.
    """

    contact_id: str
    x: float
    y: float
    width: float
    height: float
    layer: int
    hole_diameter_mm: float = 0.0


def _angle(rotation: str) -> tuple[float, bool]:
    """
    Decode Eagle's optional mirror and spin prefixes.
    """
    match = re.fullmatch(r"([MS]*?)R(-?\d+(?:\.\d+)?)", rotation or "R0")
    if match is None:
        raise ValueError(f"Unsupported board rotation: {rotation!r}.")
    return math.radians(float(match.group(2))), "M" in match.group(1)


def _point(x: float, y: float, angle: float, mirrored: bool) -> tuple[float, float]:
    """
    Apply the element's mirror before its board rotation.
    """
    if mirrored:
        x = -x
    return (x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle))


def read_eagle_board(path: Path) -> list[BoardPad]:
    """
    Read placed SMD and through-hole contacts from a Fusion/Eagle XML board.

    Unsupported package rotations are skipped. Non-XML or oversized files fail
    without changing any saved names.
    """
    if path.suffix.lower() != ".brd":
        raise ValueError("Choose a Fusion/Eagle XML .brd file under 25 MB.")
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ValueError("The selected board file cannot be read.") from error
    if size > 25_000_000:
        raise ValueError("Choose a Fusion/Eagle XML .brd file under 25 MB.")
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValueError("The selected board is not valid Eagle XML.") from error
    board = root.find("./drawing/board")
    if root.tag != "eagle" or board is None:
        raise ValueError("The selected file is not an Eagle board.")
    packages = {
        (library.get("name"), package.get("name")): package
        for library in board.findall("./libraries/library")
        for package in library.findall("./packages/package")
    }
    signals = {
        (ref.get("element"), ref.get("pad")): signal.get("name", "")
        for signal in board.findall("./signals/signal")
        for ref in signal.findall("contactref")
    }
    pads = []
    for element in board.findall("./elements/element"):
        package = packages.get((element.get("library"), element.get("package")))
        if package is None:
            continue
        try:
            origin_x, origin_y = float(element.get("x", "nan")), float(element.get("y", "nan"))
            angle, mirror = _angle(element.get("rot", "R0"))
        except ValueError:
            continue
        for smd in package.findall("smd"):
            try:
                pad_angle, pad_mirror = _angle(smd.get("rot", "R0"))
                local_x, local_y = float(smd.get("x", "nan")), float(smd.get("y", "nan"))
                dx, dy = float(smd.get("dx", "nan")), float(smd.get("dy", "nan"))
                layer = int(smd.get("layer", "0"))
            except ValueError:
                continue
            if not all(map(math.isfinite, (origin_x, origin_y, local_x, local_y, dx, dy))):
                continue
            if dx <= 0 or dy <= 0 or layer not in (1, 16) or pad_mirror:
                continue
            offset_x, offset_y = _point(local_x, local_y, angle, mirror)
            orientation = angle + (-pad_angle if mirror else pad_angle)
            width = abs(dx * math.cos(orientation)) + abs(dy * math.sin(orientation))
            height = abs(dx * math.sin(orientation)) + abs(dy * math.cos(orientation))
            name = smd.get("name", "")
            owner = element.get("name", "")
            if not owner or not name:
                continue
            pads.append(
                BoardPad(
                    f"{owner}.{name}",
                    origin_x + offset_x,
                    origin_y + offset_y,
                    width,
                    height,
                    17 - layer if mirror else layer,
                    signals.get((owner, name), ""),
                )
            )
        for native_pad in package.findall("pad"):
            try:
                local_x = float(native_pad.get("x", "nan"))
                local_y = float(native_pad.get("y", "nan"))
                drill = float(native_pad.get("drill", "nan"))
                diameter = float(native_pad.get("diameter", str(drill)))
            except ValueError:
                continue
            if not all(map(math.isfinite, (origin_x, origin_y, local_x, local_y, drill, diameter))):
                continue
            if min(drill, diameter) <= 0:
                continue
            name = native_pad.get("name", "")
            owner = element.get("name", "")
            if not owner or not name:
                continue
            offset_x, offset_y = _point(local_x, local_y, angle, mirror)
            pads.append(
                BoardPad(
                    f"{owner}.{name}",
                    origin_x + offset_x,
                    origin_y + offset_y,
                    diameter,
                    diameter,
                    0,
                    signals.get((owner, name), ""),
                    drill,
                )
            )
    return pads


def match_board_contacts(
    contacts: Iterable[ContactFootprint],
    pads: Iterable[BoardPad],
    position_tolerance_mm: float = 0.1,
) -> dict[str, BoardPad]:
    """
    Return unique one-to-one matches by board-local center and copper side.

    A 3D copper outline or hole may not have the nominal 2D pad dimensions.
    Positional ambiguity is rejected rather than guessed from those dimensions.
    """
    footprints = tuple(contacts)
    board_pads = tuple(pads)
    candidates: dict[str, list[int]] = {}
    for contact in footprints:
        candidates[contact.contact_id] = [
            index
            for index, pad in enumerate(board_pads)
            if contact.layer in (1, 16)
            and pad.layer in (0, contact.layer)
            and math.hypot(contact.x - pad.x, contact.y - pad.y) <= position_tolerance_mm
        ]
    return {
        contact_id: board_pads[indexes[0]]
        for contact_id, indexes in candidates.items()
        if len(indexes) == 1 and sum(indexes[0] in other for other in candidates.values()) == 1
    }
