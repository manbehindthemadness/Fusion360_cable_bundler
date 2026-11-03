"""
Track authored material regions across native face merging without changing geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from devtools.ribbon_analysis.budget import NativeBudget
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.material_surfaces import MaterialPatch


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
    ) -> None:
        """
        Cache native bounds once; keep the supplied solid and all entity identities untouched.
        """
        self.body, self.route, self.patches = body, route, patches
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
        self.cache: dict[tuple[int, float, float, float], Selection] = {}
        output["face_correspondence"] = {
            "native_face_count": len(self.native),
            "material_region_count": len(self.families),
            "policy": "Actual trimmed-face membership/distance and unique profile ownership",
            "trim_distance_corroborations": [],
            "shared_face_seams": [],
            "native_edge_subchains": [],
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
        Find a true trimmed-face witness within the unchanged1e-6mm fidelity tolerance.

        Evaluate cheap raw memberships first. Only their collective failure invokes
        actual trimmed-face distance. Source interior samples may claim unowned faces;
        sealed boundary queries use the established profile ownership exclusively.
        """
        profile = self.patches[index].profile_index if index < len(self.patches) else -index
        key = (profile, point.x, point.y, point.z)
        selected = self.cache.get(key)
        if selected is None:
            candidates: list[tuple[float, int, Any]] = []
            pending: list[tuple[float, int, Any]] = []
            for j, (face, box) in enumerate(zip(self.native, self.boxes)):
                if allowed is not None and j not in allowed:
                    continue
                owner = self.owners.get(j)
                if owner is not None and owner != profile:
                    continue
                if self.sealed and owner is None:
                    continue
                if not all(
                    low - 1e-7 <= getattr(point, a) <= high + 1e-7
                    for a, (low, high) in zip("xyz", box)
                ):
                    continue
                self.queries += 1
                if self.queries > 30000:
                    raise RuntimeError("Material face-query budget exhausted")
                ok, uv = face.evaluator.getParameterAtPoint(point)
                if not ok:
                    continue
                ok, actual = face.evaluator.getPointAtParameter(uv)
                error = actual.distanceTo(point) * 10 if ok else math.inf
                if error > 1e-6:
                    continue
                target = candidates if face.evaluator.isParameterOnFace(uv) else pending
                target.append((error, j, uv))
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
                    if error <= 1e-6:
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
            trim_distance_queries=self.distance_queries,
            native_faces=output,
        )
        return tuple(output)

    def edge_seam_error(self, first: int, second: int, points: tuple[Any, ...]) -> float:
        """
        Require a source seam to lie on an actual shared native edge subchain.

        Kernel simplification can extend a native edge beyond a short authored
        material region. Its entire endpoint chain need not equal that subregion;
        every sampled source boundary must still lie on the real shared edges.
        """
        first_edges = {edge.tempId: edge for edge in self.item(first).edges}
        second_edges = {edge.tempId for edge in self.item(second).edges}
        shared = [edge for key, edge in first_edges.items() if key in second_edges]
        if not shared:
            return math.inf
        errors = []
        for point in points:
            if self.select(first, point) is None or self.select(second, point) is None:
                return math.inf
            world = point.copy()
            world.transformBy(self.occurrence.transform2)
            distances = []
            for edge in shared:
                self.distance_queries += 1
                if self.distance_queries > 512:
                    raise RuntimeError("Material boundary-distance budget exhausted")
                self.budget.check("actual shared-edge subchain")
                distances.append(
                    self.distance(world, edge.createForAssemblyContext(self.occurrence))
                )
            errors.append(min(distances))
        maximum = max(errors)
        self.output["face_correspondence"]["native_edge_subchains"].append(
            {
                "regions": [first, second],
                "edges": [edge.tempId for edge in shared],
                "samples": len(points),
                "maximum_error_mm": maximum,
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
        Report the selected raw-membership or separately recorded strict trim-distance proof.
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
