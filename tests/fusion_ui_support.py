"""Shared Fusion UI test doubles, fixtures, and deterministic helpers."""

# ruff: noqa: F401

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import CodeType, ModuleType, SimpleNamespace
from typing import Any, Protocol, cast
from unittest.mock import Mock
from uuid import UUID

import pytest

from wire_bundler.application import HarnessLoadResult
from wire_bundler.domain import (
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    PathwayEndpoint,
    RefineGeometry,
    StandaloneEndDefinition,
    WireColor,
    WireStripe,
    dumps,
    loads,
)
from wire_bundler.routing import GateFrame, Vector3

REFINE_ID = UUID("30000000-0000-0000-0000-000000000099")

__all__ = (
    "Any",
    "Callable",
    "ControlKind",
    "ControlStructure",
    "GateFrame",
    "HarnessDefinition",
    "HarnessLoadResult",
    "JunctionDefinition",
    "JunctionPathwayRelationship",
    "Mock",
    "ModuleType",
    "Path",
    "PathwayEndpoint",
    "Protocol",
    "REFINE_ID",
    "RefineGeometry",
    "SimpleNamespace",
    "StandaloneEndDefinition",
    "UUID",
    "Vector3",
    "WireColor",
    "WireStripe",
    "_PaletteLifecycleModule",
    "_configure_relationship_selector_casts",
    "_configure_save_test",
    "_refine_control",
    "cast",
    "dumps",
    "importlib",
    "json",
    "loads",
    "pytest",
    "replace",
    "sys",
)


class _RefinePlacementResult(Protocol):
    """
    Describe the placement fields asserted by lifecycle tests.
    """

    insertion_index: int
    geometry: RefineGeometry


class _PaletteLifecycleModule(Protocol):
    """
    Describe the private lifecycle surface exercised by this regression test.
    """

    _runtime: Any
    ADD_WIRES_COMMAND_ID: str
    COMMAND_ID: str
    COMMAND_SPECS: tuple[Any, ...]
    PendingSlot: type
    UiRuntime: type
    PALETTE_RESOURCE_FILES: tuple[Path, ...]
    JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID: str
    JUNCTION_RELATIONSHIP_CHOICE_INPUT_ID: str
    STANDALONE_END_GUIDES_INPUT_ID: str
    STANDALONE_END_BOUNDARY_INPUT_ID: str
    _PaletteIncomingHandler: type
    _PaletteEditExecuteHandler: type
    _PaletteEditDestroyedHandler: type
    _PaletteEditCreatedHandler: type
    _HistoryChangedHandler: type
    _DocumentSavingHandler: type
    _DocumentSavedHandler: type
    _open_palette_edit: Callable[[object, str, str], None]
    _apply_palette_edit: Callable[[object, str, str], str]
    _refresh_active_preview: Callable[..., str]
    _reconcile_active_refines: Callable[[object], None]
    reconcile_active_refines: Callable[[object], None]
    remove_junction: Callable[..., None]
    remove_pathway: Callable[..., None]
    _apply_generated_materials: Callable[[object, UUID], str]
    _send_palette_state: Callable[[object, str], None]
    reconcile_preview_history: Callable[[object, tuple[HarnessDefinition, ...]], None]
    _ShowPaletteCreatedHandler: type
    _RefineCommandState: type
    _AddJunctionCommandState: type
    _AddJunctionPreSelectHandler: type
    _AddJunctionRelationshipCommandState: type
    _AddJunctionRelationshipInputChangedHandler: type
    _AddStandaloneEndCommandState: type
    _AddStandaloneEndPreSelectHandler: type
    _JunctionRelationshipCandidate: type
    _SegmentCommandState: type
    _SegmentPreSelectHandler: type
    _RefinePreSelectHandler: type
    _RefineMouseDragHandler: type
    _RefineActiveSelectionHandler: type
    _EditRefineCommandState: type
    _EditRefineDestroyedHandler: type
    _EditRefineInputChangedHandler: type
    _EditRefineExecutePreviewHandler: type
    _read_refine_placement: Callable[[object, object], _RefinePlacementResult]
    _junction_profile_token: Callable[[object, object], str]
    _read_junction_relationship_candidate: Callable[[object, object], Any]
    _update_junction_relationship_choices: Callable[[object, object], None]
    _read_standalone_end_inputs: Callable[[object, object], tuple[tuple[str, ...], Any]]
    _open_add_junction_command: Callable[[object, str], None]
    _open_add_junction_relationship_command: Callable[[object, str], None]
    _update_refine_placement: Callable[..., None]
    _refine_geometry_transform: Callable[[RefineGeometry], object]
    _add_refine_transform_input: Callable[[object, RefineGeometry], object]
    _read_edited_refine_geometry: Callable[[object], RefineGeometry]
    _preview_edited_refine: Callable[[object, object], None]
    draw_candidate_refine: Callable[[object, RefineGeometry], object]
    draw_refine_editor: Callable[[object, UUID, RefineGeometry], object]
    update_candidate_refine: Callable[[object, RefineGeometry], None]
    update_refine_editor: Callable[[object, RefineGeometry], None]
    PathwaySpine: type
    REFINE_SPINE_ENTITY_ID: str
    REFINE_GRAPHICS_GROUP_ID: str
    _show_palette: Callable[[object], None]
    _create_harness_gateway: Callable[[object], object]
    remove_standalone_end: Callable[[UUID, UUID, object], None]
    rename_standalone_end: Callable[[UUID, UUID, str, object], None]
    serialize_palette_state: Callable[[object, str], str]
    _delete_damaged_harness: Callable[[object, str], str]
    _appearance_libraries_payload: Callable[[object], list[dict[str, str]]]
    _library_appearances_payload: Callable[[object, str], list[dict[str, str]]]
    _preview_routes: Callable[[object, str], int]
    _generate_solids: Callable[[object, str], int]
    _clear_preview: Callable[[object], int]
    _clear_highlight: Callable[[object], None]
    _clear_solids: Callable[[object, str], int]
    clear_route_previews: Callable[[object], int]
    clear_refine_spine: Callable[[object], None]
    clear_wire_solids: Callable[[object], int]
    generated_wire_bodies: Callable[..., tuple[object, ...]]
    has_refine_graphics: Callable[[object], bool]
    has_route_previews: Callable[[object], bool]
    show_route_previews: Callable[..., tuple[object, ...]]
    refresh_route_previews: Callable[..., tuple[str, ...]]
    _log_to_fusion: Callable[[str], None]
    _member_entity_tokens: Callable[[HarnessDefinition, str, UUID], tuple[str, ...]]
    _highlight_member: Callable[[object, str], int]
    _require_active_design: Callable[[object], object]
    highlight_route_preview: Callable[[object, object], int]
    highlight_route_members: Callable[[object, tuple[UUID, ...]], int]
    highlight_refine_graphics: Callable[[object, tuple[UUID, ...]], int]
    load_harnesses: Callable[[object], tuple[HarnessLoadResult, ...]]


def _nested_code_names(code: CodeType) -> set[str]:
    """
    Collect names referenced by a test and its nested lambdas.
    """
    names = set(code.co_names)
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            names.update(_nested_code_names(constant))
    return names


@pytest.fixture
def addin_module(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> _PaletteLifecycleModule:
    """
    Import the lifecycle module against minimal Fusion handler stubs.
    """
    adsk_module = ModuleType("adsk")
    core_module = ModuleType("adsk.core")
    fusion_module = ModuleType("adsk.fusion")
    handler_names = (
        "CommandEventHandler",
        "ApplicationCommandEventHandler",
        "ActiveSelectionEventHandler",
        "DocumentEventHandler",
        "InputChangedEventHandler",
        "MouseEventHandler",
        "SelectionEventHandler",
        "ValidateInputsEventHandler",
        "CommandCreatedEventHandler",
        "HTMLEventHandler",
        "NavigationEventHandler",
    )
    for handler_name in handler_names:
        setattr(core_module, handler_name, type(handler_name, (), {}))
    core_module.PaletteDockingStates = SimpleNamespace(  # type: ignore[attr-defined]
        PaletteDockStateRight="right"
    )
    core_module.PaletteDockingOptions = SimpleNamespace(  # type: ignore[attr-defined]
        PaletteDockOptionsToVerticalOnly="vertical"
    )
    adsk_module.core = core_module  # type: ignore[attr-defined]
    adsk_module.fusion = fusion_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "adsk", adsk_module)
    monkeypatch.setitem(sys.modules, "adsk.core", core_module)
    monkeypatch.setitem(sys.modules, "adsk.fusion", fusion_module)
    for module_name in tuple(sys.modules):
        if module_name.startswith("wire_bundler.fusion.ui"):
            sys.modules.pop(module_name, None)

    module_names = (
        "wire_bundler.fusion.ui.lifecycle",
        "wire_bundler.fusion.ui.palette",
        "wire_bundler.fusion.ui.palette_state",
        "wire_bundler.fusion.ui.viewport",
        "wire_bundler.fusion.ui.edits",
        "wire_bundler.fusion.ui.launchers",
        "wire_bundler.fusion.ui.registration",
        "wire_bundler.fusion.ui.runtime",
        "wire_bundler.fusion.ui.commands.harness",
        "wire_bundler.fusion.ui.commands.pathways",
        "wire_bundler.fusion.ui.commands.junctions",
        "wire_bundler.fusion.ui.commands.ends",
        "wire_bundler.fusion.ui.commands.refines",
        "wire_bundler.fusion.ui.commands.wires",
    )
    modules = tuple(importlib.import_module(name) for name in module_names)
    requested_names = _nested_code_names(request.function.__code__)

    def ownership_score(candidate: ModuleType) -> tuple[int, int]:
        owned = sum(
            1
            for name in requested_names
            if getattr(getattr(candidate, name, None), "__module__", None) == candidate.__name__
        )
        available = sum(name in vars(candidate) for name in requested_names)
        return owned, available

    module = max(modules, key=ownership_score)
    return cast(_PaletteLifecycleModule, cast(object, module))


def _refine_control(radius_mm: float = 10.0) -> ControlStructure:
    """
    Build one deterministic persisted refine for lifecycle-boundary tests.
    """
    return ControlStructure(
        REFINE_ID,
        "Refine Point 01",
        ControlKind.REFINE,
        "",
        refine_geometry=RefineGeometry(
            (1.0, 2.0, 3.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), radius_mm
        ),
    )


def _configure_save_test(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    has_preview: bool,
) -> tuple[SimpleNamespace, SimpleNamespace]:
    """
    Configure one document save with a controllable live-preview result.
    """
    preview_design = object()
    document = SimpleNamespace(
        products=SimpleNamespace(itemByProductType=lambda _product_type: preview_design)
    )
    compatibility = SimpleNamespace(isCacheGraphicsOnDocumentSave=True)
    application = SimpleNamespace(
        preferences=SimpleNamespace(compatibilityPreferences=compatibility)
    )
    core_module = sys.modules["adsk.core"]
    fusion_module = sys.modules["adsk.fusion"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    fusion_module.Design = SimpleNamespace(cast=lambda product: product)  # type: ignore[attr-defined]
    monkeypatch.setattr(addin_module, "has_route_previews", lambda _design: has_preview)
    monkeypatch.setattr(addin_module, "has_refine_graphics", lambda _design: False)
    module_runtime = vars(addin_module)["_runtime"]
    module_runtime.graphics_cache_restore_value = None
    module_runtime.graphics_cache_save_document = None
    return document, compatibility


def _configure_relationship_selector_casts() -> None:
    """
    Make command-input and profile casts transparent for selector tests.
    """
    core_module = sys.modules["adsk.core"]
    fusion_module = sys.modules["adsk.fusion"]
    core_module.SelectionCommandInput = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda value: value
    )
    core_module.DropDownCommandInput = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda value: value
    )
    fusion_module.Profile = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
