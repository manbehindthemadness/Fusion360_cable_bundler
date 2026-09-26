"""
Preview current Pos Import matches without saving contact names.

Requires Fusion with the 3D PCB assembly active and exactly one electronics
board open. Run through local MCP with readOnly=true. Loads isolated copies of
the changed modules, avoiding a reload of the running add-in.
"""

import json
import runpy

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import loads


def run(_context: object) -> None:
    """
    Print uniquely matched connector pins from the current on-disk implementation.
    """
    board_module = runpy.run_module("cable_bundler.application.board_contact_import")
    adapter = runpy.run_module("cable_bundler.fusion.interface_contact_naming")
    globals_ = adapter["_live_board_pads"].__globals__
    globals_.update(
        {key: board_module[key] for key in ("BoardPad", "ContactFootprint", "match_board_contacts")}
    )
    application = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("Activate the 3D PCB assembly before the preview.")
    pads = adapter["_live_board_pads"](application)
    for attribute in design.findAttributes("kev0.cable_bundler", "harness_definition"):
        for interface in loads(attribute.value).interfaces:
            footprints = adapter["_contact_footprints"](design, interface)
            matches = board_module["match_board_contacts"](footprints, pads)
            print(
                json.dumps(
                    {
                        "interface": interface.name,
                        "contactCount": len(interface.contacts),
                        "connectedThroughHolePads": len(pads),
                        "matches": {
                            key: f"{pad.label} ({pad.signal})" for key, pad in matches.items()
                        },
                    },
                    sort_keys=True,
                )
            )
