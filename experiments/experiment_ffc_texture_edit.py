"""
Test whether a textured FFC side survives sweep-feature recomputation.

Run through Fusion ``Python.Run`` with a textured FFC design active and no
command running. This creates and leaves open an unsaved parametric scratch;
the active source design is only read.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_discrete_spline_seam import _seam_report
from experiments.experiment_ffc_spline_seam import _case
from experiments.experiment_ffc_texture_rebuild import (
    _compare_meshes,
    _map_report,
    _mesh_samples,
    _side_face,
    _source_texture,
)
from experiments.experiment_ph_quintic import HermiteCase, ph_hermite_candidates
from experiments.experiment_product_profile_sweeps import _section_report


def _feature_audit(
    feature: adsk.fusion.SweepFeature,
    root: adsk.fusion.Component,
    offset_y_cm: float,
) -> tuple[dict[str, object], dict[str, object]]:
    """
    Inspect topology, seam, appearance, and mesh after a feature recompute.
    """
    if feature.bodies.count != 1:
        raise RuntimeError("The edited FFC sweep no longer has one body.")
    body = feature.bodies.item(0)
    side = _side_face(body)
    section = root.sketches.item(root.sketches.count - 1)
    spline = section.sketchCurves.sketchFittedSplines.item(0)
    seam_point = spline.fitPoints.item(0).worldGeometry
    curve = ph_hermite_candidates(
        HermiteCase("ffc_edit", complex(0.0, 20.0), 25.0 + 0j, -25.0 + 0j)
    )[0]
    geometry = {
        "solid": body.isSolid,
        "faces": body.faces.count,
        "midpoint": _section_report(body, curve, offset_y_cm),
        "seam": _seam_report(feature, seam_point, 5.0, 20.0, 180.0, offset_y_cm),
        "appearance_name": body.appearance.name if body.appearance is not None else None,
        "texture_map": _map_report(body),
    }
    return geometry, _mesh_samples(side, offset_y_cm)


def run(_context: object) -> None:
    """
    Restore an edited FFC sweep to 180° and compare it with its baseline.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    source = application.activeDocument
    source_modified_before = source.isModified
    source_design = adsk.fusion.Design.cast(application.activeProduct)
    if source_design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    texture, source_map = _source_texture(source_design)
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the parametric FFC scratch.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The parametric scratch is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    row = _case(design.rootComponent, 5, 20.0, 180.0, 0.0)
    if row["result"] != "solid" or row["midpoint_section"]["wire_count"] != 1:
        raise RuntimeError("The baseline FFC sweep was not section-valid.")
    features = design.rootComponent.features.sweepFeatures
    feature = features.item(features.count - 1)
    if texture is not None:
        copied = design.appearances.addByCopy(texture, "FFC edit texture probe")
        feature.bodies.item(0).appearance = copied
    baseline, baseline_mesh = _feature_audit(feature, design.rootComponent, 0.0)
    original_expression = feature.twistAngle.expression
    feature.twistAngle.expression = "170 deg"
    intermediate_expression = feature.twistAngle.expression
    feature.twistAngle.expression = original_expression
    restored, restored_mesh = _feature_audit(feature, design.rootComponent, 0.0)
    application.activeViewport.fit()
    report = {
        "source_document": source.name,
        "source_modified_before": source_modified_before,
        "source_modified_after": source.isModified,
        "source_texture_name": texture.name if texture is not None else None,
        "source_texture_map": source_map,
        "scratch_document": scratch.name,
        "twist_expression_before": original_expression,
        "twist_expression_intermediate": intermediate_expression,
        "twist_expression_restored": feature.twistAngle.expression,
        "baseline": baseline,
        "restored": restored,
        "mesh_comparison": _compare_meshes(baseline_mesh, restored_mesh),
    }
    root_path = Path(cable_bundler.__file__).resolve().parents[1]
    output = root_path / "artifacts/verification/ffc_texture_edit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "FFC_TEXTURE_EDIT="
        + json.dumps(
            {
                "source_unchanged": source.isModified == source_modified_before,
                "restored_faces": restored["faces"],
                "mesh_comparable": report["mesh_comparison"]["comparable"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
