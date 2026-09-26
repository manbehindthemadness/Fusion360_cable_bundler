"""
Inspect recently selected Interface faces for I/O pad identification.

Requires Fusion with the current 3D PCB design active and saved Interface
contacts. Execute through the local MCP server with readOnly=true. Prints
bounded geometry metadata without changing documents, geometry, or harness data.
"""

import json

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.electron

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import loads
from cable_bundler.fusion.interface_contact_naming import _board_point, _frame
from cable_bundler.fusion.interface_contact_projection import _face_loops
from cable_bundler.fusion.interface_targets import resolve_interface_target


def _read_connector(application: adsk.core.Application) -> None:
    """
    Report the native signal reference path for the first three J3 connector pads.
    """
    for document in application.documents:
        for product in document.products:
            board = adsk.electron.Board.cast(product)
            if board is None:
                continue
            for signal in board.signals:
                references = getattr(signal, "contactRefs", None)
                if references is None:
                    print(
                        json.dumps(
                            {
                                "signalMembers": [
                                    key for key in dir(signal) if not key.startswith("_")
                                ]
                            }
                        )
                    )
                    return
                for reference in references:
                    if reference.element.name != "J3":
                        continue
                    contact = reference.contact
                    if contact.name not in ("01", "02", "03"):
                        continue
                    pad = contact.pad
                    print(
                        json.dumps(
                            {
                                "connector": reference.element.name,
                                "pin": contact.name,
                                "signal": signal.name,
                                "hasNativePad": pad is not None,
                                "rawPad": None
                                if pad is None
                                else {
                                    key: getattr(pad, key)
                                    for key in ("x", "y", "diameter", "drill")
                                },
                            }
                        )
                    )


def run(_context: object) -> None:
    """
    Print board-local bounds for the three most recently added contact faces.
    """
    application = adsk.core.Application.get()
    _read_connector(application)
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("Activate the 3D PCB design for the contact probe.")
    for attribute in design.findAttributes("kev0.cable_bundler", "harness_definition"):
        for interface in loads(attribute.value).interfaces:
            if len(interface.targets) != 1:
                continue
            board_occurrence = resolve_interface_target(design, interface.targets[0])
            if board_occurrence is None:
                continue
            origin, axes = _frame(board_occurrence)
            print(json.dumps({"interface": interface.name, "contacts": len(interface.contacts)}))
            for contact in interface.contacts[-3:]:
                for face in design.findEntityByToken(contact.entity_token) or ():
                    if adsk.fusion.BRepFace.cast(face) is None:
                        continue
                    loops = _face_loops(face)
                    points = [_board_point(point, origin, axes) for loop in loops for point in loop]
                    bounds = (
                        [
                            [
                                min(point[axis] for point in points),
                                max(point[axis] for point in points),
                            ]
                            for axis in range(3)
                        ]
                        if points
                        else []
                    )
                    print(
                        json.dumps(
                            {
                                "contactId": str(contact.contact_id),
                                "geometry": face.geometry.objectType,
                                "path": face.assemblyContext.fullPathName,
                                "boardLocalBoundsMm": bounds,
                            }
                        )
                    )
