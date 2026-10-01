"""
Replay representative saved ribbon fits without changing the active Fusion design.

Submit as a ``readOnly=true`` script through the optional local Fusion MCP server.
Requires the saved ``Wire creation tester v107`` document and no active command.
The three samples span the smallest, median, and largest stored branch diameters.
"""

import json
from time import perf_counter
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import loads
from cable_bundler.fusion import cable_solids
from cable_bundler.fusion.cable_solid_parts.metadata import world_to_harness
from cable_bundler.fusion.cable_solid_parts.ribbon_overlap import fitted_ribbon_overlap_diameter
from cable_bundler.fusion.ribbon_geometry import ribbon_route_shape


class _CountingBody:
    """
    Count read-only native classifications delegated to the saved ribbon body.
    """

    def __init__(self, body: adsk.fusion.BRepBody) -> None:
        """
        Retain the stable generated body for one fit replay.
        """
        self.body = body
        self.queries = 0

    def pointContainment(self, point: adsk.core.Point3D) -> int:
        """
        Forward one unchanged point classification to Fusion.
        """
        self.queries += 1
        return self.body.pointContainment(point)


def run(_context: object) -> None:
    """
    Compare stored branch diameters with current fitter results on saved geometry.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.name != "Wire creation tester v107":
        raise RuntimeError("Open the saved Wire creation tester v107 design first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before replaying ribbon fits.")
    modified_before = document.isModified
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    definitions = tuple(
        (adsk.fusion.Component.cast(attribute.parent), loads(attribute.value))
        for attribute in design.findAttributes("kev0.cable_bundler", "harness_definition")
    )
    for occurrence in design.rootComponent.allOccurrences:
        if "Cable Group 5" not in occurrence.component.name:
            continue
        attribute = occurrence.component.attributes.itemByName(
            "kev0.cable_bundler", "generated_cable_group"
        )
        if attribute is None:
            continue
        metadata = json.loads(attribute.value)
        group_id = UUID(metadata["cable_group_id"])
        harness, definition = next(
            (
                (component, saved)
                for component, saved in definitions
                if component is not None
                and any(group.cable_group_id == group_id for group in saved.cable_groups)
            ),
            (None, None),
        )
        if harness is None or definition is None:
            raise RuntimeError("The generated ribbon has no owning harness definition.")
        group = next(group for group in definition.cable_groups if group.cable_group_id == group_id)
        body = next(
            (
                body
                for body in occurrence.component.bRepBodies
                if "Discrete Ribbon" in body.name and body.isValid and body.isSolid
            ),
            None,
        )
        if body is None:
            raise RuntimeError("The saved ribbon body is unavailable.")
        route_started = perf_counter()
        _routes, legs, by_id = cable_solids._solve_complete_group_routes(design, definition, None)
        main = next(
            leg for leg in legs if leg.cable_group_id == group_id and not leg.is_connection_branch
        )
        fitted = ribbon_route_shape(
            design,
            definition,
            main,
            by_id[main.route_id],
            group.ribbon_lines,
            group.diameter_mm,
        )
        route_and_shape_ms = round((perf_counter() - route_started) * 1000.0, 1)
        planes = {
            main.start_connection_id: fitted.guide_planes[0],
            main.end_connection_id: fitted.guide_planes[1],
        }
        saved_by_id = {
            UUID(branch["route_id"]): float(branch["diameter_mm"])
            for branch in metadata["connection_branches"]
        }
        branches = sorted(
            (leg for leg in legs if leg.cable_group_id == group_id and leg.is_connection_branch),
            key=lambda leg: saved_by_id[leg.route_id],
        )
        if not branches:
            raise RuntimeError("The saved ribbon has no connection branches.")
        transform = world_to_harness(design, harness)
        samples = []
        for index in sorted({0, len(branches) // 2, len(branches) - 1}):
            branch = branches[index]
            guide_plane = planes.get(branch.start_connection_id)
            if guide_plane is None:
                raise RuntimeError("The saved branch has no fitted guide plane.")
            counted = _CountingBody(body)
            started = perf_counter()
            measured = fitted_ribbon_overlap_diameter(
                counted,
                by_id[branch.route_id],
                guide_plane,
                branch.diameter_mm or group.diameter_mm,
                transform,
            )
            saved = saved_by_id[branch.route_id]
            samples.append(
                {
                    "route_id": str(branch.route_id),
                    "saved_diameter_mm": saved,
                    "measured_diameter_mm": measured,
                    "difference_mm": measured - saved,
                    "containment_queries": counted.queries,
                    "fit_ms": round((perf_counter() - started) * 1000.0, 1),
                }
            )
        print(
            "RIBBON_FIT_PARITY="
            + json.dumps(
                {
                    "document": document.name,
                    "route_and_shape_ms": route_and_shape_ms,
                    "samples": samples,
                    "within_fit_precision": all(
                        abs(sample["difference_mm"]) <= 0.005 for sample in samples
                    ),
                    "document_modified_before": modified_before,
                    "document_modified_after": document.isModified,
                },
                sort_keys=True,
            )
        )
        return
    raise RuntimeError("The active design has no generated Cable Group 5 ribbon.")
