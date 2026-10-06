"""
Display four fixed sphere boundary layouts without invoking a ribbon solver.

Requires the live Fusion API, an idle command, and the local development MCP
runner. Creates one unsaved owned document; other documents are untouched.
Graphics are illustrative, transient, and carry no geometry-compliance claim.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

Point = tuple[float, float]
Curve = tuple[Point, Point, Point, Point]
WIDTH_MM = 28.5
REPORT_ROOT = (
    Path(__file__).resolve().parents[1] / "artifacts/verification/ribbon-direction-preview"
)
CAP_A = (-0.9, 0.0)
CAP_B = (0.9, 0.0)
LAYOUTS: tuple[tuple[str, int, int, tuple[Curve, ...]], ...] = (
    ("01 A outward - B outward", -1, 1, ((CAP_A, (-0.3, 0), (0.3, 0), CAP_B),)),
    (
        "02 A inward - B inward",
        1,
        -1,
        (
            (CAP_A, (-1.6, 0), (-1.6, 1.1), (0, 1.1)),
            ((0, 1.1), (1.6, 1.1), (1.6, 0), CAP_B),
        ),
    ),
    (
        "03 A outward - B inward",
        -1,
        -1,
        (
            (CAP_A, (-0.2, 0), (0.1, 1.1), (0.8, 1.1)),
            ((0.8, 1.1), (1.5, 1.1), (1.5, 0), CAP_B),
        ),
    ),
    (
        "04 A inward - B outward",
        1,
        1,
        (
            (CAP_A, (-1.5, 0), (-1.5, 1.1), (-0.8, 1.1)),
            ((-0.8, 1.1), (-0.1, 1.1), (0.2, 0), CAP_B),
        ),
    ),
)


def _samples(curves: tuple[Curve, ...]) -> list[Point]:
    """
    Sample fixed authored cubics, omitting duplicate span junctions.
    """
    points: list[Point] = []
    for index, curve in enumerate(curves):
        for step in range(1 if index else 0, 41):
            t = step / 40
            s = 1 - t
            factors = (s**3, 3 * s * s * t, 3 * s * t * t, t**3)
            points.append(
                (
                    sum(weight * point[0] for weight, point in zip(factors, curve)),
                    sum(weight * point[1] for weight, point in zip(factors, curve)),
                )
            )
    return points


def _line(
    group: adsk.fusion.CustomGraphicsGroup,
    points: list[tuple[float, float, float]],
    color: tuple[int, int, int],
    weight: float = 1.0,
) -> None:
    """
    Add a local-coordinate line strip whose coordinates are already centimeters.
    """
    coordinates = adsk.fusion.CustomGraphicsCoordinates.create(
        [value for point in points for value in point]
    )
    entity = group.addLines(coordinates, [], True)
    if entity is None:
        raise RuntimeError("Fusion did not create a preview line.")
    entity.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
        adsk.core.Color.create(*color, 255)
    )
    entity.weight = weight


def _label(group: adsk.fusion.CustomGraphicsGroup, text: str, x: float, y: float) -> None:
    """
    Position a readable caption in the common layout plane.
    """
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(x, y, 0)
    entity = group.addText(text, "Arial", 0.35, transform)
    if entity is None:
        raise RuntimeError("Fusion did not create a preview caption.")
    entity.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
        adsk.core.Color.create(35, 35, 35, 255)
    )


def run(_context: object) -> None:
    """
    Leave four labeled previews active, and record layout-only evidence and timing.

    Fixed centerlines are authored inputs, not routing solutions. No lofts,
    branches, body construction, search, or post-build compliance audit occurs.
    """
    app = adsk.core.Application.get()
    if str(app.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before previewing.")
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_ROOT / "live-preview-report.json"
    if report_path.exists():
        raise FileExistsError("Preview evidence already exists; do not overwrite it.")
    started = perf_counter()
    before = [document.name for document in app.documents]
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    document.name = "Ribbon directions - 4x sphere - layout preview"
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("The new Fusion document has no design.")
    scale = WIDTH_MM / 10
    for index, (name, direction_a, direction_b, curves) in enumerate(LAYOUTS):
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(index * 5.1 * scale, 0, 0)
        occurrence = design.rootComponent.occurrences.addNewComponent(transform)
        occurrence.component.name = name
        group = occurrence.component.customGraphicsGroups.add()
        group.name = "Boundary layout only - compliance unmeasured"
        group.isSelectable = False
        for plane in range(3):
            circle = []
            for step in range(129):
                angle = 2 * math.pi * step / 128
                a, b = 2 * scale * math.cos(angle), 2 * scale * math.sin(angle)
                circle.append(((a, b, 0), (a, 0, b), (0, a, b))[plane])
            _line(group, circle, (155, 155, 155))
        samples = _samples(curves)
        coordinates = adsk.fusion.CustomGraphicsCoordinates.create(
            [
                value
                for x, y in samples
                for z in (-0.5, 0.5)
                for value in (x * scale, y * scale, z * scale)
            ]
        )
        indices: list[int] = []
        for step in range(len(samples) - 1):
            a = 2 * step
            indices.extend((a, a + 1, a + 3, a, a + 3, a + 2))
        mesh = group.addMesh(coordinates, indices, [], [])
        if mesh is None:
            raise RuntimeError("Fusion did not create a preview ribbon mesh.")
        mesh.cullMode = adsk.fusion.CustomGraphicsCullModes.CustomGraphicsCullNone
        mesh.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
            adsk.core.Color.create(110, 172, 210, 255)
        )
        for lane in range(20):
            z = (-0.5 + lane / 19) * scale
            _line(group, [(x * scale, y * scale, z) for x, y in samples], (45, 90, 125))
        for cap, direction, end in ((CAP_A, direction_a, "A"), (CAP_B, direction_b, "B")):
            x, y = cap[0] * scale, cap[1] * scale
            _line(group, [(x, y, -0.5 * scale), (x, y, 0.5 * scale)], (205, 85, 40), 4)
            tip = x + direction * 0.6 * scale
            _line(group, [(x, y, 0.6 * scale), (tip, y, 0.6 * scale)], (205, 85, 40), 3)
            _line(
                group,
                [
                    (tip - direction * 0.15 * scale, y - 0.12 * scale, 0.6 * scale),
                    (tip, y, 0.6 * scale),
                    (tip - direction * 0.15 * scale, y + 0.12 * scale, 0.6 * scale),
                ],
                (205, 85, 40),
                3,
            )
            _label(group, end, x - 0.1 * scale, -0.45 * scale)
        _label(group, name, -1.9 * scale, -2.2 * scale)
        _label(group, "W = 28.5 mm / sphere D = 114 mm", -1.9 * scale, -2.45 * scale)
    viewport = app.activeViewport
    camera = viewport.camera
    center = 1.5 * 5.1 * scale
    camera.target = adsk.core.Point3D.create(center, 0, 0)
    camera.eye = adsk.core.Point3D.create(center, -30 * scale, 40 * scale)
    camera.upVector = adsk.core.Vector3D.create(0, 0.8, 0.6)
    camera.isPerspective = False
    camera.isFitView = True
    viewport.camera = camera
    viewport.refresh()
    image_saved = viewport.saveAsImageFile(str(REPORT_ROOT / "live-preview.png"), 1600, 700)
    report = {
        "question": "Compare four end-facing directions side by side in four-width spheres.",
        "scope": "Illustrative fixed-centerline layouts, not solver outputs.",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "width_mm": WIDTH_MM,
        "sphere_diameter_mm": 4 * WIDTH_MM,
        "planned_layouts": 4,
        "displayed_layouts": design.rootComponent.occurrences.count,
        "solver_evaluations": 0,
        "native_solid_attempts": 0,
        "built_solids": sum(o.component.bRepBodies.count for o in design.rootComponent.occurrences),
        "compliance": "unmeasured",
        "cases": [name for name, *_ in LAYOUTS],
        "elapsed_seconds": perf_counter() - started,
        "previous_documents": before,
        "document": document.name,
        "image_saved": image_saved,
        "retention": "Leave this owned unsaved preview open; other documents untouched.",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    app.log(json.dumps(report))
