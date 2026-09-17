"""
Verify external harness placement and persistence in an Assembly design.

The scenario owns both cloud files it creates and deletes them during mandatory
cleanup. Run it only inside Fusion through its registered runner or the QA suite.
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

ADDIN_ROOT = Path(__file__).resolve().parent.parent
if str(ADDIN_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDIN_ROOT))

# noinspection PyUnresolvedReferences
import adsk.core  # noqa: E402

# noinspection PyUnresolvedReferences
import adsk.fusion  # noqa: E402

from experiments.experiment_command_history import _create_circular_profile  # noqa: E402
from experiments.experiment_preview_reload import (  # noqa: E402
    _delete_temporary_data_file,
    _wait_for_cloud_processing,
)
from experiments.scenario_report import ScenarioReport  # noqa: E402
from wire_bundler.application import (  # noqa: E402
    add_pathway,
    add_wire_batch,
    create_empty_harness,
)
from wire_bundler.domain import (  # noqa: E402
    RoutingMode,
    WireGroupDefinition,
    dumps,
    loads,
)
from wire_bundler.fusion import FusionHarnessGateway  # noqa: E402
from wire_bundler.fusion.wire_solids import (  # noqa: E402
    generate_wire_group_solids,
    generated_wire_group_occurrences,
)

SCENARIO_NAME = "assembly_placement"
ARTIFACT_ROOT = ADDIN_ROOT / "artifacts" / "verification"
HARNESS_ID = UUID("7a000000-0000-0000-0000-000000000001")
CONTROL_ID = UUID("7a000000-0000-0000-0000-000000000011")
PATHWAY_ID = UUID("7a000000-0000-0000-0000-000000000012")
PROFILE_ID = UUID("7a000000-0000-0000-0000-000000000013")
SOURCE_CONNECTION_ID = UUID("7a000000-0000-0000-0000-000000000014")
DESTINATION_CONNECTION_ID = UUID("7a000000-0000-0000-0000-000000000015")
WIRE_ID = UUID("7a000000-0000-0000-0000-000000000016")
WIRE_GROUP_ID = UUID("7a000000-0000-0000-0000-000000000017")


def run(_context: object) -> None:
    """
    Run the disposable Assembly placement scenario and display its result.
    """
    report = ScenarioReport(SCENARIO_NAME, ARTIFACT_ROOT, _log_to_fusion)
    application: Optional[adsk.core.Application] = None
    try:
        application = _require_application()
        verify_assembly_placement(application, report)
        report.finish(True)
        application.userInterface.messageBox(
            "Assembly placement verification passed.\n\n"
            "The disposable parent and external harness files were deleted.\n"
            f"Log: {report.log_path}\nReport: {report.json_path}",
            "Wire Bundler Assembly Placement",
        )
    except (AssertionError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
        failure = traceback.format_exc()
        report.finish(False, failure)
        if application is not None and application.userInterface is not None:
            application.userInterface.messageBox(
                "Assembly placement verification failed.\n\n"
                f"Log: {report.log_path}\nReport: {report.json_path}\n\n{failure}",
                "Wire Bundler Assembly Placement",
            )


def verify_assembly_placement(
    application: adsk.core.Application,
    report: ScenarioReport,
) -> None:
    """
    Create, save, reopen, validate, and delete one external harness fixture.
    """
    previous_document = application.activeDocument
    initial_document_count = application.documents.count
    parent_document: Optional[adsk.core.Document] = None
    parent_data_file: Optional[adsk.core.DataFile] = None
    child_data_file: Optional[adsk.core.DataFile] = None
    suffix = uuid4().hex[:12]
    parent_name = f"WB_QA_Assembly_{suffix}"
    harness_name = f"WB_QA_External_Harness_{suffix}"
    try:
        with report.step("Create isolated Assembly design"):
            active_folder = application.data.activeFolder
            if active_folder is None:
                raise RuntimeError("Fusion has no active cloud folder for disposable QA data.")
            parent_document = application.documents.add(
                adsk.core.DocumentTypes.FusionDesignDocumentType
            )
            if parent_document is None:
                raise RuntimeError("Fusion did not create the Assembly fixture.")
            design = adsk.fusion.Design.cast(application.activeProduct)
            if design is None:
                raise RuntimeError("Fusion did not activate the Assembly fixture.")
            design.designIntent = adsk.fusion.DesignIntentTypes.AssemblyDesignIntentType

        with report.step("Create unsaved external harness component"):
            gateway = FusionHarnessGateway(design, active_folder)
            definition = create_empty_harness(
                harness_name,
                RoutingMode.ROUTING_GATES,
                gateway,
                id_factory=lambda: HARNESS_ID,
            )
            if definition.harness_id != HARNESS_ID:
                raise AssertionError("External harness identity was not preserved.")
            if design.rootComponent.occurrences.count != 1:
                raise AssertionError("Assembly did not contain exactly one harness occurrence.")
            occurrence = design.rootComponent.occurrences.item(0)
            if occurrence is None or not occurrence.isReferencedComponent:
                raise AssertionError("Harness occurrence is not an external reference.")
            stored = gateway.list_stored_harnesses()
            if len(stored) != 1 or loads(stored[0].serialized_definition).harness_id != HARNESS_ID:
                raise AssertionError("External harness metadata was not discoverable before save.")

        with report.step("Generate grouped geometry inside external harness"):
            harness_component = gateway.harness_component(HARNESS_ID)
            source = _create_circular_profile(
                harness_component, 0.0, 0.0, 0.0, 0.12, "QA External Source"
            )
            gate = _create_circular_profile(
                harness_component, 5.0, 0.0, 0.0, 0.8, "QA External Gate"
            )
            destination = _create_circular_profile(
                harness_component, 10.0, 0.0, 0.0, 0.12, "QA External Destination"
            )
            pathway_ids = iter((CONTROL_ID, PATHWAY_ID))
            add_pathway(
                HARNESS_ID,
                "QA External Pathway",
                RoutingMode.ROUTING_GATES,
                (gate.entityToken,),
                gateway,
                id_factory=lambda: next(pathway_ids),
            )
            wire_ids = iter((PROFILE_ID, SOURCE_CONNECTION_ID, DESTINATION_CONNECTION_ID, WIRE_ID))
            add_wire_batch(
                HARNESS_ID,
                PATHWAY_ID,
                (source.entityToken,),
                (destination.entityToken,),
                1.0,
                gateway,
                id_factory=lambda: next(wire_ids),
            )
            routed_definition = loads(gateway.read_harness_definition(HARNESS_ID))
            wire = routed_definition.wires[0]
            grouped_definition = replace(
                routed_definition,
                wire_groups=(
                    WireGroupDefinition(
                        WIRE_GROUP_ID,
                        (wire.start_connection_id, wire.end_connection_id),
                        routed_definition.profiles[0].diameter_mm,
                    ),
                ),
            )
            gateway.replace_harness_definition(HARNESS_ID, dumps(grouped_definition))
            if (
                generate_wire_group_solids(
                    design,
                    harness_component,
                    grouped_definition,
                )
                != 1
            ):
                raise AssertionError("Assembly harness did not generate one grouped solid.")
            generated = generated_wire_group_occurrences(harness_component)
            if len(generated) != 1 or generated[0].component.bRepBodies.count != 1:
                raise AssertionError("Assembly harness did not own its single routed body.")

        with report.step("Save parent and external harness files"):
            if not parent_document.saveAs(
                parent_name,
                active_folder,
                "Wire Bundler automated Assembly placement verification",
                "wire-bundler-qa",
            ):
                raise RuntimeError("Fusion declined to save the Assembly fixture.")
            fusion_document = adsk.fusion.FusionDocument.cast(parent_document)
            if fusion_document is None or fusion_document.dataFile is None:
                raise RuntimeError("Saved Assembly fixture has no cloud DataFile.")
            parent_data_file = fusion_document.dataFile
            _wait_for_cloud_processing(parent_data_file)
            child_references = parent_data_file.childReferences
            if child_references.count != 1:
                raise AssertionError(
                    "Saved Assembly did not reference exactly one external harness file."
                )
            child_data_file = child_references.item(0)
            if child_data_file is None:
                raise RuntimeError("Fusion did not expose the saved external harness DataFile.")
            _wait_for_cloud_processing(child_data_file)
            if child_data_file.name != harness_name:
                raise AssertionError(
                    f"External harness file is named {child_data_file.name!r}, "
                    f"expected {harness_name!r}."
                )

        with report.step("Close and reopen parent Assembly"):
            if not parent_document.close(False):
                raise RuntimeError("Fusion did not close the saved Assembly fixture.")
            parent_document = None
            reopened_document = application.documents.open(parent_data_file, True)
            if reopened_document is None:
                raise RuntimeError("Fusion did not reopen the Assembly fixture.")
            parent_document = reopened_document
            reopened_design = adsk.fusion.Design.cast(application.activeProduct)
            if reopened_design is None:
                raise RuntimeError("Reopened Assembly fixture is not a Fusion design.")
            if (
                reopened_design.designIntent
                != adsk.fusion.DesignIntentTypes.AssemblyDesignIntentType
            ):
                raise AssertionError("Reopened design did not retain Assembly intent.")

        with report.step("Validate reopened external harness"):
            if reopened_design.rootComponent.occurrences.count != 1:
                raise AssertionError("Reopened Assembly lost its external harness occurrence.")
            reopened_occurrence = reopened_design.rootComponent.occurrences.item(0)
            if reopened_occurrence is None or not reopened_occurrence.isReferencedComponent:
                raise AssertionError("Reopened harness occurrence is not externally referenced.")
            reopened_gateway = FusionHarnessGateway(reopened_design, active_folder)
            reopened_stored = reopened_gateway.list_stored_harnesses()
            if len(reopened_stored) != 1:
                raise AssertionError(
                    f"Expected one reopened harness, found {len(reopened_stored)}."
                )
            reopened_definition = loads(reopened_stored[0].serialized_definition)
            if reopened_definition.harness_id != HARNESS_ID:
                raise AssertionError("Reopened external harness identity changed.")
            reopened_harness = reopened_gateway.harness_component(HARNESS_ID)
            reopened_generated = generated_wire_group_occurrences(reopened_harness)
            if len(reopened_generated) != 1:
                raise AssertionError("Reopened external harness lost grouped geometry.")

        report.record_observation(
            "fusion.assemblyPlacement",
            {
                "assemblyIntentPersisted": True,
                "externalOccurrencePersisted": True,
                "externalHarnessIdentityPersisted": True,
                "externalGroupedGeometryPersisted": True,
                "parentChildReferenceCount": 1,
            },
        )
    finally:
        if parent_document is not None and parent_document.isValid:
            with report.step("Close disposable Assembly document"):
                if not parent_document.close(False):
                    raise RuntimeError("Fusion did not close the disposable Assembly document.")
        if parent_data_file is not None and parent_data_file.isValid:
            with report.step("Delete disposable parent Assembly DataFile"):
                _delete_temporary_data_file(parent_data_file)
        if child_data_file is not None and child_data_file.isValid:
            with report.step("Delete disposable external harness DataFile"):
                _delete_temporary_data_file(child_data_file)
        if (
            previous_document is not None
            and previous_document.isValid
            and application.activeDocument != previous_document
            and not previous_document.activate()
        ):
            raise RuntimeError("Fusion did not restore the previously active document.")
        if application.documents.count != initial_document_count:
            raise AssertionError(
                "Assembly placement changed the open document count: "
                f"before={initial_document_count}, after={application.documents.count}."
            )


def _require_application() -> adsk.core.Application:
    """
    Return the active Fusion application or reject standalone execution.
    """
    application = adsk.core.Application.get()
    if application is None:
        raise RuntimeError("Assembly placement verification must run inside Autodesk Fusion.")
    return application


def _log_to_fusion(message: str) -> None:
    """
    Mirror Assembly placement progress into Fusion's application log.
    """
    adsk.core.Application.log(
        f"Wire Bundler Assembly placement: {message}",
        adsk.core.LogLevels.InfoLogLevel,
        adsk.core.LogTypes.FileLogType,
    )
