"""
Preserve the selected221surface/seam/ordered-guide/cap audit in maintained source.

Copied without changing its measurement policy from the retained221artifact.
No geometry repair or tolerance expansion is performed by this development audit.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

# noinspection PyUnresolvedReferences
from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_native import native_point, native_surface
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches


def angle(a: Vector3, b: Vector3) -> float:
    """
    Measure an ordered direction difference without modulo180 identification.
    """
    return math.degrees(math.atan2(magnitude(cross(unit(a), unit(b))), dot(unit(a), unit(b))))


def audit(body: Any, row: dict[str, Any], budget: NativeBudget, occurrence: Any) -> dict[str, Any]:
    """
    Measure fixed native face families, ordered seam chains, three guides and caps.

    Extends archived212/213 to varying count/diameter without nearest-side lookup.
    A failure preserves partial measurements through the caller-owned output dict.
    """
    output: dict[str, Any] = row["audit"]
    output["membership_corroborations"] = []
    output["endpoint_sample_roundoff"] = []

    def membership(face_index: int, point: Any, uv: Any, patch: Any) -> bool:
        """
        Corroborate rejected UV queries on the same trimmed face and solid.

        Native NURBS control equality and independent trimmed-face distance must
        both pass; no other face, side reassignment or expanded tolerance is used.
        All initial membership rejections remain individually reported.
        """
        face = body.faces.item(face_index)
        if face.evaluator.isParameterOnFace(uv):
            return True
        if len(output["membership_corroborations"]) >= 64:
            raise RuntimeError("Membership corroboration count cap")
        budget.check("trimmed-face membership corroboration")
        native_data = face.geometry.getData()
        authored_data = native_surface(patch).getData()
        controls_match = (
            native_data[:5] == authored_data[:5]
            and len(native_data[5]) == len(authored_data[5])
            and all(a.distanceTo(b) * 10 <= 1e-12 for a, b in zip(native_data[5], authored_data[5]))
            and native_data[6:] == authored_data[6:]
        )
        measured = adsk.core.Application.get().measureManager.measureMinimumDistance(
            point, face.createForAssemblyContext(occurrence)
        )
        containment = body.pointContainment(point)
        distance = measured.value * 10
        accepted = (
            controls_match
            and distance <= 1e-6
            and containment == adsk.fusion.PointContainment.PointOnPointContainment
        )
        output["membership_corroborations"].append(
            {
                "face": face_index,
                "uv": [uv.x, uv.y],
                "distance_mm": distance,
                "controls_match": controls_match,
                "containment": int(containment),
                "accepted": accepted,
            }
        )
        return accepted

    pieces = []
    for item in row["pieces"]:
        pose = Pose(**{key: Vector3(**value) for key, value in item["pose"].items()})
        geometry = (
            CylindricalFold(**item["geometry"])
            if item["kind"] == "fold"
            else Straight(**item["geometry"])
        )
        pieces.append(PlacedPiece(pose, geometry, item["label"]))
    profile = material_profile(row["lines"], row["diameter_mm"])
    patches = material_patches(tuple(pieces), profile)
    count = len(profile)
    lookup = {(p.piece_index, p.region, p.profile_index): i for i, p in enumerate(patches)}
    half = row["profile_width_mm"] / 2
    if body.faces.count != len(patches) + 2:
        raise RuntimeError("Frozen triple/topology guard")
    for index, patch in enumerate(patches):
        budget.check("native surface audit")
        face = body.faces.item(index)
        piece = pieces[patch.piece_index]
        geometry = piece.geometry
        patch_max = 0.0
        for fraction in (0.013, 0.13, 0.33, 0.5, 0.71, 0.89, 0.987):
            for v in (0.03, 0.19, 0.5, 0.83, 0.97):
                q, b = patch.profile.point(v)
                if isinstance(geometry, Straight):
                    material_u = fraction
                else:
                    low, high = geometry.bend_interval(q)
                    material_u = (
                        low + fraction * (high - low)
                        if patch.region == "bend"
                        else fraction * low
                        if patch.region == "before"
                        else high + fraction * (1 - high)
                    )
                point, velocity, across, _ = piece.surface(min(1, max(0, material_u)), q)
                normal = unit(cross(velocity, across))
                expected = point.translated(normal, b)
                ok, uv = face.evaluator.getParameterAtPoint(native_point(expected))
                if not ok:
                    raise RuntimeError(f"Face {index} cannot invert expected material point")
                inside = membership(index, native_point(expected), uv, patch)
                ok, actual = face.evaluator.getPointAtParameter(uv)
                error = actual.distanceTo(native_point(expected)) * 10 if ok else math.inf
                output["native_points_checked"] += 1
                patch_max = max(patch_max, error)
                if not inside or error > 1e-6:
                    output["failed_points"].append(
                        {
                            "face": index,
                            "region": patch.region,
                            "fraction": fraction,
                            "v": v,
                            "error_mm": error,
                            "inside": inside,
                        }
                    )
        output["maximum_error_mm"] = max(output["maximum_error_mm"], patch_max)
        output["patches_audited"] += 1
        output["samples"].append(
            {
                "face": index,
                "piece": patch.piece_index,
                "region": patch.region,
                "profile": patch.profile.label,
                "maximum_error_mm": patch_max,
                "surface_type": face.geometry.objectType,
            }
        )

    if output["failed_points"]:
        raise RuntimeError("Native full-profile surface fidelity gate")

    for index, patch in enumerate(patches):
        budget.check("ordered seam chains")
        pairs = [
            (index - index % count + (index + 1) % count, patch.rows[0][-1], patch.rows[-1][-1])
        ]
        if index >= count:
            pairs.append((index - count, patch.rows[0][0], patch.rows[0][-1]))
        for neighbor, start, end in pairs:
            face = body.faces.item(index)
            other = {edge.tempId for edge in body.faces.item(neighbor).edges}
            shared = [edge for edge in face.edges if edge.tempId in other]
            counts: Counter[int] = Counter()
            vertices: dict[int, Any] = {}
            connections: dict[int, set[int]] = {}
            for edge in shared:
                a, b = edge.startVertex, edge.endVertex
                counts.update((a.tempId, b.tempId))
                vertices.update({a.tempId: a, b.tempId: b})
                connections.setdefault(a.tempId, set()).add(b.tempId)
                connections.setdefault(b.tempId, set()).add(a.tempId)
            tips = [key for key, degree in counts.items() if degree == 1]
            pending = list(tips[:1])
            reached = set()
            while pending:
                key = pending.pop()
                if key not in reached:
                    reached.add(key)
                    pending.extend(connections[key] - reached)
            collapsed = magnitude(difference(start, end)) < 1e-10
            valid = (
                not shared
                if collapsed
                else (
                    len(tips) == 2
                    and max(counts.values(), default=0) <= 2
                    and reached == set(counts)
                )
            )
            residual = 0.0
            if valid and not collapsed:
                a, b = [vertices[key].geometry for key in tips]
                residual = (
                    min(
                        max(
                            float(a.distanceTo(native_point(start))),
                            float(b.distanceTo(native_point(end))),
                        ),
                        max(
                            float(b.distanceTo(native_point(start))),
                            float(a.distanceTo(native_point(end))),
                        ),
                    )
                    * 10
                )
                valid = residual <= 1e-6
            output["seams_checked"] += 1
            if not valid:
                output["seam_failures"].append(
                    {
                        "faces": [index, neighbor],
                        "edge_count": len(shared),
                        "endpoint_error_mm": residual,
                    }
                )

    def physical(
        piece_number: int,
        material_u: float,
        offset_mm: float,
        height_mm: float,
        profile_index: int,
    ) -> Vector3:
        """
        Read the prescribed material point from its fixed native face family.
        """
        material_piece = pieces[piece_number]
        material_geometry = material_piece.geometry
        if isinstance(material_geometry, Straight):
            region = "straight"
        else:
            entry, exit_fraction = material_geometry.bend_interval(offset_mm)
            region = (
                "before"
                if material_u < entry
                else "after"
                if material_u > exit_fraction
                else "bend"
            )
            if (piece_number, region, profile_index) not in lookup:
                region = "bend"
        point, velocity, across, _ = material_piece.surface(material_u, offset_mm)
        planned_point = point.translated(unit(cross(velocity, across)), height_mm)
        face_index = lookup[(piece_number, region, profile_index)]
        material_face = body.faces.item(face_index)
        inverted, uv = material_face.evaluator.getParameterAtPoint(native_point(planned_point))
        if not inverted or not membership(
            face_index, native_point(planned_point), uv, patches[face_index]
        ):
            raise RuntimeError("Corresponding guide point is outside prescribed native face")
        evaluated, native_value = material_face.evaluator.getPointAtParameter(uv)
        if not evaluated or native_value.distanceTo(native_point(planned_point)) * 10 > 1e-6:
            raise RuntimeError("Native guide projection mismatch")
        return Vector3(native_value.x * 10, native_value.y * 10, native_value.z * 10)

    def guide(guide_piece: int, guide_u: float, guide_name: str) -> Vector3:
        """
        Track fixed outer tips or the midpoint of corresponding native skins.
        """
        if guide_name == "left":
            return physical(guide_piece, guide_u, half, 0, row["lines"] + 1)
        if guide_name == "right":
            return physical(guide_piece, guide_u, -half, 0, 2 * row["lines"] + 3)
        lane = row["lines"] // 2
        height = profile[lane].point(0.5 if row["lines"] % 2 else 0.0)[1]
        bottom_index = next(i for i, arc in enumerate(profile) if arc.label == f"bottom-{lane}")
        top = physical(guide_piece, guide_u, 0, height, lane)
        bottom = physical(guide_piece, guide_u, 0, -height, bottom_index)
        return Vector3((top.x + bottom.x) / 2, (top.y + bottom.y) / 2, (top.z + bottom.z) / 2)

    for name, q in (("left", half), ("center", 0.0), ("right", -half)):
        errors = []
        tangent_errors = []
        for piece_index, placed in enumerate(pieces):
            budget.check("three material guides")
            geometry = placed.geometry
            fractions = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
            if isinstance(geometry, CylindricalFold):
                low, high = geometry.bend_interval(q)
                middles = [low / 2, (low + high) / 2, (1 + high) / 2]
                fractions.extend(middles)
            else:
                middles = [0.5]
            if min(fractions) < -1e-14 or max(fractions) > 1 + 1e-14:
                raise RuntimeError("Material sample outside endpoint roundoff bound")
            for value in fractions:
                if value < 0 or value > 1:
                    output["endpoint_sample_roundoff"].append(
                        {
                            "name": name,
                            "piece": piece_index,
                            "raw_u": value,
                            "measured_u": min(1.0, max(0.0, value)),
                        }
                    )
            for u in sorted(set(min(1.0, max(0.0, value)) for value in fractions)):
                actual = guide(piece_index, u, name)
                expected = placed.surface(u, q)[0]
                error = magnitude(difference(actual, expected))
                errors.append(error)
                output["guide_records"].append(
                    {"name": name, "piece": piece_index, "u": u, "position_error_mm": error}
                )
            for u in middles:
                if not 1e-4 < u < 1 - 1e-4:
                    continue
                before, after = (
                    guide(piece_index, u - 1e-5, name),
                    guide(piece_index, u + 1e-5, name),
                )
                tangent_errors.append(angle(difference(after, before), placed.surface(u, q)[1]))
        output["guide_maximum_position_error_mm"][name] = max(errors)
        output["guide_maximum_tangent_error_degrees"][name] = max(tangent_errors)
    for end in (False, True):
        piece_index, u = (len(pieces) - 1, 1.0) if end else (0, 0.0)
        side = "end" if end else "start"
        actual_left, actual_right = (
            guide(piece_index, u, "left"),
            guide(piece_index, u, "right"),
        )
        width = Vector3(**row["case"][side + "_width"])
        center = guide(piece_index, u, "center")
        face = body.faces.item(len(patches) + (1 if end else 0))
        ok, normal = face.evaluator.getNormalAtPoint(native_point(center))
        if not ok:
            raise RuntimeError("Native cap normal unavailable")
        outward = Vector3(0, 0, 0).translated(
            Vector3(**row["case"][side + "_tangent"]), 1 if end else -1
        )
        output["caps"].append(
            {
                "side": side,
                "center_error_mm": magnitude(difference(center, Vector3(**row["case"][side]))),
                "ordered_width_error_degrees": angle(difference(actual_left, actual_right), width),
                "outward_normal_error_degrees": angle(
                    Vector3(normal.x, normal.y, normal.z), outward
                ),
            }
        )
    output["body_revision_after"] = body.revisionId
    if (
        output["seam_failures"]
        or max(output["guide_maximum_tangent_error_degrees"].values()) > 0.001
    ):
        raise RuntimeError("Native seam or guide tangent gate")
    if any(
        cap["center_error_mm"] > 1e-6
        or cap["ordered_width_error_degrees"] > 0.001
        or cap["outward_normal_error_degrees"] > 0.001
        for cap in output["caps"]
    ):
        raise RuntimeError("Ordered cap gate")
    return output
