"""
Verify a full connector row against the current hardware_ble_test assembly.

Requires Fusion, the current 3D PCB design with a named J3.01 Interface contact,
and its electronics board open. Run through local MCP with readOnly=true. Reads
the first and last J3 pads and checks all 19 row identities without adding or
renaming contacts or changing the current selection.
"""

import json
import math
import runpy
import sys
from types import ModuleType

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import loads
from cable_bundler.fusion.interface_contact_naming import _board_point, _frame, _live_board_pads
from cable_bundler.fusion.interface_targets import resolve_interface_target


def run(_context: object) -> None:
    """
    Check the isolated current row implementation against real connector geometry.
    """
    core_name = "cable_bundler.application.interface_contact_rows"
    core = runpy.run_module(core_name, alter_sys=True)
    isolated = ModuleType(core_name)
    vars(isolated).update(core)
    previous = sys.modules.get(core_name)
    try:
        sys.modules[core_name] = isolated
        adapter = runpy.run_module("cable_bundler.fusion.interface_contact_rows", alter_sys=True)
    finally:
        if previous is None:
            sys.modules.pop(core_name, None)
        else:
            sys.modules[core_name] = previous
    application = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("Activate the hardware_ble_test 3D assembly.")
    pads = [pad for pad in _live_board_pads(application) if pad.label.startswith("J3.")]
    end_pad = next(pad for pad in pads if pad.label == "J3.19")
    for attribute in design.findAttributes("kev0.cable_bundler", "harness_definition"):
        for interface in loads(attribute.value).interfaces:
            contact = next(
                (item for item in interface.contacts if item.name.startswith("J3.01")), None
            )
            if contact is None:
                continue
            board = resolve_interface_target(design, interface.targets[0])
            origin, axes = _frame(board)
            describe = adapter["describe_row_target"]
            first = max(
                design.findEntityByToken(contact.entity_token),
                key=lambda face: _board_point(describe(face).center_mm, origin, axes)[2],
            )
            start = describe(first)
            start_local = _board_point(start.center_mm, origin, axes)
            expected_end = [end_pad.x, end_pad.y, start_local[2]]
            expected_world = [
                origin[i] + sum(expected_end[j] * axes[j][i] for j in range(3)) for i in range(3)
            ]
            candidates = list(adapter["_candidates"](adapter["_scope"](first), start.kind))
            matching = []
            for entity in candidates:
                if not adapter["_near_segment_bounds"](entity, expected_world, expected_world):
                    continue
                target = describe(entity)
                if target.geometry_type != start.geometry_type:
                    continue
                point = _board_point(target.center_mm, origin, axes)
                matching.append((math.dist(point, expected_end), entity))
            distance, last = min(matching, key=lambda item: item[0])
            if distance > 0.02:
                raise RuntimeError("The expected J3.19 endpoint was not found.")
            row = adapter["collect_contact_row"](first, last)
            labels = []
            for item in row:
                point = _board_point(item.center_mm, origin, axes)
                matching_pads = [
                    pad for pad in pads if math.hypot(point[0] - pad.x, point[1] - pad.y) < 0.02
                ]
                if len(matching_pads) != 1:
                    raise RuntimeError("A row member does not uniquely match a J3 pad.")
                labels.append(matching_pads[0].label)
            expected = [f"J3.{index:02}" for index in range(1, 20)]
            if labels != expected:
                raise RuntimeError(f"Unexpected row identities: {labels!r}")
            reverse = adapter["collect_contact_row"](last, first)
            if [item.token for item in reverse] != [item.token for item in reversed(row)]:
                raise RuntimeError("Reversed endpoint picks changed row membership.")
            print(
                json.dumps(
                    {"status": "passed", "count": len(row), "labels": labels, "reverseOrder": True}
                )
            )
            return
    raise RuntimeError("Save a named J3.01 Interface contact before running this fixture.")
