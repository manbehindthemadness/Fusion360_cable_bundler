"""
Regenerate only Pathway_001 in the current unsaved Fusion test design.

Run through the local Fusion MCP script executor after confirming the active
document and idle command. The experiment leaves the generated body visible
and does not save or close the document.
"""

from __future__ import annotations

from typing import Any


def rebuild_candidate() -> dict[str, Any]:
    """
    Replace only the existing Pathway_001 group and report its fitted output.
    """
    import adsk.core  # type: ignore[import-not-found]
    import adsk.fusion  # type: ignore[import-not-found]

    from cable_bundler.application import load_harnesses, plan_cable_group_routes
    from cable_bundler.fusion.cable_solids import (
        _generated_cable_group_metadata_by_id,
        _refresh_generated_cable_groups,
    )
    from cable_bundler.fusion.ribbon_geometry import ribbon_route_shape
    from cable_bundler.fusion.route_preview import solve_cable_group_centerlines
    from cable_bundler.fusion.ui.support import _create_harness_gateway

    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.name != "Wire creation tester v104":
        raise RuntimeError("Open the expected Wire creation tester v104 design first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before regenerating the ribbon.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    gateway = _create_harness_gateway(application)
    harnesses = tuple(item.definition for item in load_harnesses(gateway) if item.definition)
    if len(harnesses) != 1:
        raise RuntimeError("The test design must contain exactly one valid harness.")
    definition = harnesses[0]
    pathway_names = {path.pathway_id: path.name for path in definition.pathways}
    candidates = tuple(
        leg
        for leg in plan_cable_group_routes(definition)
        if "Pathway_001" in (pathway_names.get(pathway_id) for pathway_id in leg.pathway_ids)
    )
    if len(candidates) != 1:
        raise RuntimeError("Pathway_001 must identify exactly one group route.")
    leg = candidates[0]
    group = next(
        group for group in definition.cable_groups if group.cable_group_id == leg.cable_group_id
    )
    if group.group_type.value != "ribbon" or group.ribbon_lines != 19:
        raise RuntimeError("Pathway_001 is not the expected 19-line ribbon.")
    harness = gateway.harness_component(definition.harness_id)
    if harness is None:
        raise RuntimeError("The harness component is unavailable.")
    before = _generated_cable_group_metadata_by_id(harness)
    if leg.cable_group_id not in before:
        raise RuntimeError("Pathway_001 has no generated body to replace.")
    before_occurrence = before[leg.cable_group_id][0]
    before_name = before_occurrence.component.name
    routes, solved_legs = solve_cable_group_centerlines(design, definition)
    matched = next(
        (
            route
            for route, solved_leg in zip(routes, solved_legs)
            if solved_leg.route_id == leg.route_id
        ),
        None,
    )
    if matched is None:
        raise RuntimeError("Pathway_001 route solving failed.")
    fitted = ribbon_route_shape(
        design, definition, leg, matched, group.ribbon_lines, group.diameter_mm
    )
    if fitted.shape.start_fit is None or fitted.shape.end_fit is None:
        raise RuntimeError(f"Pathway_001 did not fit both guides: {fitted.fit_warnings!r}")
    notices: list[str] = []
    replaced = _refresh_generated_cable_groups(
        design, harness, definition, frozenset({leg.cable_group_id}), notices
    )
    after = _generated_cable_group_metadata_by_id(harness)
    occurrence = after[leg.cable_group_id][0]
    component = occurrence.component
    bodies = component.bRepBodies
    return {
        "document": document.name,
        "replaced": replaced,
        "oldComponent": before_name,
        "newComponent": component.name,
        "oldOccurrenceValid": before_occurrence.isValid,
        "visible": occurrence.isLightBulbOn,
        "bodyCount": bodies.count,
        "solid": bodies.count == 1 and bodies.item(0).isSolid,
        "loftCount": component.features.loftFeatures.count,
        "sweepCount": component.features.sweepFeatures.count,
        "startFitted": fitted.shape.start_fit is not None,
        "endFitted": fitted.shape.end_fit is not None,
        "spread": fitted.shape.spread,
        "maximumPitchRatio": fitted.shape.maximum_pitch_ratio,
        "minimumEndRadiusMm": fitted.shape.minimum_end_radius_mm,
        "endLeadMm": fitted.shape.end_lead_mm,
        "fitWarnings": fitted.fit_warnings,
        "notices": notices,
        "saved": False,
    }
