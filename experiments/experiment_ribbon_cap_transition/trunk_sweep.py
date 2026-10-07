"""
Construct an experimental constant-profile trunk using Fusion's twist sweep.

The native twist interpolation is not the numerical quintic frame field. Two
cap sketches are diagnostic references, not guide rails or sweep constraints.
"""

from __future__ import annotations

import math
from types import ModuleType

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import CableGroupDefinition
from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane
from cable_bundler.routing import RibbonShape


def build_trunk_sweep(
    builder: ModuleType,
    degrees: float,
    component: adsk.fusion.Component,
    center_path: adsk.fusion.Path,
    shape: RibbonShape,
    group: CableGroupDefinition,
    transform: adsk.core.Matrix3D,
    guide_planes: tuple[RibbonGuidePlane | None, RibbonGuidePlane | None],
) -> tuple[
    adsk.fusion.SweepFeature,
    tuple[adsk.fusion.Sketch, ...],
    tuple[adsk.fusion.ConstructionPlane, ...],
]:
    """
    Sweep one original start contour once, retaining both exact cap references.

    No loft fallback, rail, profile scaling, section deformation or cleanup of
    failed diagnostic inputs occurs. Reject a missing or non-positive solid.
    """
    if not math.isfinite(degrees):
        raise ValueError("Sweep twist must be finite.")
    sections = []
    planes = []
    for index, fit, guide in (
        (0, shape.start_fit, guide_planes[0]),
        (len(shape.frames) - 1, shape.end_fit, guide_planes[1]),
    ):
        if fit is None:
            raise ValueError("Both fixed cap fits are required for the sweep diagnostic.")
        section, plane = builder._add_section(
            component,
            center_path,
            shape.frames[index],
            group,
            transform,
            path_fraction=index / (len(shape.frames) - 1),
            lane_centers=tuple(lane[index] for lane in shape.lanes),
            lane_normals=fit.normals,
            end_fit=fit,
            guide_plane=guide,
        )
        sections.append(section)
        planes.append(plane)
    sweep_input = component.features.sweepFeatures.createInput(
        sections[0].profiles.item(0),
        center_path,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    sweep_input.twistAngle = adsk.core.ValueInput.createByReal(math.radians(degrees))
    sweep = component.features.sweepFeatures.add(sweep_input)
    if sweep is None or sweep.bodies.count != 1:
        raise RuntimeError("Fusion did not return a single swept trunk.")
    body = sweep.bodies.item(0)
    if not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
        raise RuntimeError("Fusion did not return a positive-volume swept solid.")
    sweep.name = f"Trunk sweep - {degrees:g}deg requested twist"
    return sweep, tuple(sections), tuple(planes)
