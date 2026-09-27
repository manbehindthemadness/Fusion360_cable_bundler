"""
Guarded local Fusion geometry naming from saved Interface contact metadata.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import AttachmentTargetKind, InterfaceContact


def _contact(identity: int, pin: str, value: str) -> InterfaceContact:
    """
    Create a persistent face contact with saved naming metadata.
    """
    return InterfaceContact(
        UUID(int=identity), AttachmentTargetKind.FACE, f"face-{identity}", value, pin
    )


@pytest.mark.parametrize(
    ("pin", "value", "expected"),
    [("1", "VCC", "Pin 1: VCC"), ("P7", "", "Pin P7"), ("", "GND", "GND")],
)
def test_local_name_uses_only_saved_fields(
    addin_module: object, pin: str, value: str, expected: str
) -> None:
    """
    Format both fields without consulting or rewriting their metadata.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_local_naming")
    assert module._local_name(_contact(1, pin, value)) == expected


def test_name_locals_writes_only_unique_editable_owners(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Skip shared, unresolved, unnamed, and non-writable targets across Interfaces.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_local_naming")
    contacts = (
        _contact(10, "1", "VCC"),
        _contact(11, "2", "GND"),
        _contact(12, "3", "NC"),
        _contact(13, "", ""),
        _contact(14, "4", "DATA"),
    )
    other = _contact(20, "5", "OTHER")
    interface = SimpleNamespace(interface_id=UUID(int=1), contacts=contacts)
    second = SimpleNamespace(interface_id=UUID(int=2), contacts=(other,))
    definition = SimpleNamespace(interfaces=(interface, second))
    gateway = SimpleNamespace(read_harness_definition=Mock(return_value="saved"))
    writable = SimpleNamespace(name="Body 1")
    shared = SimpleNamespace(name="Shared")
    owners = {
        contacts[0].contact_id: ("unique", writable),
        contacts[1].contact_id: ("shared", shared),
        contacts[2].contact_id: None,
        contacts[3].contact_id: ("unused", SimpleNamespace(name="Unused")),
        contacts[4].contact_id: ("no-name", SimpleNamespace()),
        other.contact_id: ("shared", shared),
    }
    monkeypatch.setitem(vars(module), "_require_active_design", lambda _application: object())
    monkeypatch.setitem(vars(module), "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setitem(vars(module), "loads", lambda _serialized: definition)
    monkeypatch.setitem(
        vars(module), "_resolved_owner", lambda _design, contact: owners[contact.contact_id]
    )

    notice = module.name_interface_contact_locals(object(), UUID(int=3), interface.interface_id, ())

    assert writable.name == "Pin 1: VCC"
    assert shared.name == "Shared"
    assert "Named 1 local geometries" in notice
    assert "1 shared geometry" in notice
    assert "1 unresolved or non-editable geometry" in notice
    assert "1 no Pin or Value" in notice
    assert "1 no writable name" in notice
    with pytest.raises(ValueError, match="invalid contact identity"):
        module.name_interface_contact_locals(
            object(), UUID(int=3), interface.interface_id, (UUID(int=99),)
        )


def test_local_owner_rejects_referenced_or_ambiguous_geometry(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A face in a linked component or a split token cannot be renamed.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_local_naming")
    owner = SimpleNamespace(entityToken="body", name="Body")
    occurrence = SimpleNamespace(isReferencedComponent=True)
    entity = SimpleNamespace(body=owner, assemblyContext=occurrence)
    contact = _contact(10, "1", "VCC")
    monkeypatch.setitem(vars(module), "resolve_contact_entities", lambda _design, _token: (entity,))
    monkeypatch.setitem(
        vars(module), "attachment_target_kind", lambda _entity: AttachmentTargetKind.FACE
    )
    assert module._resolved_owner(object(), contact) is None
    occurrence.isReferencedComponent = False
    assert module._resolved_owner(object(), contact) == ("body", owner)
    monkeypatch.setitem(
        vars(module), "resolve_contact_entities", lambda _design, _token: (entity, entity)
    )
    assert module._resolved_owner(object(), contact) is None

    def unavailable(_design: object, _token: str) -> tuple[object, ...]:
        """
        Simulate a stale Fusion token without aborting the naming pass.
        """
        raise RuntimeError("stale proxy")

    monkeypatch.setitem(vars(module), "resolve_contact_entities", unavailable)
    assert module._resolved_owner(object(), contact) is None


def test_name_owner_uses_the_geometry_name_exposed_by_fusion(addin_module: object) -> None:
    """
    Faces name their body, sketch targets their sketch, and points themselves.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_local_naming")
    body = object()
    sketch = object()
    entity = SimpleNamespace(body=body, parentSketch=sketch)
    assert module._name_owner(entity, AttachmentTargetKind.FACE) is body
    assert module._name_owner(entity, AttachmentTargetKind.CIRCULAR_EDGE) is body
    assert module._name_owner(entity, AttachmentTargetKind.PROFILE) is sketch
    assert module._name_owner(entity, AttachmentTargetKind.SKETCH_POINT) is sketch
    assert module._name_owner(entity, AttachmentTargetKind.JOINT_ORIGIN) is entity


def test_name_locals_skips_rejected_write_without_changing_other_contacts(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Fusion name-setter failures remain skips rather than aborting the batch.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_local_naming")

    class RejectedName:
        """
        Mimic a Fusion owner whose name setter refuses an edit.
        """

        @property
        def name(self) -> str:
            """
            Return its unchanged current name.
            """
            return "Existing"

        @name.setter
        def name(self, _value: str) -> None:
            """
            Simulate a host-side read-only naming boundary.
            """
            raise RuntimeError("read-only")

    contacts = (_contact(10, "1", "VCC"), _contact(11, "2", "GND"))
    interface = SimpleNamespace(interface_id=UUID(int=1), contacts=contacts)
    gateway = SimpleNamespace(read_harness_definition=Mock(return_value="saved"))
    untouched = SimpleNamespace(name="Untouched")
    owners = {
        contacts[0].contact_id: ("rejected", RejectedName()),
        contacts[1].contact_id: ("other", untouched),
    }
    monkeypatch.setitem(vars(module), "_require_active_design", lambda _application: object())
    monkeypatch.setitem(vars(module), "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setitem(
        vars(module), "loads", lambda _serialized: SimpleNamespace(interfaces=(interface,))
    )
    monkeypatch.setitem(
        vars(module), "_resolved_owner", lambda _design, contact: owners[contact.contact_id]
    )

    notice = module.name_interface_contact_locals(
        object(), UUID(int=3), interface.interface_id, (contacts[0].contact_id,)
    )

    assert "1 name write rejected" in notice
    assert untouched.name == "Untouched"
