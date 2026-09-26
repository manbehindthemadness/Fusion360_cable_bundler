"""
Live source fingerprints for Interface contact disk-cache validation.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from cable_bundler.domain import AttachmentTargetKind, InterfaceContact


def test_body_revision_and_occurrence_placement_change_signature(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Revalidate both face geometry and its assembly-space placement.
    """
    source: Any = importlib.import_module("cable_bundler.fusion.interface_contact_source")
    body = SimpleNamespace(revisionId="revision-1", name="Pads")
    matrix = SimpleNamespace(values=[1.0] * 16)

    def matrix_values() -> list[float]:
        """
        Return the current transform values for the fake Fusion matrix.
        """
        return matrix.values

    matrix.asArray = matrix_values
    occurrence = SimpleNamespace(transform2=matrix)
    entity = SimpleNamespace(body=body, assemblyContext=occurrence)

    def resolve(_design: object, _token: str) -> tuple[object, ...]:
        """
        Return the selected face proxy.
        """
        return (entity,)

    def kind(_entity: object) -> AttachmentTargetKind:
        """
        Classify the fake proxy as a face.
        """
        return AttachmentTargetKind.FACE

    monkeypatch.setitem(vars(source), "resolve_contact_entities", resolve)
    monkeypatch.setitem(vars(source), "attachment_target_kind", kind)
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")

    original = source.contact_source_signature(object(), contact)
    body.revisionId = "revision-2"
    revised = source.contact_source_signature(object(), contact)
    matrix.values[3] = 5.0
    moved = source.contact_source_signature(object(), contact)

    assert original is not None
    assert len({original, revised, moved}) == 3


def test_unavailable_revision_fails_closed(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Never trust an outline when Fusion cannot identify its source revision.
    """
    source: Any = importlib.import_module("cable_bundler.fusion.interface_contact_source")
    entity = SimpleNamespace(body=SimpleNamespace(revisionId="", name="Pads"))

    def resolve(_design: object, _token: str) -> tuple[object, ...]:
        """
        Return a face whose body revision is unavailable.
        """
        return (entity,)

    def kind(_entity: object) -> AttachmentTargetKind:
        """
        Classify the fake proxy as a face.
        """
        return AttachmentTargetKind.FACE

    monkeypatch.setitem(vars(source), "resolve_contact_entities", resolve)
    monkeypatch.setitem(vars(source), "attachment_target_kind", kind)
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")

    assert source.contact_source_signature(object(), contact) is None


def test_sketch_revision_changes_profile_signature(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Invalidate a profile when its owning sketch changes without a token change.
    """
    source: Any = importlib.import_module("cable_bundler.fusion.interface_contact_source")
    sketch = SimpleNamespace(revisionId="sketch-1", name="Connectors")
    entity = SimpleNamespace(parentSketch=sketch, assemblyContext=None)

    def resolve(_design: object, _token: str) -> tuple[object, ...]:
        """
        Return the selected sketch profile.
        """
        return (entity,)

    def kind(_entity: object) -> AttachmentTargetKind:
        """
        Classify the fake entity as a profile.
        """
        return AttachmentTargetKind.PROFILE

    monkeypatch.setitem(vars(source), "resolve_contact_entities", resolve)
    monkeypatch.setitem(vars(source), "attachment_target_kind", kind)
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.PROFILE, "profile-token")

    original = source.contact_source_signature(object(), contact)
    sketch.revisionId = "sketch-2"

    assert original is not None
    assert source.contact_source_signature(object(), contact) != original


def test_point_movement_changes_signature_without_owner_revision(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Validate construction-point contacts by their live coordinates.
    """
    source: Any = importlib.import_module("cable_bundler.fusion.interface_contact_source")
    entity = SimpleNamespace(
        geometry=SimpleNamespace(x=1.0, y=2.0, z=3.0),
        name="Test Point",
        assemblyContext=None,
    )

    def resolve(_design: object, _token: str) -> tuple[object, ...]:
        """
        Return the selected construction point.
        """
        return (entity,)

    def kind(_entity: object) -> AttachmentTargetKind:
        """
        Classify the fake entity as a construction point.
        """
        return AttachmentTargetKind.CONSTRUCTION_POINT

    monkeypatch.setitem(vars(source), "resolve_contact_entities", resolve)
    monkeypatch.setitem(vars(source), "attachment_target_kind", kind)
    contact = InterfaceContact(UUID(int=4), AttachmentTargetKind.CONSTRUCTION_POINT, "point")

    original = source.contact_source_signature(object(), contact)
    entity.geometry.x = 4.0

    assert original is not None
    assert source.contact_source_signature(object(), contact) != original
