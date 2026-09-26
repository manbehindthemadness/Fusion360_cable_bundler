"""
Bounded native-reference caching, invalidation, and release regressions.
"""

import gc
import importlib
import json
import sys
import weakref
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest


def test_contact_cache_reuses_valid_results_and_releases_evicted_proxies(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Prove lookup reuse, strict capacity, design scoping, and explicit reference release.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_cache")
    module.clear_contact_resolutions()
    monkeypatch.setitem(vars(module), "MAX_CONTACT_RESOLUTIONS", 2)

    class Entity:
        """
        Provide weak-referenceable native-like validity without retaining a design.
        """

        isValid = True

    references = []

    def resolve(_token: str) -> tuple[Entity, ...]:
        """
        Track only weak references so the test observes actual cache ownership.
        """
        entity = Entity()
        references.append(weakref.ref(entity))
        return (entity,)

    resolver = Mock(side_effect=resolve)
    design = SimpleNamespace(
        rootComponent=SimpleNamespace(entityToken="design-a"), findEntityByToken=resolver
    )
    try:
        module.resolve_contact_entities(design, "a")
        module.resolve_contact_entities(design, "a")
        assert resolver.call_count == 1
        module.resolve_contact_entities(design, "b")
        module.resolve_contact_entities(design, "c")
        gc.collect()
        assert references[0]() is None
        assert len(module._entries) == 2
        module.resolve_contact_entities(design, "c")[0].isValid = False
        module.resolve_contact_entities(design, "c")
        assert resolver.call_count == 4
        design.rootComponent.entityToken = "design-b"
        module.resolve_contact_entities(design, "a")
        assert len(module._entries) == 1
        module.clear_contact_resolutions()
        gc.collect()
        assert all(reference() is None for reference in references)
    finally:
        module.clear_contact_resolutions()


@pytest.mark.parametrize(
    "command, invalidates",
    [
        ("MoveCommand", True),
        ("UndoCommand", True),
        ("kev0_cable_bundler_harness_builder_set_interface_contact_name", False),
        ("kev0_cable_bundler_select_interface_contacts", False),
    ],
)
def test_contact_cache_lifecycle_invalidation(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    invalidates: bool,
) -> None:
    """
    Keep metadata-only reuse but release native proxies on edits and document transitions.
    """
    cache = importlib.import_module("cable_bundler.fusion.interface_contact_cache")
    lifecycle = importlib.import_module("cable_bundler.fusion.ui.lifecycle")
    monkeypatch.setitem(
        vars(sys.modules["adsk.core"]),
        "Application",
        SimpleNamespace(get=lambda: SimpleNamespace(activeProduct=None)),
    )
    monkeypatch.setitem(
        vars(sys.modules["adsk.fusion"]), "Design", SimpleNamespace(cast=lambda _: None)
    )
    design = SimpleNamespace(rootComponent=SimpleNamespace(entityToken="design"))
    entity = SimpleNamespace(entityToken="face", isValid=True)
    cache.remember_contact_entity(design, entity)
    lifecycle._HistoryChangedHandler().notify(SimpleNamespace(commandId=command))
    assert bool(cache._entries) is not invalidates
    lifecycle._ContactDocumentChangedHandler().notify(SimpleNamespace())
    assert not cache._entries


def test_contact_geometry_dispatch_limits_work_to_requested_batch(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Resolve only requested contacts, and reject oversized geometry batches.
    """
    module = importlib.import_module("cable_bundler.fusion.ui.palette")
    interface_id = UUID(int=2)
    contacts = tuple(SimpleNamespace(contact_id=UUID(int=i + 10)) for i in range(12))
    interface = SimpleNamespace(interface_id=interface_id, contacts=contacts)
    monkeypatch.setitem(
        vars(module),
        "_create_harness_gateway",
        lambda _: SimpleNamespace(read_harness_definition=lambda _: "definition"),
    )
    monkeypatch.setitem(vars(module), "loads", lambda _: SimpleNamespace(interfaces=(interface,)))
    monkeypatch.setitem(vars(module), "_require_active_design", lambda _: "design")
    project = Mock(side_effect=lambda _design, contact: {"contactId": str(contact.contact_id)})
    monkeypatch.setitem(vars(module), "project_interface_contact", project)
    describe = Mock(return_value={"reason": "eligible", "snapshot": "missing"})
    monkeypatch.setitem(vars(module), "describe_interface_contact_cache", describe)
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(interface_id),
        "contactIds": [str(contacts[2].contact_id)],
        "diagnostics": True,
        "diagnosticFirstBatch": True,
    }
    application = object()
    result = json.loads(
        module._dispatch_palette_action(application, "get_interface_contacts", json.dumps(payload))
    )
    assert result["contacts"] == [{"contactId": str(contacts[2].contact_id)}]
    assert result["cacheBefore"] == describe.return_value
    assert result["cacheStats"] == {"hits": 0, "misses": 1}
    assert isinstance(result["serverMs"], int)
    describe.assert_called_once_with(application, UUID(int=1), interface_id)
    project.assert_called_once_with("design", contacts[2])
    payload["contactIds"] = [str(item.contact_id) for item in contacts]
    with pytest.raises(ValueError, match="eight"):
        module._dispatch_palette_action(object(), "get_interface_contacts", json.dumps(payload))


def test_complete_cache_dispatch_reads_all_contacts_once(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The warm diagram path avoids one Fusion gateway read per eight contacts.
    """
    module = importlib.import_module("cable_bundler.fusion.ui.palette")
    interface_id = UUID(int=2)
    contacts = tuple(SimpleNamespace(contact_id=UUID(int=index + 10)) for index in range(24))
    interface = SimpleNamespace(interface_id=interface_id, contacts=contacts)
    read_definition = Mock(return_value="definition")
    monkeypatch.setitem(
        vars(module),
        "_create_harness_gateway",
        lambda _application: SimpleNamespace(read_harness_definition=read_definition),
    )
    monkeypatch.setitem(
        vars(module), "loads", lambda _value: SimpleNamespace(interfaces=(interface,))
    )
    projection = Mock(return_value=[{"contactId": str(item.contact_id)} for item in contacts])
    monkeypatch.setitem(vars(module), "read_complete_cached_contacts", projection)
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(interface_id),
        "contactIds": [str(item.contact_id) for item in contacts],
    }

    result = json.loads(
        module._dispatch_palette_action(
            object(), "get_interface_contacts_cached", json.dumps(payload)
        )
    )

    assert result["cacheComplete"] is True
    assert len(result["contacts"]) == 24
    assert isinstance(result["serverMs"], int)
    read_definition.assert_called_once_with(UUID(int=1))
    projection.assert_called_once()


def test_rebuild_dispatch_clears_current_interface_and_native_references(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A manual rebuild clears both persistence layers before the next batch.
    """
    module = importlib.import_module("cable_bundler.fusion.ui.palette")
    interface_id = UUID(int=2)
    harness_id = UUID(int=1)
    interface = SimpleNamespace(interface_id=interface_id)
    monkeypatch.setitem(
        vars(module),
        "_create_harness_gateway",
        lambda _: SimpleNamespace(read_harness_definition=lambda _: "definition"),
    )
    monkeypatch.setitem(vars(module), "loads", lambda _: SimpleNamespace(interfaces=(interface,)))
    clear_disk = Mock(return_value=True)
    clear_native = Mock()
    monkeypatch.setitem(vars(module), "clear_interface_contact_snapshot", clear_disk)
    monkeypatch.setitem(vars(module), "clear_contact_resolutions", clear_native)
    monkeypatch.setitem(vars(module), "disk_cache_available", lambda *_: True)
    application = object()

    result = json.loads(
        module._dispatch_palette_action(
            application,
            "rebuild_interface_contacts_cache",
            json.dumps({"harnessId": str(harness_id), "interfaceId": str(interface_id)}),
        )
    )

    assert result == {"ok": True, "diskCacheAvailable": True, "diskCacheCleared": True}
    clear_disk.assert_called_once_with(application, harness_id, interface_id)
    clear_native.assert_called_once_with()

    clear_disk.side_effect = PermissionError("denied")
    with pytest.raises(RuntimeError, match="Could not clear"):
        module._dispatch_palette_action(
            application,
            "rebuild_interface_contacts_cache",
            json.dumps({"harnessId": str(harness_id), "interfaceId": str(interface_id)}),
        )
    clear_native.assert_called_once_with()


def test_cache_status_dispatch_reports_read_only_diagnostics(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The palette can inspect cache eligibility without resolving any contacts.
    """
    module = importlib.import_module("cable_bundler.fusion.ui.palette")
    application = object()
    harness_id = UUID(int=1)
    interface_id = UUID(int=2)
    describe = Mock(
        return_value={"reason": "document has unsaved changes", "snapshot": "unavailable"}
    )
    monkeypatch.setitem(vars(module), "describe_interface_contact_cache", describe)

    result = json.loads(
        module._dispatch_palette_action(
            application,
            "get_interface_contact_cache_status",
            json.dumps({"harnessId": str(harness_id), "interfaceId": str(interface_id)}),
        )
    )

    assert result["cache"] == describe.return_value
    describe.assert_called_once_with(application, harness_id, interface_id)
