"""
Read-only live check of board-local Interface contact footprints.

Requires Fusion with the current 3D PCB assembly and saved Interface contacts.
Run as a script with fusion_mcp_execute readOnly=true. Does not edit the design.
"""

import json

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import loads
from cable_bundler.fusion.interface_contact_naming import _contact_footprints


def run(_context: object) -> None:
    """
    Print board-local footprints for persisted contacts without naming them.
    """
    application = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("Open the 3D PCB design for this check.")
    for attribute in design.findAttributes("kev0.cable_bundler", "harness_definition"):
        definition = loads(attribute.value)
        for interface in definition.interfaces:
            footprints = _contact_footprints(design, interface)
            if footprints:
                print(
                    json.dumps(
                        {
                            "interface": interface.name,
                            "contactCount": len(interface.contacts),
                            "footprints": [item.__dict__ for item in footprints],
                        }
                    )
                )
