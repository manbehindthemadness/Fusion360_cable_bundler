"""
Extend the unchanged221audit with a strict actual-trim certificate for collapsed edges.
"""

from __future__ import annotations

import runpy
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import difference, magnitude
from devtools.ribbon_analysis.budget import NativeBudget
from experiments.experiment_ribbon_contraction.runner import ROOT, restore
from experiments.experiment_ribbon_fold_route.material_native import native_surface
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_surfaces import (
    MaterialPatch,
    material_patches,
)
from experiments.experiment_ribbon_joint_route.trim import rectangular_interior


def _certificate(face: Any, patch: MaterialPatch, uv: Any, occurrence: Any) -> dict[str, Any]:
    """
    Verify identical NURBS support, actual linear trim sides and strict query interior.

    The separate trimmed-face distance gate remains1e-6mm. Only a single outer
    loop of three/four degree-one nonrational curves is supported. An omitted
    side is allowed only when all corresponding authored controls coincide within
    the builder's existing1e-10mm collapsed-vertex bound. Native controls must
    match within the original1e-12mm corroboration bound. No SDK object is patched.
    """
    result: dict[str, Any] = {"uv": [uv.x, uv.y], "accepted": False}
    if (
        face.geometry.objectType != "adsk::core::NurbsSurface"
        or face.loops.count != 1
        or not face.loops.item(0).isOuter
    ):
        return result
    native, authored = face.geometry.getData(), native_surface(patch).getData()
    matched = (
        native[:5] == authored[:5]
        and len(native[5]) == len(authored[5])
        and all(a.distanceTo(b) * 10 <= 1e-12 for a, b in zip(native[5], authored[5]))
        and native[6:] == authored[6:]
    )
    result["controls_match"] = matched
    if not matched:
        return result
    segments = []
    for coedge in face.loops.item(0).coEdges:
        curve = coedge.geometry
        if curve.objectType != "adsk::core::NurbsCurve2D":
            return result
        data = curve.getData()
        if not data[0] or data[2] != 1 or len(data[1]) != 2 or data[4]:
            return result
        a, b = data[1]
        segments.append(((a.x, a.y), (b.x, b.y)))
    rows = patch.rows
    side_controls = {
        "u0": rows[0],
        "u1": rows[-1],
        "v0": tuple(r[0] for r in rows),
        "v1": tuple(r[-1] for r in rows),
    }
    collapsed = frozenset(
        name
        for name, points in side_controls.items()
        if max(magnitude(difference(p, points[0])) for p in points) < 1e-10
    )
    inside = rectangular_interior(
        (patch.knots_u[0], patch.knots_u[-1], 0.0, 1.0), tuple(segments), collapsed, (uv.x, uv.y)
    )
    result.update(
        segments=segments, collapsed_sides=sorted(collapsed), certified_uv_interior=inside
    )
    if not inside:
        return result
    ok, point = face.evaluator.getPointAtParameter(uv)
    if not ok:
        return result
    world = point.copy()
    world.transformBy(occurrence.transform2)
    measured = adsk.core.Application.get().measureManager.measureMinimumDistance(
        world, face.createForAssemblyContext(occurrence)
    )
    distance = measured.value * 10
    result.update(trimmed_distance_mm=distance, accepted=distance <= 1e-6)
    return result


class _Evaluator:
    """
    Delegate native evaluation, adding only the separately recorded trim certificate.
    """

    def __init__(
        self,
        face: Any,
        index: int,
        patch: MaterialPatch,
        occurrence: Any,
        output: dict[str, Any],
        budget: NativeBudget,
    ) -> None:
        """
        Bind one immutable native face and its exact planned material provenance.
        """
        self.face, self.index, self.patch = face, index, patch
        self.occurrence, self.output, self.budget = occurrence, output, budget

    def __getattr__(self, name: str) -> Any:
        """
        Preserve all original point, derivative and inverse-query behavior.
        """
        return getattr(self.face.evaluator, name)

    def isParameterOnFace(self, uv: Any) -> bool:
        """
        Keep raw decisions and require an actual-boundary proof for any added acceptance.
        """
        if self.face.evaluator.isParameterOnFace(uv):
            return True
        self.budget.check("independent collapsed-edge trim certificate")
        records = self.output["trim_certifications"]
        if len(records) >= 64:
            raise RuntimeError("Trim certification count cap")
        result = _certificate(self.face, self.patch, uv, self.occurrence)
        result.update(face=self.index, raw_membership=False)
        records.append(result)
        return bool(result["accepted"])


class _Face:
    """
    Expose an unchanged native face with a validation-only evaluator adapter.
    """

    def __init__(self, native: Any, evaluator: _Evaluator) -> None:
        """
        Retain the real face for topology, geometry and assembly-context queries.
        """
        self.native, self.evaluator = native, evaluator

    def __getattr__(self, name: str) -> Any:
        """
        Delegate every operation except the explicit membership query adapter.
        """
        return getattr(self.native, name)


class _Faces:
    """
    Preserve native face indexing, adding certificates only to known lateral patches.
    """

    def __init__(
        self,
        body: Any,
        patches: tuple[MaterialPatch, ...],
        occurrence: Any,
        output: dict[str, Any],
        budget: NativeBudget,
    ) -> None:
        """
        Bind unchanged face order and the original audit's material patch lookup.
        """
        self.body, self.patches, self.occurrence = body, patches, occurrence
        self.output, self.budget = output, budget

    @property
    def count(self) -> int:
        """
        Retain the original topology-count guard.
        """
        return self.body.faces.count

    def item(self, index: int) -> Any:
        """
        Leave cap evaluators unchanged and adapt only a corresponding lateral face.
        """
        face = self.body.faces.item(index)
        if index >= len(self.patches):
            return face
        return _Face(
            face,
            _Evaluator(face, index, self.patches[index], self.occurrence, self.output, self.budget),
        )


class _Body:
    """
    Delegate the existing body while exposing only a read-only face-evaluation adapter.
    """

    def __init__(self, native: Any, faces: _Faces) -> None:
        """
        Keep actual solid identity, revision and containment queries untouched.
        """
        self.native, self.faces = native, faces

    def __getattr__(self, name: str) -> Any:
        """
        Preserve original body operations and guards without SDK mutation.
        """
        return getattr(self.native, name)


def audit(body: Any, row: dict[str, Any], budget: NativeBudget, occurrence: Any) -> dict[str, Any]:
    """
    Run all original221measurements with separately evidenced trim membership decisions.

    Geometry, point-inversion results, surface/guide distance tolerances, seam checks
    and complete ordered caps remain unchanged. Historical reports and archived
    source are never edited. New reports name this extended policy explicitly.
    """
    route = restore(row)
    patches = material_patches(route.pieces, material_profile(row["lines"], row["diameter_mm"]))
    output = row["audit"]
    output["trim_certifications"] = []
    output["fidelity_policy"] = "221plus explicit actual-UV-rectangle/collapsed-edge certificate"
    original = runpy.run_path(
        str(ROOT / "artifacts/verification/ribbon_fidelity221/fidelity_audit221.py")
    )["audit"]
    faces = _Faces(body, patches, occurrence, output, budget)
    return original(_Body(body, faces), row, budget, occurrence)
