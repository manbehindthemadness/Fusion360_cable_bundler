"""
Color contact-indexed trace faces on the open side-by-side production lofts.

Run through local Fusion MCP after the 19-line controlled loft comparison.
Only the active unsaved scratch is changed. Contact spheres are synthetic
markers at the control plan's ordered contact centers, not copied Interfaces.
"""

from __future__ import annotations

import colorsys
import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain.ffc import resolve_ffc_dimensions
from cable_bundler.fusion.solid_ribbon import SolidRibbonSection
from experiments.experiment_production_loft_uv_comparison import _controlled_plan

OUTPUT = (
    Path(__file__).resolve().parents[1] / "artifacts/verification/production_loft_contact_traces"
)
SOURCE_LIBRARY = "BA5EE55E-9982-449B-9D66-9F036540E140"
SOURCE_APPEARANCE = "Prism-129"
LINES = 19
PITCH_MM = 2.5066666666666664
DIAMETER_MM = 1.5
END_X_CM = 11.0
PLANE_TOLERANCE_CM = 0.003
CENTER_TOLERANCE_MM = 0.03
WIDTH_TOLERANCE_MM = 0.05


def _appearance(
    design: adsk.fusion.Design,
    source: adsk.core.Appearance,
    name: str,
    rgb: tuple[int, int, int],
) -> adsk.core.Appearance:
    """
    Reuse or make a document-local solid-color appearance for this trial.
    """
    appearance = design.appearances.itemByName(name)
    if appearance is None:
        appearance = design.appearances.addByCopy(source, name)
    if appearance is None:
        raise RuntimeError(f"Fusion could not create {name}.")
    albedo = appearance.appearanceProperties.itemById("opaque_albedo")
    if albedo is None:
        raise RuntimeError(f"Fusion did not expose {name}'s albedo.")
    albedo.value = adsk.core.Color.create(*rgb, 255)
    return appearance


def _line_rgb(index: int) -> tuple[int, int, int]:
    """
    Give every ordered contact a distinct, high-saturation test color.
    """
    red, green, blue = colorsys.hsv_to_rgb((index * 0.618033988749895) % 1.0, 0.85, 0.95)
    return round(red * 255), round(green * 255), round(blue * 255)


def _end_interval(face: adsk.fusion.BRepFace, station: SolidRibbonSection) -> tuple[float, float]:
    """
    Measure one side face's width interval on a rendered contact plane.
    """
    meshes = face.meshManager.displayMeshes
    if not meshes.count:
        raise RuntimeError("A loft side face has no rendered mesh.")
    nodes = meshes.item(0).nodeCoordinates
    plane_x_cm = station.centers[0].x / 10.0
    across = tuple(
        (node.y * station.width.y + node.z * station.width.z) * 10.0
        for node in nodes
        if abs(node.x - plane_x_cm) < PLANE_TOLERANCE_CM
    )
    if len(across) < 2:
        raise RuntimeError("A loft side face misses a control contact plane.")
    return min(across), max(across)


def _trace_faces(
    feature: adsk.fusion.LoftFeature,
    start_station: SolidRibbonSection,
    end_station: SolidRibbonSection,
    trace_width_mm: float,
) -> tuple[tuple[int, adsk.fusion.BRepFace, dict[str, float]], ...]:
    """
    Resolve exactly two broad faces per contact by measured end intervals.
    """
    selected: list[tuple[int, adsk.fusion.BRepFace, dict[str, float]]] = []
    start_centers_mm = tuple(
        center.y * start_station.width.y + center.z * start_station.width.z
        for center in start_station.centers
    )
    end_centers_mm = tuple(
        center.y * end_station.width.y + center.z * end_station.width.z
        for center in end_station.centers
    )
    for face_index in range(feature.sideFaces.count):
        face = feature.sideFaces.item(face_index)
        start_low, start_high = _end_interval(face, start_station)
        start_mid = (start_low + start_high) / 2.0
        width = start_high - start_low
        if abs(width - trace_width_mm) > WIDTH_TOLERANCE_MM:
            continue
        lane = min(range(LINES), key=lambda index: abs(start_mid - start_centers_mm[index]))
        start_error = abs(start_mid - start_centers_mm[lane])
        end_low, end_high = _end_interval(face, end_station)
        end_mid = (end_low + end_high) / 2.0
        end_error = abs(end_mid - end_centers_mm[lane])
        if start_error > CENTER_TOLERANCE_MM or end_error > CENTER_TOLERANCE_MM:
            raise RuntimeError(
                f"Face {face_index} is not centered on contact {lane + 1} at both ends."
            )
        selected.append(
            (
                lane,
                face,
                {
                    "face_index": face_index,
                    "width_mm": width,
                    "start_center_error_mm": start_error,
                    "end_center_error_mm": end_error,
                },
            )
        )
    counts = [sum(item[0] == lane for item in selected) for lane in range(LINES)]
    if counts != [2] * LINES:
        raise RuntimeError(f"Expected top and bottom trace faces per contact; got {counts}.")
    return tuple(selected)


def _markers(
    root: adsk.fusion.Component,
    label: str,
    offset_y_cm: float,
    colors: tuple[adsk.core.Appearance, ...],
    stations: tuple[SolidRibbonSection, SolidRibbonSection],
) -> int:
    """
    Place small colored spheres just outside both ordered contact planes.
    """
    manager = adsk.fusion.TemporaryBRepManager.get()
    if manager is None:
        raise RuntimeError("Fusion temporary B-Rep services are unavailable.")
    count = 0
    for end, station in enumerate(stations):
        for lane, center in enumerate(station.centers):
            x_cm = -0.14 if end == 0 else END_X_CM + 0.14
            point = adsk.core.Point3D.create(
                x_cm,
                center.y / 10.0 + offset_y_cm,
                center.z / 10.0,
            )
            temporary = manager.createSphere(point, 0.055)
            if temporary is None:
                raise RuntimeError("Fusion could not create a contact marker sphere.")
            body = root.bRepBodies.add(temporary)
            if body is None:
                raise RuntimeError("Fusion could not persist a contact marker sphere.")
            body.name = f"{label} contact {lane + 1:02d} {'start' if end == 0 else 'end'}"
            body.appearance = colors[lane]
            count += 1
    return count


def run(_context: object) -> None:
    """
    Show target widths and gaps aligned to every numbered contact center.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved 19-line comparison scratch first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    root = design.rootComponent
    components = {
        occurrence.component.name: occurrence.component for occurrence in root.occurrences
    }
    expected = {
        "Production loft · Discrete · valid control": ("Discrete", 0.0, DIAMETER_MM),
        "Production loft · FFC · valid control": (
            "FFC",
            4.0,
            resolve_ffc_dimensions(PITCH_MM, (None,) * LINES, None, None).trace_width_mm,
        ),
    }
    if set(components) != set(expected):
        raise RuntimeError("The active design is not the two controlled production lofts.")
    if any(body.name.startswith("FFC contact ") for body in root.bRepBodies):
        raise RuntimeError("Contact markers are already present in this scratch.")
    library = application.materialLibraries.itemById(SOURCE_LIBRARY)
    source = None if library is None else library.appearances.itemById(SOURCE_APPEARANCE)
    if source is None:
        raise RuntimeError("Fusion's generic opaque appearance is unavailable.")
    plan = _controlled_plan(LINES, PITCH_MM, DIAMETER_MM)
    colors = tuple(
        _appearance(design, source, f"Contact trace {lane + 1:02d}", _line_rgb(lane))
        for lane in range(LINES)
    )
    neutral = _appearance(design, source, "Contact trace gap neutral", (55, 58, 62))
    cases: list[dict[str, object]] = []
    for name, (label, offset_y_cm, target_width_mm) in expected.items():
        component = components[name]
        lofts = component.features.loftFeatures
        if lofts.count != 1 or lofts.item(0).bodies.count != 1:
            raise RuntimeError(f"Expected one loft body for {label}.")
        feature = lofts.item(0)
        selected = _trace_faces(feature, plan.sections[0], plan.sections[-1], target_width_mm)
        for face in feature.sideFaces:
            face.appearance = neutral
        for lane, face, _measurement in selected:
            face.appearance = colors[lane]
        marker_count = _markers(
            root, label, offset_y_cm, colors, (plan.sections[0], plan.sections[-1])
        )
        cases.append(
            {
                "profile": label,
                "contact_count": LINES,
                "marker_count": marker_count,
                "pitch_mm": PITCH_MM,
                "target_width_mm": target_width_mm,
                "target_gap_mm": PITCH_MM - target_width_mm,
                "colored_trace_faces": len(selected),
                "neutral_gap_and_edge_faces": feature.sideFaces.count - len(selected),
                "max_start_center_error_mm": max(
                    row[2]["start_center_error_mm"] for row in selected
                ),
                "max_end_center_error_mm": max(row[2]["end_center_error_mm"] for row in selected),
                "max_width_error_mm": max(
                    abs(row[2]["width_mm"] - target_width_mm) for row in selected
                ),
                "faces": [dict(lane=lane + 1, **measurement) for lane, _, measurement in selected],
            }
        )
    viewport = application.activeViewport
    OUTPUT.mkdir(parents=True, exist_ok=True)
    captures: dict[str, str] = {}
    for label, direction in (("top", 1.0), ("bottom", -1.0)):
        camera = viewport.camera
        camera.target = adsk.core.Point3D.create(5.5, 2.0, 0.0)
        camera.eye = adsk.core.Point3D.create(5.5, 2.0, 30.0 * direction)
        camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
        camera.viewExtents = 16.0
        viewport.camera = camera
        viewport.refresh()
        capture = OUTPUT / f"{label}.png"
        if not viewport.saveAsImageFile(str(capture), 0, 0):
            raise RuntimeError(f"Fusion could not capture the {label} contact trace view.")
        captures[label] = str(capture)
    report = OUTPUT / "report.json"
    report.write_text(
        json.dumps({"scratch": document.name, "cases": cases, "captures": captures}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(
        "PRODUCTION_LOFT_CONTACT_TRACES="
        + json.dumps({"report": str(report), "captures": captures})
    )


def capture_individual(_context: object) -> None:
    """
    Hide the overlapping control loft while capturing each contact bank.

    Leave FFC visible from above in the same unsaved scratch for inspection.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved contact-trace scratch first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    root = design.rootComponent
    occurrences = {
        occurrence.component.name.split(" · ")[1]: occurrence
        for occurrence in root.occurrences
        if occurrence.component.name.startswith("Production loft · ")
    }
    if set(occurrences) != {"Discrete", "FFC"}:
        raise RuntimeError("Both controlled production lofts must be present.")
    markers = tuple(
        body
        for body in root.bRepBodies
        if body.name.startswith(("Discrete contact ", "FFC contact "))
    )
    if len(markers) != 4 * LINES:
        raise RuntimeError("Both 19-contact marker banks must be present.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    viewport = application.activeViewport
    captures: dict[str, str] = {}
    for label, target_y_cm in (("Discrete", 0.0), ("FFC", 4.0)):
        for other, occurrence in occurrences.items():
            occurrence.isLightBulbOn = other == label
        for body in markers:
            body.isLightBulbOn = body.name.startswith(f"{label} contact ")
        for side, direction in (("top", 1.0), ("bottom", -1.0)):
            camera = viewport.camera
            camera.target = adsk.core.Point3D.create(5.5, target_y_cm, 0.0)
            camera.eye = adsk.core.Point3D.create(5.5, target_y_cm, 30.0 * direction)
            camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
            camera.viewExtents = 13.0
            viewport.camera = camera
            viewport.refresh()
            capture = OUTPUT / f"{label.lower()}_{side}.png"
            if not viewport.saveAsImageFile(str(capture), 0, 0):
                raise RuntimeError(f"Fusion could not capture {label} {side}.")
            captures[f"{label.lower()}_{side}"] = str(capture)
    camera = viewport.camera
    camera.target = adsk.core.Point3D.create(5.5, 4.0, 0.0)
    camera.eye = adsk.core.Point3D.create(5.5, 4.0, 30.0)
    camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
    camera.viewExtents = 13.0
    viewport.camera = camera
    viewport.refresh()
    report = OUTPUT / "individual_report.json"
    report.write_text(json.dumps(captures, indent=2) + "\n", encoding="utf-8")
    print("PRODUCTION_LOFT_CONTACT_CAPTURES=" + json.dumps(captures))


if __name__ == "__main__":
    run(None)
