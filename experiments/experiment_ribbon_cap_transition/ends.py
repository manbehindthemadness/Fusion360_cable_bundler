"""
Apply lane-specific smooth cap corrections without moving authored targets.

The correction field has zero added second derivative at its boundaries.
Neither this field nor its samples certify the native loft interpolation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_secure_discrete_ribbon.shape import RibbonEndFit, ribbon_line_lengths


def cap_direction(normal: Vector3, toward: Vector3) -> Vector3:
    """
    Orient a finite cap normal toward a specified non-tangential route direction.
    """
    for vector in (normal, toward):
        if not all(math.isfinite(v) for v in (vector.x, vector.y, vector.z)):
            raise ValueError("Cap directions must be finite.")
        if magnitude(vector) <= 1e-8:
            raise ValueError("Cap directions must be nonzero.")
    alignment = dot(unit(normal), unit(toward))
    if abs(alignment) <= 1e-8:
        raise ValueError("The route direction is tangent to its cap plane.")
    direction = unit(normal)
    sign = -1 if alignment < 0 else 1
    return Vector3(sign * direction.x, sign * direction.y, sign * direction.z)


def correction_weights(distance_mm: float, lead_mm: float) -> tuple[float, float]:
    """
    Return quintic position and derivative weights on a bounded physical lead.

    Position weight has zero first and second derivatives at both boundaries.
    Derivative weight has unit first derivative at the cap, zero at the join,
    and zero second derivative at both. Outside the lead both weights are zero.
    """
    if not math.isfinite(lead_mm) or lead_mm <= 0:
        raise ValueError("A cap correction requires a positive finite lead.")
    if not math.isfinite(distance_mm) or distance_mm < 0:
        raise ValueError("Cap distance must be finite and nonnegative.")
    if distance_mm >= lead_mm:
        return 0.0, 0.0
    u = distance_mm / lead_mm
    return 1 - 10 * u**3 + 15 * u**4 - 6 * u**5, lead_mm * (u - 6 * u**3 + 8 * u**4 - 3 * u**5)


@dataclass(frozen=True)
class SmoothCapTransition:
    """
    Bound end support and correct each lane's own sampled entry direction.

    Six percent of the shortest input lane is a conservative authoring cap,
    not a certificate of the final complete end region. Combined trunk/end
    lengths and curvature must still be audited after branch planning.
    """

    exact_inward: tuple[Vector3, Vector3] | None = None
    fits: tuple[RibbonEndFit, RibbonEndFit] | None = None

    def _needs_correction(self, lanes: tuple[tuple[Vector3, ...], ...]) -> bool:
        """
        Require support unless exact translated-lane geometry proves it unnecessary.
        """
        if self.exact_inward is None or self.fits is None:
            return True
        for index, fit, inward in zip((0, -1), self.fits, self.exact_inward):
            if fit.approach_normal is None or len(fit.centers) != len(lanes):
                return True
            if dot(cap_direction(fit.approach_normal, inward), unit(inward)) < 1 - 1e-10:
                return True
            if any(
                magnitude(difference(lane[index], target)) > 1e-8
                for lane, target in zip(lanes, fit.centers)
            ):
                return True
        return False

    def lead_length_mm(
        self, historical_lead_mm: float, lanes: tuple[tuple[Vector3, ...], ...]
    ) -> float:
        """
        Cap the old width-based support without imposing a minimum end length.
        """
        if not self._needs_correction(lanes):
            return 0.0
        return min(historical_lead_mm, 0.06 * min(ribbon_line_lengths(lanes)))

    def blend(
        self,
        lanes: tuple[tuple[Vector3, ...], ...],
        fit: RibbonEndFit | None,
        *,
        at_start: bool,
        distances_mm: tuple[float, ...],
        lead_mm: float,
    ) -> tuple[tuple[Vector3, ...], ...]:
        """
        Fit each ordered cap center with a lane-specific smooth correction field.

        Reject missing or unusable cap data. Tangents are estimated from input
        lane samples; native endpoint tangency remains an unmeasured property.
        """
        if fit is None:
            return lanes
        if not lanes or len(fit.centers) != len(lanes) or len(fit.normals) != len(lanes):
            raise ValueError("The cap must supply every ordered lane.")
        if fit.approach_normal is None:
            raise ValueError("The cap requires its actual plane normal.")
        if len(distances_mm) < 2 or any(len(lane) != len(distances_mm) for lane in lanes):
            raise ValueError("Cap lane samples and distances must agree.")
        if any(not math.isfinite(d) for d in distances_mm) or any(
            b <= a for a, b in zip(distances_mm, distances_mm[1:])
        ):
            raise ValueError("Cap sample distances must be finite and strictly increasing.")
        if distances_mm[0] != 0.0:
            raise ValueError("Cap sample distances must start at zero.")
        end_index, next_index = (0, 1) if at_start else (-1, -2)
        total = distances_mm[-1]
        first_span = distances_mm[1] - distances_mm[0] if at_start else total - distances_mm[-2]
        middle_lane = lanes[len(lanes) // 2]
        desired = cap_direction(
            fit.approach_normal, difference(middle_lane[next_index], middle_lane[end_index])
        )
        origin = fit.centers[0]
        for point in (*fit.centers, *(point for lane in lanes for point in lane)):
            if not all(math.isfinite(v) for v in (point.x, point.y, point.z)):
                raise ValueError("Cap centers and lane samples must be finite.")
        if any(abs(dot(difference(center, origin), desired)) > 1e-7 for center in fit.centers):
            raise ValueError("Ordered cap centers must share the actual cap plane.")
        for normal in fit.normals:
            if (
                not all(math.isfinite(v) for v in (normal.x, normal.y, normal.z))
                or magnitude(normal) <= 1e-8
            ):
                raise ValueError("Cap lobe normals must be finite and nonzero.")
            if abs(dot(unit(normal), desired)) > 1e-7:
                raise ValueError("Cap lobe normals must lie in the actual cap plane.")
        adjusted = []
        for lane, target in zip(lanes, fit.centers):
            inward = difference(lane[next_index], lane[end_index])
            if magnitude(inward) <= 1e-8:
                raise ValueError("A cap lane has no usable sampled entry direction.")
            speed = magnitude(inward) / first_span
            derivative = Vector3(
                inward.x / first_span, inward.y / first_span, inward.z / first_span
            )
            if self.exact_inward is not None:
                derivative = self.exact_inward[0 if at_start else 1]
                speed = magnitude(derivative)
            tangent_delta = difference(
                Vector3(desired.x * speed, desired.y * speed, desired.z * speed), derivative
            )
            displacement = difference(target, lane[end_index])
            if lead_mm == 0:
                if magnitude(displacement) > 1e-8 or magnitude(tangent_delta) > 1e-8:
                    raise ValueError(
                        "A zero-support cap must already match exact position and tangent."
                    )
                adjusted.append(lane)
                continue
            points = []
            for index, point in enumerate(lane):
                distance = (
                    distances_mm[index] - distances_mm[0]
                    if at_start
                    else total - distances_mm[index]
                )
                position_weight, tangent_weight = correction_weights(distance, lead_mm)
                points.append(
                    point.translated(displacement, position_weight).translated(
                        tangent_delta, tangent_weight
                    )
                )
            adjusted.append(tuple(points))
        return tuple(adjusted)


def align_branch_cap(route: RoutePreview, inward: Vector3) -> RoutePreview:
    """
    Align the last cap handle while preserving connection position and orientation.

    The terminal target, its first handle, cap center, identity and span order
    remain fixed. The changed cubic needs fresh curvature and length checks.
    """
    if not route.curves:
        raise ValueError("A cap branch requires at least one cubic.")
    last = route.curves[-1]
    direction = cap_direction(inward, inward)
    if dot(direction, last.derivative(1)) <= 0:
        raise ValueError("The cap handle cannot reverse the branch arrival direction.")
    handle = magnitude(difference(last.end, last.control_b))
    if not math.isfinite(handle) or handle <= 1e-8:
        raise ValueError("A cap branch requires a positive finite endpoint handle.")
    aligned = replace(last, control_b=last.end.translated(direction, -handle))
    return replace(route, curves=(*route.curves[:-1], aligned))
