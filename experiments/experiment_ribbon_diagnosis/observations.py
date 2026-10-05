"""
Measure the actual sketch coordinates passed to the copied production builder.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
from types import ModuleType

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import CableGroupDefinition
from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane
from cable_bundler.routing import RibbonEndFit, RibbonFrame, Vector3
from cable_bundler.routing.geometry import difference, dot, unit


class PlanePolicy(Enum):
    """
    Compare original path planes with planes of the unchanged sampled frames.
    """

    PATH = "original_path_planes"
    FRAME = "sampled_frame_planes"


def angle_degrees(first: Vector3, second: Vector3) -> float:
    """
    Return the unsigned normal mismatch, independent of normal polarity.
    """
    return math.degrees(math.acos(min(1.0, abs(dot(unit(first), unit(second))))))


@dataclass
class SectionRecord:
    """
    Preserve measurements and exact authored arc triplets before cleanup.
    """

    number: int
    frame: RibbonFrame
    maximum_off_plane_mm: float = 0.0
    normal_error_degrees: float = 0.0
    frame_origin_plane_distance_mm: float = 0.0
    plane_origin_mm: tuple[float, float, float] | None = None
    plane_normal: tuple[float, float, float] | None = None
    maximum_arc_endpoint_displacement_mm: float = 0.0
    profile_count: int | None = None
    error: str | None = None
    points_mm: list[tuple[float, float, float]] = field(default_factory=list)

    def summary(self) -> dict[str, object]:
        """
        Keep the report compact while retaining failed-profile reproduction data.
        """
        result = asdict(self)
        result["authored_point_count"] = len(self.points_mm)
        if self.error is None:
            result.pop("points_mm")
        return result


@dataclass
class SectionObserver:
    """
    Instrument private copied bindings and restore them even after a kernel error.

    PATH forwards inputs unchanged. FRAME changes only the interior sketch plane;
    lane points, cap guides, frame count, banking, folding, and loft calls agree.
    """

    builder: ModuleType
    policy: PlanePolicy
    records: list[SectionRecord] = field(default_factory=list)
    current: SectionRecord | None = None
    original_point: Callable[..., adsk.core.Point3D] = field(init=False)
    original_section: Callable[..., tuple[adsk.fusion.Sketch, adsk.fusion.ConstructionPlane]] = (
        field(init=False)
    )

    def __post_init__(self) -> None:
        """
        Capture originals without changing any module yet.
        """
        self.original_point = self.builder._lane_section_point
        self.original_section = self.builder._add_section

    def install(self) -> None:
        """
        Replace only this experiment's private loaded functions.
        """
        self.builder._lane_section_point = self.point
        self.builder._add_section = self.section

    def restore(self) -> None:
        """
        Restore the two private functions after one case.
        """
        self.builder._lane_section_point = self.original_point
        self.builder._add_section = self.original_section

    def point(
        self,
        section: adsk.fusion.Sketch,
        frame: RibbonFrame,
        centers: tuple[Vector3, ...],
        normals: tuple[Vector3, ...],
        end_fit: RibbonEndFit | None,
        across_mm: float,
        height_mm: float,
        diameter_mm: float,
        transform: adsk.core.Matrix3D,
    ) -> adsk.core.Point3D:
        """
        Observe sketch Z before returning the identical point to arc construction.
        """
        point = self.original_point(
            section, frame, centers, normals, end_fit, across_mm, height_mm, diameter_mm, transform
        )
        if self.current is not None:
            record = self.current
            record.maximum_off_plane_mm = max(record.maximum_off_plane_mm, abs(point.z) * 10)
            world = section.sketchToModelSpace(point)
            record.points_mm.append((world.x * 10, world.y * 10, world.z * 10))
            origin = section.sketchToModelSpace(adsk.core.Point3D.create(0, 0, 0))
            tip = section.sketchToModelSpace(adsk.core.Point3D.create(0, 0, 1))
            normal = Vector3(tip.x - origin.x, tip.y - origin.y, tip.z - origin.z)
            record.plane_origin_mm = (origin.x * 10, origin.y * 10, origin.z * 10)
            record.plane_normal = (normal.x, normal.y, normal.z)
            record.normal_error_degrees = angle_degrees(normal, frame.tangent)
            delta = difference(frame.origin, Vector3(origin.x * 10, origin.y * 10, origin.z * 10))
            record.frame_origin_plane_distance_mm = abs(dot(delta, unit(normal)))
        return point

    def section(
        self,
        component: adsk.fusion.Component,
        route_curve: adsk.fusion.Path,
        frame: RibbonFrame,
        group: CableGroupDefinition,
        transform: adsk.core.Matrix3D,
        offsets_mm: tuple[float, ...] = (),
        path_fraction: float = 0.0,
        lane_centers: tuple[Vector3, ...] = (),
        lane_normals: tuple[Vector3, ...] = (),
        end_fit: RibbonEndFit | None = None,
        guide_plane: RibbonGuidePlane | None = None,
    ) -> tuple[adsk.fusion.Sketch, adsk.fusion.ConstructionPlane]:
        """
        Record actual point/plane discrepancies for successful and rejected sections.
        """
        record = SectionRecord(len(self.records) + 1, frame)
        self.records.append(record)
        self.current = record
        if self.policy is PlanePolicy.FRAME and guide_plane is None:
            guide_plane = RibbonGuidePlane(frame.origin, frame.tangent)
        try:
            result = self.original_section(
                component,
                route_curve,
                frame,
                group,
                transform,
                offsets_mm=offsets_mm,
                path_fraction=path_fraction,
                lane_centers=lane_centers,
                lane_normals=lane_normals,
                end_fit=end_fit,
                guide_plane=guide_plane,
            )
            record.profile_count = result[0].profiles.count
            for index, arc in enumerate(result[0].sketchCurves.sketchArcs):
                expected = record.points_mm[index * 3 : index * 3 + 3]
                if len(expected) != 3:
                    continue
                actual = (arc.startSketchPoint.worldGeometry, arc.endSketchPoint.worldGeometry)
                endpoints = tuple((point.x * 10, point.y * 10, point.z * 10) for point in actual)
                deviation = min(
                    max(math.dist(endpoints[0], first), math.dist(endpoints[1], last))
                    for first, last in ((expected[0], expected[2]), (expected[2], expected[0]))
                )
                record.maximum_arc_endpoint_displacement_mm = max(
                    record.maximum_arc_endpoint_displacement_mm, deviation
                )
            return result
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            record.error = str(error)
            raise
        finally:
            self.current = None

    def retain_profiles(self, component: adsk.fusion.Component) -> int:
        """
        Recreate exact observed arc triplets as evidence after native cleanup.

        These sketches are diagnostic copies only and never feed another loft.
        Off-plane coordinates are deliberately preserved in 3D.
        """
        count = 0
        for record in self.records:
            if not record.points_mm:
                continue
            sketch = component.sketches.add(component.xYConstructionPlane)
            sketch.name = f"Observed section {record.number} — diagnostic evidence"
            for index in range(0, len(record.points_mm) - 2, 3):
                points = tuple(
                    sketch.modelToSketchSpace(adsk.core.Point3D.create(x / 10, y / 10, z / 10))
                    for x, y, z in record.points_mm[index : index + 3]
                )
                sketch.sketchCurves.sketchArcs.addByThreePoints(*points)
            sketch.isLightBulbOn = record.error is not None
            count += 1
        return count
