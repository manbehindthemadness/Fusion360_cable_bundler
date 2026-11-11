"""
Track authored material regions across native face merging without changing geometry.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Callable

from devtools.ribbon_analysis.budget import NativeBudget
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.material_surfaces import MaterialPatch

from .accuracy import STRICT_ACCURACY, DimensionalAccuracy
from .edge_parameter import inspect as inspect_edge_parameter
from .line_boundary import LINE_TYPE
from .line_boundary import certify as certify_line_boundary


@dataclass(frozen=True)
class Selection:
    """
    Retain an actual native face, inverse parameter and independently bounded surface error.
    """

    index: int
    uv: Any
    error_mm: float


class MaterialFaces:
    """
    Expose ordered material regions while retaining the real native face ownership map.

    Full-profile interior samples establish ownership before boundary/guide queries.
    A native face may cover several regions of the same profile arc. Crossing profile
    identity, uncovered lateral faces, missing caps and failed trim distances reject.
    No face count, raw membership decision or physical error is relabelled as native.
    """

    def __init__(
        self,
        body: Any,
        route: FoldRoute,
        patches: tuple[MaterialPatch, ...],
        occurrence: Any,
        budget: NativeBudget,
        point: Callable[[Any], Any],
        distance: Callable[[Any, Any], float],
        output: dict[str, Any],
        *,
        accuracy: DimensionalAccuracy = STRICT_ACCURACY,
        collapsed_boundary_tolerance_mm: float | None = None,
    ) -> None:
        """
        Cache native bounds once; keep the supplied solid and all entity identities untouched.
        """
        self.body, self.route, self.patches = body, route, patches
        self.accuracy = accuracy
        self.collapsed_boundary_tolerance_mm = (
            accuracy.goal_mm
            if collapsed_boundary_tolerance_mm is None
            else collapsed_boundary_tolerance_mm
        )
        if (
            type(self.collapsed_boundary_tolerance_mm) not in (int, float)
            or not math.isfinite(self.collapsed_boundary_tolerance_mm)
            or self.collapsed_boundary_tolerance_mm <= 0
        ):
            raise ValueError("Collapsed boundary tolerance must be finite and positive")
        if not body.isSolid or body.volume <= 0:
            raise ValueError("Material correspondence requires a closed positive solid")
        self.occurrence, self.budget = occurrence, budget
        self.point, self.distance, self.output = point, distance, output
        self.native: list[Any] = [body.faces.item(i) for i in range(body.faces.count)]
        self.boxes = []
        for face in self.native:
            box = face.boundingBox
            self.boxes.append(
                tuple((getattr(box.minPoint, a), getattr(box.maxPoint, a)) for a in "xyz")
            )
        self.owners: dict[int, int] = {}
        self.members: list[set[int]] = [set() for _ in range(len(patches) + 2)]
        self.families = [Family(self, i) for i in range(len(patches) + 2)]
        self.sealed = False
        self.queries = self.distance_queries = 0
        self.edge_queries = 0
        self.cache: dict[tuple[int, float, float, float], Selection] = {}
        output["face_correspondence"] = {
            "native_face_count": len(self.native),
            "material_region_count": len(self.families),
            "policy": "Actual trimmed-face membership/distance and unique profile ownership",
            "trim_distance_corroborations": [],
            "shared_face_seams": [],
            "native_edge_subchains": [],
            "native_vertex_boundaries": [],
            "native_line_boundaries": [],
            "edge_parameter_queries": 0,
        }

    @property
    def count(self) -> int:
        """
        Count declared material regions, separately from recorded native face count.
        """
        return len(self.families)

    def item(self, index: int) -> Family:
        """
        Return an authored material region backed exclusively by real native faces.
        """
        return self.families[index]

    def select(self, index: int, point: Any, allowed: set[int] | None = None) -> Selection | None:
        """
        Find a true trimmed-face witness within the explicit dimensional accuracy policy.

        Evaluate cheap raw memberships first. Only their collective failure invokes
        actual trimmed-face distance. Source interior samples may claim unowned faces;
        sealed boundary queries use the established profile ownership exclusively.
        Try previously verified members of this material region first. Their raw
        trimmed membership within the original accuracy goal supplies a complete
        witness; other results retain the exhaustive search and distance fallback.
        This changes query ordering, not samples, ownership, coverage or budgets.
        Correspondence promises a valid witness, not a globally nearest face.
        """
        profile = self.patches[index].profile_index if index < len(self.patches) else -index
        key = (profile, point.x, point.y, point.z)
        selected = self.cache.get(key)
        if selected is None:
            candidates: list[tuple[float, int, Any]] = []
            pending: list[tuple[float, int, Any]] = []
            preferred = self.members[index]
            order = (
                *sorted(preferred),
                *(j for j in range(len(self.native)) if j not in preferred),
            )
            for j in order:
                face, box = self.native[j], self.boxes[j]
                if allowed is not None and j not in allowed:
                    continue
                owner = self.owners.get(j)
                if owner is not None and owner != profile:
                    continue
                if self.sealed and owner is None:
                    continue
                if not all(
                    low - self.accuracy.search_radius_mm / 10
                    <= getattr(point, a)
                    <= high + self.accuracy.search_radius_mm / 10
                    for a, (low, high) in zip("xyz", box)
                ):
                    continue
                self.queries += 1
                if self.queries + self.edge_queries > 30000:
                    raise RuntimeError("Material face-query budget exhausted")
                ok, uv = face.evaluator.getParameterAtPoint(point)
                if not ok:
                    continue
                ok, actual = face.evaluator.getPointAtParameter(uv)
                error = actual.distanceTo(point) * 10 if ok else math.inf
                if not self.accuracy.accepts(error):
                    continue
                target = candidates if face.evaluator.isParameterOnFace(uv) else pending
                target.append((error, j, uv))
                if target is candidates and j in preferred and self.accuracy.meets_goal(error):
                    break
            if not candidates:
                for _, j, uv in sorted(pending, key=lambda row: (row[0], row[1])):
                    self.distance_queries += 1
                    if self.distance_queries > 512:
                        raise RuntimeError("Material trim-distance budget exhausted")
                    self.budget.check("actual trimmed-face correspondence")
                    world = point.copy()
                    world.transformBy(self.occurrence.transform2)
                    error = self.distance(
                        world, self.native[j].createForAssemblyContext(self.occurrence)
                    )
                    self.output["face_correspondence"]["trim_distance_corroborations"].append(
                        {
                            "region": index,
                            "native_face": j,
                            "raw_membership": False,
                            "distance_mm": error,
                        }
                    )
                    if self.accuracy.accepts(error):
                        self.accuracy.observe(
                            self.output, "trim_distance", error, region=index, native_face=j
                        )
                        candidates.append((error, j, uv))
                        break
            if not candidates:
                return None
            error, j, uv = min(candidates, key=lambda row: (row[0], row[1]))
            selected = Selection(j, uv, error)
            self.cache[key] = selected
        self.owners[selected.index] = profile
        self.members[index].add(selected.index)
        return selected

    def seal_surfaces(self) -> None:
        """
        Require complete lateral ownership and identify two distinct actual terminal caps.
        """
        if any(not family for family in self.members[:-2]):
            raise RuntimeError("An authored material region lacks native coverage")
        remaining = set(range(len(self.native))) - self.owners.keys()
        if len(remaining) != 2:
            raise RuntimeError("Uncovered native faces or missing terminal caps")
        for i, target in enumerate((self.route.targets.start, self.route.targets.end)):
            selected = self.select(len(self.patches) + i, self.point(target), remaining)
            if selected is None:
                raise RuntimeError("Native terminal cap correspondence failed")
            remaining.remove(selected.index)
        if remaining:
            raise RuntimeError("Native face ownership is incomplete")
        self.sealed = True

    def shared(self, first: int, second: int) -> bool:
        """
        Identify a source material boundary lying within a common native face.
        """
        return bool(self.members[first] & self.members[second])

    def seam_error(self, first: int, second: int, points: tuple[Any, ...]) -> float:
        """
        Measure both sides of a material boundary on their actual trimmed native faces.
        """
        errors = []
        for point in points:
            a, b = self.select(first, point), self.select(second, point)
            if a is None or b is None:
                return math.inf
            errors.extend((a.error_mm, b.error_mm))
        maximum = max(errors)
        self.output["face_correspondence"]["shared_face_seams"].append(
            {"regions": [first, second], "samples": len(points), "maximum_error_mm": maximum}
        )
        return maximum

    def records(self) -> tuple[dict[str, Any], ...]:
        """
        Retain all source regions on each real face without crossing conductor/profile identity.
        """
        output = []
        for index in range(len(self.native)):
            sources = []
            for region, members in enumerate(self.members):
                if index not in members:
                    continue
                if region >= len(self.patches):
                    sources.append({"region": "start" if region == len(self.patches) else "end"})
                else:
                    patch = self.patches[region]
                    sources.append(
                        {
                            "piece_index": patch.piece_index,
                            "region": patch.region,
                            "profile_index": patch.profile_index,
                            "label": patch.profile.label,
                        }
                    )
            if not sources:
                raise RuntimeError("Native face lost material provenance")
            output.append(
                {
                    "sources": sources,
                    "profile_index": self.owners[index] if self.owners[index] >= 0 else None,
                    "label": sources[0].get("label", sources[0]["region"]),
                    "native_face_index": index,
                }
            )
        self.output["face_correspondence"].update(
            face_queries=self.queries,
            edge_parameter_queries=self.edge_queries,
            trim_distance_queries=self.distance_queries,
            native_faces=output,
        )
        return tuple(output)

    def edge_seam_error(
        self, first: int, second: int, points: tuple[Any, ...], *, controls: tuple[Any, ...] = ()
    ) -> float:
        """
        Require a source seam to lie on an actual shared native edge subchain.

        Kernel simplification can extend a native edge beyond a short authored
        material region. Its entire endpoint chain need not equal that subregion;
        every sampled source boundary must still lie on the real shared edges.
        A kernel-collapsed edge instead requires a shared native vertex and the
        entire positive-weight source control hull within the supplied kernel point
        tolerance and dimensional policy. The default remains the original goal;
        coincident unconnected vertices are insufficient.
        Each point may stop after an actual edge distance meets the original
        accuracy goal. That distance is a certified witness bound, not a claim
        of the nearest edge. Warning-only or failed witnesses retain the full
        minimum search. All original samples and the shared query cap remain.
        A real shared Line3D edge can instead certify the positive-weight
        source control hull and every sample through outward distance bounds
        to its actual trimmed endpoints. All original face memberships remain;
        curved/unknown geometry and non-goal bounds retain the original search.
        Other edges may supply a parameter-range-checked, independently measured
        native goal witness for each original sample. These attempts share the
        original raw native-query pool with faces. Misses and warning-only
        residuals retain the complete minimum-distance search and its 512-query cap.
        """
        first_edges = {edge.tempId: edge for edge in self.item(first).edges}
        second_edges = {edge.tempId for edge in self.item(second).edges}
        shared = [edge for key, edge in first_edges.items() if key in second_edges]
        if not shared:
            return self._vertex_seam_error(first, second, points, controls)
        linear = [
            edge
            for edge in shared
            if getattr(getattr(edge, "geometry", None), "objectType", None) == LINE_TYPE
        ]
        if controls and linear:
            world_controls = tuple(point.copy() for point in controls)
            world_points = tuple(point.copy() for point in points)
            for point in (*world_controls, *world_points):
                if not point.transformBy(self.occurrence.transform2):
                    raise RuntimeError("Native line-boundary assembly transform failed")
            for edge in linear:
                certificate = certify_line_boundary(
                    edge.createForAssemblyContext(self.occurrence),
                    world_controls,
                    world_points,
                    self.accuracy.goal_mm,
                    lambda: self.budget.check("actual finite-line control hull"),
                )
                if certificate is not None:
                    if any(
                        self.select(first, point) is None or self.select(second, point) is None
                        for point in points
                    ):
                        return math.inf
                    self.output["face_correspondence"]["native_line_boundaries"].append(
                        {
                            "regions": [first, second],
                            "native_edge": edge.tempId,
                            **asdict(certificate),
                        }
                    )
                    return certificate.maximum_error_mm
        errors = []
        parameter_samples = 0

        def parameter_checkpoint() -> None:
            """
            Share the original thirty-thousand raw native-query pool with face correspondence.
            """
            self.edge_queries += 1
            self.output["face_correspondence"]["edge_parameter_queries"] = self.edge_queries
            if self.queries + self.edge_queries > 30000:
                raise RuntimeError("Material shared native-query budget exhausted")
            self.budget.check("actual shared-edge parameter witness")

        for point in points:
            if self.select(first, point) is None or self.select(second, point) is None:
                return math.inf
            world = point.copy()
            if not world.transformBy(self.occurrence.transform2):
                raise RuntimeError("Native boundary assembly transform failed")
            distances = []
            for edge in shared:
                proxy = edge.createForAssemblyContext(self.occurrence)
                witness = inspect_edge_parameter(
                    proxy, world, self.accuracy.goal_mm, parameter_checkpoint
                )
                if witness is not None:
                    distances.append(witness.error_mm)
                    parameter_samples += 1
                    break
                self.distance_queries += 1
                if self.distance_queries > 512:
                    raise RuntimeError("Material boundary-distance budget exhausted")
                self.budget.check("actual shared-edge subchain")
                distance = self.distance(world, proxy)
                distances.append(distance)
                if 0.0 <= distance <= self.accuracy.goal_mm:
                    break
            errors.append(min(distances))
        maximum = max(errors)
        self.output["face_correspondence"]["native_edge_subchains"].append(
            {
                "regions": [first, second],
                "edges": [edge.tempId for edge in shared],
                "samples": len(points),
                "maximum_error_mm": maximum,
                "distance_policy": "original_goal_witness_else_full_minimum",
                "parameter_witness_samples": parameter_samples,
            }
        )
        return maximum

    def _vertex_seam_error(
        self, first: int, second: int, points: tuple[Any, ...], controls: tuple[Any, ...]
    ) -> float:
        """
        Certify a collapsed material boundary through actual shared vertex identity and strict bounds.

        Controls come from the authored positive-weight seam, whose curve lies
        inside their convex hull. A caller may supply the kernel's point tolerance
        for measured collapsed topology, independently bounded by dimensional
        acceptance. Preserve the original goal in the record; a larger accepted
        residual is still a seam accuracy warning. Never create or weld topology.
        """
        if not points or not controls:
            return math.inf
        vertices = []
        for region in (first, second):
            vertices.append(
                {
                    vertex.tempId: vertex
                    for edge in self.item(region).edges
                    for vertex in (edge.startVertex, edge.endVertex)
                }
            )
        candidates = []
        for key in sorted(vertices[0].keys() & vertices[1].keys()):
            self.budget.check("actual collapsed seam vertex")
            vertex = vertices[0][key]
            distances = tuple(vertex.geometry.distanceTo(point) * 10 for point in controls)
            if all(
                self.accuracy.accepts(value) and value <= self.collapsed_boundary_tolerance_mm
                for value in distances
            ):
                candidates.append((max(distances), key))
        if not candidates:
            return math.inf
        bound, vertex_id = min(candidates)
        errors = [bound]
        for point in points:
            a, b = self.select(first, point), self.select(second, point)
            if (
                a is None
                or b is None
                or not all(
                    self.accuracy.accepts(value) and value <= self.collapsed_boundary_tolerance_mm
                    for value in (a.error_mm, b.error_mm)
                )
            ):
                return math.inf
            errors.extend((a.error_mm, b.error_mm))
        maximum = max(errors)
        self.output["face_correspondence"]["native_vertex_boundaries"].append(
            {
                "regions": [first, second],
                "vertex": vertex_id,
                "controls": len(controls),
                "samples": len(points),
                "control_hull_bound_mm": bound,
                "maximum_error_mm": maximum,
                "goal_mm": self.accuracy.goal_mm,
                "collapsed_boundary_tolerance_mm": self.collapsed_boundary_tolerance_mm,
            }
        )
        return maximum


# Native evaluator method names are fixed by Fusion's public API.
# noinspection PyPep8Naming
class Family:
    """
    Delegate evaluation to a selected real face and expose the region's outer edge union.
    """

    def __init__(self, collection: MaterialFaces, index: int) -> None:
        """
        Bind one material region; no synthetic native geometry or edges are created.
        """
        self.collection, self.index = collection, index
        self.active: Selection | None = None
        self.evaluator: Any = self

    @property
    def geometry(self) -> Any:
        """
        Expose the selected native support only after a successful physical query.
        """
        if self.active is None:
            raise RuntimeError("Material region has no selected native face")
        return self.collection.native[self.active.index].geometry

    @property
    def edges(self) -> list[Any]:
        """
        Keep real exterior edges, excluding edges internal to a split native family.
        """
        edges: dict[int, Any] = {}
        counts: dict[int, int] = {}
        for index in self.collection.members[self.index]:
            for edge in self.collection.native[index].edges:
                edges[edge.tempId] = edge
                counts[edge.tempId] = counts.get(edge.tempId, 0) + 1
        return [edge for key, edge in edges.items() if counts[key] == 1]

    def getParameterAtPoint(self, point: Any) -> tuple[bool, Any]:
        """
        Select an actual trimmed face and retain its unmodified native UV parameter.
        """
        self.active = self.collection.select(self.index, point)
        return (True, self.active.uv) if self.active is not None else (False, None)

    def isParameterOnFace(self, uv: Any) -> bool:
        """
        Report selected raw membership or independently measured trim-distance correspondence.
        """
        return self.active is not None and uv == self.active.uv

    def getPointAtParameter(self, uv: Any) -> tuple[bool, Any]:
        """
        Evaluate the real selected native face; never substitute the planned point.
        """
        if self.active is None:
            return False, None
        return self.collection.native[self.active.index].evaluator.getPointAtParameter(uv)

    def getNormalAtPoint(self, point: Any) -> tuple[bool, Any]:
        """
        Read the actual oriented cap normal from its registered native face.
        """
        selected = self.collection.select(self.index, point)
        if selected is None:
            return False, None
        self.active = selected
        return self.collection.native[selected.index].evaluator.getNormalAtPoint(point)

    def createForAssemblyContext(self, occurrence: Any) -> Any:
        """
        Delegate a corroboration query to the actual selected native face.
        """
        if self.active is None:
            raise RuntimeError("Material region has no selected native face")
        return self.collection.native[self.active.index].createForAssemblyContext(occurrence)
