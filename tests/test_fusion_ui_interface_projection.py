"""
Fusion Interface contact projection regressions.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import AttachmentTargetKind, InterfaceContact


def _collection(*items: object) -> SimpleNamespace:
    """
    Mimic a Fusion indexed collection.
    """
    return SimpleNamespace(count=len(items), item=lambda index: items[index])


def test_projection_samples_profile_boundaries_and_keeps_mm_coordinates(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve sampled profile shape and placement for the diagram layer.
    """
    projection = importlib.import_module("cable_bundler.fusion.interface_contact_projection")

    def point(x: float, y: float, z: float = 0.0) -> SimpleNamespace:
        """
        Build one mock Fusion point in centimeters.
        """
        return SimpleNamespace(x=x, y=y, z=z)

    evaluator = SimpleNamespace(
        getParameterExtents=lambda: (True, 0.0, 1.0),
        getStrokes=lambda _start, _end, _tolerance: (
            True,
            [point(0, 0), point(1, 0), point(1, 2)],
        ),
    )
    sketch = SimpleNamespace(
        xDirection=point(1, 0),
        yDirection=point(0, 1),
        sketchToModelSpace=lambda sample: point(sample.x + 3, sample.y + 4, sample.z),
    )
    profile = SimpleNamespace(
        parentSketch=sketch,
        profileLoops=_collection(
            SimpleNamespace(
                profileCurves=_collection(
                    SimpleNamespace(geometry=SimpleNamespace(evaluator=evaluator)),
                )
            )
        ),
    )
    monkeypatch.setitem(
        vars(projection), "attachment_target_kind", lambda _entity: AttachmentTargetKind.PROFILE
    )
    monkeypatch.setitem(vars(projection), "attachment_target_name", lambda _entity, _kind: "Socket")
    design = SimpleNamespace(findEntityByToken=lambda _token: [profile])
    contact = InterfaceContact(UUID(int=901), AttachmentTargetKind.PROFILE, "profile", "J5.2")
    payload = projection.project_interface_contact(design, contact)
    assert payload["name"] == payload["assignedName"] == "J5.2"
    assert payload["normal"] == [0.0, 0.0, 1.0]
    assert payload["parentAxes"] == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert payload["loops"] == [[[30.0, 40.0, 0.0], [40.0, 40.0, 0.0], [40.0, 60.0, 0.0]]]


def test_projection_keeps_separated_faces_in_assembly_space(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve pad outlines and spacing when a proxy face yields native loop edges.
    """
    projection = importlib.import_module("cable_bundler.fusion.interface_contact_projection")

    def point(x: float, y: float, z: float = 0.0) -> SimpleNamespace:
        """
        Build a Fusion-like point or vector in centimeters.
        """
        return SimpleNamespace(x=x, y=y, z=z)

    def edge(start: tuple[float, float], end: tuple[float, float]) -> SimpleNamespace:
        """
        Return a native edge whose evaluator must be proxied before sampling.
        """

        def in_context(occurrence: SimpleNamespace) -> SimpleNamespace:
            """
            Expose world-space evaluator coordinates for the face occurrence.
            """
            samples = [point(x + occurrence.x, y + occurrence.y) for x, y in (start, end)]
            evaluator = SimpleNamespace(
                getParameterExtents=lambda: (True, 0.0, 1.0),
                getStrokes=lambda _start, _end, _tolerance: (True, samples),
            )
            return SimpleNamespace(evaluator=evaluator, assemblyContext=occurrence)

        return SimpleNamespace(assemblyContext=None, createForAssemblyContext=in_context)

    corners = ((0.0, 0.0), (0.4, 0.0), (0.4, 0.1), (0.0, 0.1))
    coedges = _collection(
        *(
            SimpleNamespace(edge=edge(corners[index], corners[(index + 1) % 4]))
            for index in range(4)
        )
    )
    faces = {
        f"pad-{index}": SimpleNamespace(
            assemblyContext=SimpleNamespace(x=index * 0.8, y=index * 0.3),
            loops=_collection(SimpleNamespace(coEdges=coedges)),
            geometry=SimpleNamespace(normal=point(0, 0, 1)),
        )
        for index in range(7)
    }
    monkeypatch.setitem(
        vars(projection), "attachment_target_kind", lambda _entity: AttachmentTargetKind.FACE
    )
    monkeypatch.setitem(vars(projection), "attachment_target_name", lambda _entity, _kind: "Pad")
    design = SimpleNamespace(findEntityByToken=lambda token: [faces[token]])
    outlines = [
        projection.project_interface_contact(
            design, InterfaceContact(UUID(int=index + 1), AttachmentTargetKind.FACE, f"pad-{index}")
        )["loops"][0]
        for index in range(7)
    ]
    assert all(len(outline) == 5 for outline in outlines)
    for index, outline in enumerate(outlines):
        assert outline[0][:2] == pytest.approx([index * 8.0, index * 3.0])
    assert [outline[1][0] - outline[0][0] for outline in outlines] == pytest.approx([4.0] * 7)


def test_projection_exposes_parent_axes_without_repositioning_geometry(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Carry the parent's assembly orientation separately from a face's normal.
    """
    projection = importlib.import_module("cable_bundler.fusion.interface_contact_projection")
    origin = SimpleNamespace(x=10.0, y=20.0, z=30.0)
    axes = [
        SimpleNamespace(x=0.0, y=0.0, z=1.0),
        SimpleNamespace(x=1.0, y=0.0, z=0.0),
        SimpleNamespace(x=0.0, y=1.0, z=0.0),
    ]
    face = SimpleNamespace(
        assemblyContext=SimpleNamespace(
            transform2=SimpleNamespace(getAsCoordinateSystem=lambda: (origin, *axes))
        ),
        geometry=SimpleNamespace(normal=SimpleNamespace(x=0.0, y=-1.0, z=0.0)),
        centroid=origin,
    )
    monkeypatch.setitem(
        vars(projection), "attachment_target_kind", lambda _entity: AttachmentTargetKind.FACE
    )
    monkeypatch.setitem(vars(projection), "attachment_target_name", lambda _entity, _kind: "Pad")
    contact = InterfaceContact(UUID(int=950), AttachmentTargetKind.FACE, "face")
    payload = projection.project_interface_contact(
        SimpleNamespace(findEntityByToken=lambda _token: [face]), contact
    )
    assert payload["parentAxes"] == [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert payload["normal"] == [0.0, -1.0, 0.0]
    assert payload["loops"] == [[[100.0, 200.0, 300.0]]]


def test_unavailable_parent_transform_uses_fallback(addin_module: object) -> None:
    """
    Keep contacts displayable when the host cannot provide their parent frame.
    """
    projection = importlib.import_module("cable_bundler.fusion.interface_contact_projection")
    transform = SimpleNamespace(getAsCoordinateSystem=Mock(side_effect=RuntimeError("unavailable")))
    entity = SimpleNamespace(assemblyContext=SimpleNamespace(transform2=transform))
    assert projection._parent_axes(entity) is None
    assert projection._parent_axes(SimpleNamespace()) is None
