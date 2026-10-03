"""
Probe the production Discrete ribbon section on PH reversal sweeps.

Run through Fusion ``Python.Run`` with no command active. This creates and
leaves open a separate unsaved scratch, without editing prior documents.
The sweep uses the actual moderate-groove section but not the production
banking guide rail or folded multi-station loft.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from cable_bundler.domain import CableGroupDefinition, CableGroupType
from cable_bundler.fusion.cable_solid_parts.ribbon_builder import _add_section
from cable_bundler.routing import RibbonFrame, Vector3
from experiments.experiment_ph_fusion_sweep import _path_sketch
from experiments.experiment_ph_quintic import HermiteCase, ph_hermite_candidates
from experiments.experiment_product_profile_sweeps import _section_report

CASES = tuple(
    (lines, separation, twist)
    for lines, separations in ((3, (3.0, 5.0, 10.0)), (5, (5.0, 10.0)))
    for separation in separations
    for twist in (0.0, 90.0, 180.0)
)


def _case(
    root: adsk.fusion.Component,
    lines: int,
    separation_mm: float,
    twist_degrees: float,
    offset_y_cm: float,
) -> dict[str, object]:
    """
    Sweep the actual Discrete ribbon contour and audit its midpoint section.
    """
    name = f"discrete_{lines}_h{separation_mm:g}_twist{twist_degrees:g}"
    row: dict[str, object] = {
        "name": name,
        "lines": lines,
        "diameter_mm": 1.0,
        "separation_mm": separation_mm,
        "twist_degrees": twist_degrees,
        "nominal_return_gap_mm": separation_mm - (lines + 0.2),
    }
    curve = ph_hermite_candidates(
        HermiteCase(name, complex(0.0, separation_mm), 25.0 + 0j, -25.0 + 0j)
    )[0]
    path_sketch, spline = _path_sketch(root, name, curve.controls, offset_y_cm)
    path = root.features.createPath(spline, False)
    group = CableGroupDefinition(
        cable_group_id=uuid4(),
        connection_ids=(uuid4(), uuid4()),
        diameter_mm=1.0,
        group_type=CableGroupType.RIBBON,
        ribbon_lines=lines,
    )
    frame = RibbonFrame(
        origin=Vector3(0.0, offset_y_cm * 10.0, 0.0),
        tangent=Vector3(1.0, 0.0, 0.0),
        width=Vector3(0.0, 1.0, 0.0),
        thickness=Vector3(0.0, 0.0, 1.0),
    )
    profile_sketch, plane = _add_section(root, path, frame, group, adsk.core.Matrix3D.create())
    profile = profile_sketch.profiles.item(0)
    profile_edges = profile.profileLoops.item(0).profileCurves.count
    area_mm2 = profile.areaProperties().area * 100.0
    nominal_volume_mm3 = area_mm2 * curve.exact_length_mm()
    row.update(
        {
            "profile_edges": profile_edges,
            "profile_area_mm2": area_mm2,
            "nominal_volume_mm3": nominal_volume_mm3,
        }
    )
    sweep_input = root.features.sweepFeatures.createInput(
        profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    if twist_degrees:
        sweep_input.twistAngle = adsk.core.ValueInput.createByString(f"{twist_degrees} deg")
    feature = root.features.sweepFeatures.add(sweep_input)
    if feature is None:
        raise RuntimeError("Fusion returned no Discrete ribbon sweep.")
    feature.name = name
    path_sketch.isLightBulbOn = False
    profile_sketch.isLightBulbOn = False
    plane.isLightBulbOn = False
    if feature.bodies.count != 1:
        row.update({"result": "non_single_body", "body_count": feature.bodies.count})
        return row
    body = feature.bodies.item(0)
    volume_mm3 = body.volume * 1000.0
    row.update(
        {
            "result": "solid" if body.isSolid else "non_solid",
            "body_face_count": body.faces.count,
            "body_volume_mm3": volume_mm3,
            "relative_volume_error": (volume_mm3 - nominal_volume_mm3) / nominal_volume_mm3,
        }
    )
    if body.isSolid:
        row["midpoint_section"] = _section_report(body, curve, offset_y_cm)
    return row


def run(_context: object) -> None:
    """
    Execute the discrete-section matrix in an unsaved isolated design.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    source = application.activeDocument
    source_modified_before = source.isModified
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create a Discrete ribbon scratch design.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The scratch document is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    rows: list[dict[str, object]] = []
    for index, (lines, separation, twist) in enumerate(CASES):
        try:
            row = _case(design.rootComponent, lines, separation, twist, index * 8.0)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            row = {
                "name": f"discrete_{lines}_h{separation:g}_twist{twist:g}",
                "lines": lines,
                "separation_mm": separation,
                "twist_degrees": twist,
                "result": "failed",
                "error": str(error),
            }
        rows.append(row)
    application.activeViewport.fit()
    report = {
        "source_document": source.name,
        "source_modified_before": source_modified_before,
        "source_modified_after": source.isModified,
        "scratch_document": scratch.name,
        "cases": rows,
    }
    root_path = Path(cable_bundler.__file__).resolve().parents[1]
    output = root_path / "artifacts/verification/discrete_ribbon_sweeps.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "DISCRETE_RIBBON_SWEEPS="
        + json.dumps(
            {"cases": len(rows), "solids": sum(row["result"] == "solid" for row in rows)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
