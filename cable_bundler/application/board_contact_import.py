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
from zipfile import BadZipFile, ZipFile, is_zipfile

_MAX_BOARD_BYTES = 25_000_000


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


@dataclass(frozen=True)
class BoardContactAnalysis:
    """
    Keep automatic matches and possible pads for contacts needing review.
    """

    matches: dict[str, BoardPad]
    suggestions: dict[str, tuple[BoardPad, ...]]


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


def _board_root(path: Path) -> ET.Element:
    """
    Read an Eagle XML board from a .brd or Fusion .fbrd file.

    Fusion archives may wrap the board XML. Accept exactly one board document
    and bound decompression before parsing any archive member.
    """
    if path.suffix.lower() not in (".brd", ".fbrd"):
        raise ValueError("Choose an Eagle .brd or Fusion .fbrd board under 25 MB.")
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ValueError("The selected board file cannot be read.") from error
    if size > _MAX_BOARD_BYTES:
        raise ValueError("Choose an Eagle .brd or Fusion .fbrd board under 25 MB.")
    try:
        if is_zipfile(path):
            with ZipFile(path) as archive:
                members = [
                    member
                    for member in archive.infolist()
                    if not member.is_dir()
                    and member.filename.lower().endswith((".brd", ".fbrd", ".xml"))
                ]
                if len(members) > 256:
                    raise ValueError("The Fusion board archive has too many XML documents.")
                roots = []
                for member in members:
                    if member.file_size > _MAX_BOARD_BYTES:
                        continue
                    with archive.open(member) as source:
                        data = source.read(_MAX_BOARD_BYTES + 1)
                    if len(data) > _MAX_BOARD_BYTES:
                        continue
                    try:
                        candidate = ET.fromstring(data)
                    except ET.ParseError:
                        continue
                    if candidate.tag == "eagle" and candidate.find("./drawing/board") is not None:
                        roots.append(candidate)
                if len(roots) != 1:
                    raise ValueError("The Fusion board archive must contain one Eagle board.")
                return roots[0]
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError, BadZipFile, RuntimeError) as error:
        raise ValueError(
            "The selected board is not valid Eagle XML or a Fusion board archive."
        ) from error
    if root.tag != "eagle" or root.find("./drawing/board") is None:
        raise ValueError("The selected file is not an Eagle board.")
    return root


def read_eagle_board(path: Path) -> list[BoardPad]:
    """
    Read placed SMD and through-hole contacts from an Eagle or Fusion board.

    Unsupported package rotations are skipped. Invalid or oversized files fail
    without changing any saved names.
    """
    root = _board_root(path)
    board = root.find("./drawing/board")
    if board is None:
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
    Return unique one-to-one matches by board-local center or pad-contained fragment.

    Exact centers take precedence. A split noncircular face may instead leave a
    small outer-boundary fragment inside one nominal pad. Every fragment of a
    contact must identify the same unique pad; ambiguity is rejected.
    """
    return analyze_board_contacts(contacts, pads, position_tolerance_mm).matches


def analyze_board_contacts(
    contacts: Iterable[ContactFootprint],
    pads: Iterable[BoardPad],
    position_tolerance_mm: float = 0.1,
) -> BoardContactAnalysis:
    """
    Preserve conservative matching and expose rejected candidates for review.

    A split contact is automatic only if all fragments agree on one pad and
    no other contact claims it. Suggestions include every fragment's possible
    pads, including those rejected by disagreement or one-to-one conflicts.
    """
    footprints = tuple(contacts)
    board_pads = tuple(pads)
    candidates: dict[str, set[int]] = {}
    possible: dict[str, set[int]] = {}
    for contact in footprints:
        same_layer = [
            index
            for index, pad in enumerate(board_pads)
            if contact.layer in (1, 16) and pad.layer in (0, contact.layer)
        ]
        centered = [
            index
            for index in same_layer
            if math.hypot(contact.x - board_pads[index].x, contact.y - board_pads[index].y)
            <= position_tolerance_mm
        ]
        projected = centered or [
            index
            for index in same_layer
            if _fragment_within_pad(contact, board_pads[index], position_tolerance_mm)
        ]
        possible.setdefault(contact.contact_id, set()).update(projected)
        if contact.contact_id in candidates:
            candidates[contact.contact_id].intersection_update(projected)
        else:
            candidates[contact.contact_id] = set(projected)
    matches = {
        contact_id: board_pads[next(iter(indexes))]
        for contact_id, indexes in candidates.items()
        if len(indexes) == 1
        and sum(next(iter(indexes)) in other for other in candidates.values()) == 1
    }
    suggestions = {
        contact_id: tuple(board_pads[index] for index in sorted(indexes))
        for contact_id, indexes in possible.items()
        if contact_id not in matches
    }
    return BoardContactAnalysis(matches, suggestions)


def _fragment_within_pad(
    contact: ContactFootprint,
    pad: BoardPad,
    tolerance_mm: float,
) -> bool:
    """
    Admit a partial outer face only when its full bounds fit one pad's bounds.
    """
    if min(contact.width, contact.height, pad.width, pad.height) <= 0:
        return False
    allowance = max(tolerance_mm, 0.2)
    return (
        abs(contact.x - pad.x) + contact.width / 2 <= pad.width / 2 + allowance
        and abs(contact.y - pad.y) + contact.height / 2 <= pad.height / 2 + allowance
    )
