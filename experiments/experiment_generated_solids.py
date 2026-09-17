"""
Verify grouped-wire material ownership, transforms, modeling modes, and clearing.

The scenario uses an isolated unsaved Hybrid design and leaves no document or cloud
data behind. Run it inside Fusion through its registered runner or the QA suite.
"""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Optional
from uuid import UUID

ADDIN_ROOT = Path(__file__).resolve().parent.parent
if str(ADDIN_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDIN_ROOT))

# noinspection PyUnresolvedReferences
import adsk.core  # noqa: E402

# noinspection PyUnresolvedReferences
import adsk.fusion  # noqa: E402

from experiments.experiment_command_history import (  # noqa: E402
    HARNESS_ID,
    build_single_wire_fixture,
)
from experiments.scenario_report import ScenarioReport  # noqa: E402
from wire_bundler.application import set_harness_material_defaults  # noqa: E402
from wire_bundler.domain import (  # noqa: E402
    StripePattern,
    WireColor,
    WireGroupDefinition,
    WireMaterialSettings,
    WireStripe,
    dumps,
    loads,
)
from wire_bundler.fusion.wire_solids import (  # noqa: E402
    GENERATED_STRIPE_GROUP_ID,
    GENERATED_WIRE_GROUP_ATTRIBUTE,
    build_wire_group_solid,
    clear_wire_solids,
    generate_wire_group_solids,
    generated_wire_group_bodies,
    generated_wire_group_occurrences,
)
from wire_bundler.routing import CubicBezier, RoutePreview, Vector3  # noqa: E402

SCENARIO_NAME = "generated_solids"
ARTIFACT_ROOT = ADDIN_ROOT / "artifacts" / "verification"
TRANSLATION_CM = (2.0, -1.5, 0.75)
WIRE_GROUP_ID = UUID("7a000000-0000-0000-0000-000000000008")


def run(_context: object) -> None:
    """
    Run the isolated generated-solid scenario and display its result.
    """
    report = ScenarioReport(SCENARIO_NAME, ARTIFACT_ROOT, _log_to_fusion)
    application: Optional[adsk.core.Application] = None
    try:
        application = _require_application()
        verify_generated_solids(application, report)
        report.finish(True)
        application.userInterface.messageBox(
            "Generated-solid verification passed.\n\n"
            f"Log: {report.log_path}\nReport: {report.json_path}",
            "Wire Bundler Generated Solids",
        )
    except (AssertionError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
        failure = traceback.format_exc()
        report.finish(False, failure)
        if application is not None and application.userInterface is not None:
            application.userInterface.messageBox(
                "Generated-solid verification failed.\n\n"
                f"Log: {report.log_path}\nReport: {report.json_path}\n\n{failure}",
                "Wire Bundler Generated Solids",
            )


def verify_generated_solids(
    application: adsk.core.Application,
    report: ScenarioReport,
) -> None:
    """
    Generate a striped wire, move its parent occurrence, and clear it.
    """
    previous_document = application.activeDocument
    initial_document_count = application.documents.count
    document: Optional[adsk.core.Document] = None
    try:
        with report.step("Create isolated generated-solid fixture"):
            document = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            if document is None:
                raise RuntimeError("Fusion did not create the generated-solid fixture.")
            design = adsk.fusion.Design.cast(application.activeProduct)
            if design is None:
                raise RuntimeError("Fusion did not activate the generated-solid fixture.")
            design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
            gateway = build_single_wire_fixture(application, design)

        with report.step("Apply deterministic insulation and stripe settings"):
            materials = WireMaterialSettings(
                insulation_material="QA ETFE",
                main_color=WireColor("QA Blue", 30, 90, 210),
                stripes=(
                    WireStripe(
                        color=WireColor("QA Yellow", 250, 210, 20),
                        width_mm=0.35,
                        pattern=StripePattern.HELICAL,
                        angle_deg=35.0,
                        repeat_mm=8.0,
                    ),
                    WireStripe(
                        color=WireColor("QA White", 245, 245, 245),
                        width_mm=0.2,
                        pattern=StripePattern.LONGITUDINAL,
                        angle_deg=180.0,
                    ),
                ),
                conductor_material="Copper",
                manufacturer="Wire Bundler QA",
                part_number="QA-STRIPED-001",
            )
            set_harness_material_defaults(HARNESS_ID, materials, gateway)
            definition = loads(gateway.read_harness_definition(HARNESS_ID))
            wire = definition.wires[0]
            wire_group = WireGroupDefinition(
                WIRE_GROUP_ID,
                (wire.start_connection_id, wire.end_connection_id),
                definition.profiles[0].diameter_mm,
            )
            definition = replace(definition, wire_groups=(wire_group,))
            gateway.replace_harness_definition(HARNESS_ID, dumps(definition))
            if definition.wire_group_materials(wire_group) != materials:
                raise AssertionError("Generated-solid fixture did not resolve its materials.")

        with report.step("Generate grouped solid and component-owned stripes"):
            harness = gateway.harness_component(HARNESS_ID)
            if generate_wire_group_solids(design, harness, definition) != 1:
                raise AssertionError("Generated-solid fixture did not create exactly one group.")
            generated = generated_wire_group_occurrences(harness)
            if len(generated) != 1:
                raise AssertionError("Generated wire-group occurrence count is not one.")
            wire_occurrence = generated[0]
            component = wire_occurrence.component
            if component.bRepBodies.count != 1 or not component.bRepBodies.item(0).isSolid:
                raise AssertionError("Single-leg wire group does not own one solid body.")
            body = component.bRepBodies.item(0)
            if body.appearance is None:
                raise AssertionError("Generated wire-group body has no insulation appearance.")
            stripe_groups = tuple(
                group
                for group in component.customGraphicsGroups
                if group.id == f"{GENERATED_STRIPE_GROUP_ID}:{WIRE_GROUP_ID}"
            )
            if len(stripe_groups) != 1 or stripe_groups[0].count != 2:
                raise AssertionError("Generated component does not own both stripe meshes.")
            metadata_attribute = component.attributes.itemByName(
                "kev0.wire_bundler",
                GENERATED_WIRE_GROUP_ATTRIBUTE,
            )
            if metadata_attribute is None:
                raise AssertionError("Generated wire-group metadata is missing.")
            metadata = json.loads(metadata_attribute.value)
            if metadata.get("wire_group_id") != str(WIRE_GROUP_ID):
                raise AssertionError("Generated wire-group identity changed.")
            if len(metadata.get("stripes", ())) != 2:
                raise AssertionError("Generated metadata did not retain both stripes.")

        with report.step("Sweep a shared-profile three-leg junction in hybrid mode"):
            _verify_branched_group_profiles(design, replace(materials, stripes=()))

        with report.step("Move parent harness and verify generated body follows"):
            before_bodies = generated_wire_group_bodies(
                design.rootComponent, harness, (WIRE_GROUP_ID,)
            )
            if len(before_bodies) != 1:
                raise AssertionError("Could not resolve the generated root-context body.")
            before_center = _box_center(before_bodies[0].boundingBox)
            harness_occurrences = design.rootComponent.allOccurrencesByComponent(harness)
            if harness_occurrences.count != 1:
                raise AssertionError("Could not resolve one root harness occurrence.")
            harness_occurrence = harness_occurrences.item(0)
            if harness_occurrence is None:
                raise RuntimeError("Fusion did not expose the root harness occurrence.")
            transform = harness_occurrence.transform2
            transform.translation = adsk.core.Vector3D.create(*TRANSLATION_CM)
            harness_occurrence.transform2 = transform
            adsk.doEvents()
            application.activeViewport.refresh()
            after_bodies = generated_wire_group_bodies(
                design.rootComponent, harness, (WIRE_GROUP_ID,)
            )
            if len(after_bodies) != 1:
                raise AssertionError("Generated body disappeared after moving its harness.")
            after_center = _box_center(after_bodies[0].boundingBox)
            measured_translation = tuple(
                after - before for before, after in zip(before_center, after_center)
            )
            if any(
                abs(measured - expected) > 1e-6
                for measured, expected in zip(measured_translation, TRANSLATION_CM)
            ):
                raise AssertionError(
                    "Generated body did not follow its harness transform: "
                    f"measured={measured_translation}, expected={TRANSLATION_CM}."
                )
            if len(generated_wire_group_occurrences(harness)) != 1 or stripe_groups[0].count != 2:
                raise AssertionError("Transform separated generated geometry from its ownership.")

        with report.step("Rebuild grouped solid in Direct modeling mode"):
            design.designType = adsk.fusion.DesignTypes.DirectDesignType
            _verify_branched_group_profiles(design, replace(materials, stripes=()))
            if generate_wire_group_solids(design, harness, definition, True) != 1:
                raise AssertionError("Direct-mode rebuild did not create exactly one group.")
            direct_generated = generated_wire_group_occurrences(harness)
            if len(direct_generated) != 1:
                raise AssertionError("Direct-mode rebuild lost grouped output ownership.")
            direct_component = direct_generated[0].component
            if (
                direct_component.bRepBodies.count != 1
                or not direct_component.bRepBodies.item(0).isSolid
            ):
                raise AssertionError("Direct-mode single-leg rebuild did not retain one solid.")

        with report.step("Clear generated component and all owned presentation"):
            if clear_wire_solids(harness) != 1:
                raise AssertionError("Clear did not remove one generated wire-group component.")
            if generated_wire_group_occurrences(harness):
                raise AssertionError("Generated occurrence remained after clear.")
            if generated_wire_group_bodies(design.rootComponent, harness, (WIRE_GROUP_ID,)):
                raise AssertionError("Generated body remained after clear.")
            if direct_component.isValid:
                raise AssertionError("Generated direct-mode component remained valid after clear.")

        report.record_observation(
            "fusion.generatedSolids",
            {
                "wireGroupIdentity": str(WIRE_GROUP_ID),
                "solidBodyCount": 1,
                "branchedBodyCount": 3,
                "stripeMeshCount": 2,
                "appearanceAssigned": True,
                "translationCm": list(TRANSLATION_CM),
                "bodyFollowedHarness": True,
                "directModeRebuild": True,
                "clearRemovedOwnedPresentation": True,
            },
        )
    finally:
        if document is not None and document.isValid:
            with report.step("Close isolated generated-solid fixture"):
                if not document.close(False):
                    raise RuntimeError("Fusion did not close the generated-solid fixture.")
        if (
            previous_document is not None
            and previous_document.isValid
            and application.activeDocument != previous_document
            and not previous_document.activate()
        ):
            raise RuntimeError("Fusion did not restore the previously active document.")
        if application.documents.count != initial_document_count:
            raise AssertionError(
                "Generated-solid scenario changed the open document count: "
                f"before={initial_document_count}, after={application.documents.count}."
            )


def _verify_branched_group_profiles(
    design: adsk.fusion.Design,
    materials: WireMaterialSettings,
) -> None:
    """
    Verify three visual bodies reuse one profile plane without Boolean features.
    """
    occurrence = design.rootComponent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    if occurrence is None:
        raise RuntimeError("Fusion did not create the branched-junction fixture component.")
    hub = Vector3(0.0, 0.0, 0.0)
    routes = (
        _pass_through_route(
            UUID(int=8801),
            "Pass Through",
            Vector3(-10.0, 0.0, 0.0),
            hub,
            Vector3(10.0, 0.0, 0.0),
        ),
        _junction_route(UUID(int=8802), "Internal Lead", Vector3(-10.0, 5.0, 0.0), hub, -2.0),
    )
    try:
        group = WireGroupDefinition(UUID(int=8800), (UUID(int=8804), UUID(int=8805)), 2.0)
        build_wire_group_solid(
            occurrence.component,
            group,
            0,
            routes,
            adsk.core.Matrix3D.create(),
            HARNESS_ID,
            materials,
            design,
        )
        if occurrence.component.bRepBodies.count != 3:
            raise AssertionError("Branched junction did not retain its three sweep segments.")
        if occurrence.component.constructionPlanes.count != 1:
            raise AssertionError("Branched junction did not reuse one shared profile plane.")
        if occurrence.component.features.combineFeatures.count:
            raise AssertionError("Branched visual geometry unexpectedly created a Boolean feature.")
    finally:
        if occurrence.isValid and not occurrence.deleteMe():
            raise RuntimeError("Fusion could not remove the branched-junction fixture component.")


def _straight_route(
    route_id: UUID,
    label: str,
    start: Vector3,
    end: Vector3,
) -> RoutePreview:
    """
    Create one straight cubic leg with exact shared endpoint identity.
    """
    delta = Vector3(
        (end.x - start.x) / 3.0,
        (end.y - start.y) / 3.0,
        (end.z - start.z) / 3.0,
    )
    return RoutePreview(
        route_id,
        label,
        (start, end),
        (
            CubicBezier(
                start,
                Vector3(start.x + delta.x, start.y + delta.y, start.z + delta.z),
                Vector3(end.x - delta.x, end.y - delta.y, end.z - delta.z),
                end,
            ),
        ),
    )


def _junction_route(
    route_id: UUID,
    label: str,
    start: Vector3,
    end: Vector3,
    terminal_control_x: float,
) -> RoutePreview:
    """
    Create a curved branch with a terminal tangent on the shared junction axis.
    """
    return RoutePreview(
        route_id,
        label,
        (start, end),
        (
            CubicBezier(
                start,
                Vector3(start.x * 2.0 / 3.0, start.y, start.z),
                Vector3(terminal_control_x, end.y, end.z),
                end,
            ),
        ),
    )


def _pass_through_route(
    route_id: UUID,
    label: str,
    start: Vector3,
    junction: Vector3,
    end: Vector3,
) -> RoutePreview:
    """
    Create one logical route that must be split at an attached terminal lead.
    """
    left = _straight_route(route_id, label, start, junction).curves[0]
    right = _straight_route(route_id, label, junction, end).curves[0]
    return RoutePreview(route_id, label, (start, junction, end), (left, right))


def _box_center(box: adsk.core.BoundingBox3D) -> tuple[float, float, float]:
    """
    Return the center of a Fusion bounding box in internal centimeters.
    """
    return (
        (box.minPoint.x + box.maxPoint.x) / 2.0,
        (box.minPoint.y + box.maxPoint.y) / 2.0,
        (box.minPoint.z + box.maxPoint.z) / 2.0,
    )


def _require_application() -> adsk.core.Application:
    """
    Return the active Fusion application or reject standalone execution.
    """
    application = adsk.core.Application.get()
    if application is None:
        raise RuntimeError("Generated-solid verification must run inside Autodesk Fusion.")
    return application


def _log_to_fusion(message: str) -> None:
    """
    Mirror generated-solid progress into Fusion's application log.
    """
    adsk.core.Application.log(
        f"Wire Bundler generated solids: {message}",
        adsk.core.LogLevels.InfoLogLevel,
        adsk.core.LogTypes.FileLogType,
    )
