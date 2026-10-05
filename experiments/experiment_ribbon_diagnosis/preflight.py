"""
Plan reverse-loft endings and reject known rule violations before native lofting.

These checks do not certify Fusion's interpolation or continuous material strain.
Absence of a known violation therefore remains unresolved, never a predicted pass.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from cable_bundler.routing import RibbonShape
from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import (
    UnsafeRibbon,
    certify_curvature,
    discrete_profile_reach,
)

from .compact import length_bounds
from .end_sections import CappedConnectionTurns


@dataclass
class EndPlan:
    """
    Freeze the authored branch routes before construction and reuse them verbatim.
    """

    case: RibbonStressCase
    turns: CappedConnectionTurns
    routes: dict[str, RoutePreview] = field(default_factory=dict)
    inputs: dict[str, tuple[Vector3, Vector3, Vector3, float]] = field(default_factory=dict)

    def __call__(
        self, center: Vector3, inward: Vector3, bend: Vector3, radius_mm: float, name: str
    ) -> RoutePreview:
        """
        Refuse construction requests that differ from the checked plan.
        """
        if self.inputs.get(name) != (center, inward, bend, radius_mm):
            raise ValueError("Reverse-loft inputs differ from the pre-build end plan.")
        return self.routes[name]

    def inspect(self, shape: RibbonShape) -> dict[str, object]:
        """
        Check trunk and all endings even when the trunk is already rejected.

        The six-percent allowance also constrains the internal fitted-end region.
        Final lane lengths include both branches. Endpoint coincidence and cap
        approach are checked separately from the unproven loft tangent behavior.
        """
        self.routes.clear()
        self.inputs.clear()
        failures: list[str] = []
        try:
            trunk_certificate = asdict(
                certify_curvature(
                    self.case.route,
                    discrete_profile_reach(self.case.lines, self.case.diameter_mm),
                )
            )
        except UnsafeRibbon as error:
            trunk_certificate = {"rejected": str(error)}
            failures.append("trunk_input_curvature")
        if not shape.meets_length_target:
            failures.append("trunk_lane_length_spread")
        trunk_lower, _ = length_bounds(self.case.route.curves)
        if shape.end_lead_mm > 0.06 * trunk_lower + 1e-9:
            failures.append("internal_end_region_exceeds_six_percent")
        if (
            shape.minimum_end_radius_mm is not None
            and shape.minimum_end_radius_mm < 3 * self.case.diameter_mm - 1e-6
        ):
            failures.append("sampled_fitted_end_radius_below_trial_minimum")
        if shape.maximum_pitch_ratio > 1.03 + 1e-9:
            failures.append("neighbor_pitch")
        totals = list(shape.lengths_mm)
        endings: list[dict[str, object]] = []
        width = self.case.lines * self.case.diameter_mm
        for index, label, fit in ((0, "A", shape.start_fit), (-1, "B", shape.end_fit)):
            if fit is None:
                failures.append(f"missing_end_fit_{label}")
                continue
            frame = shape.frames[index]
            sign = 1 if index == 0 else -1
            inward = Vector3(
                *(sign * v for v in (frame.tangent.x, frame.tangent.y, frame.tangent.z))
            )
            bend = Vector3(
                *(sign * v for v in (frame.thickness.x, frame.thickness.y, frame.thickness.z))
            )
            for lane, center in enumerate(fit.centers):
                name = f"{self.case.name} end {index} pin {lane + 1}"
                route = self.turns(center, inward, bend, 8 * width, name)
                self.inputs[name] = (center, inward, bend, 8 * width)
                self.routes[name] = route
                lower, upper = length_bounds(route.curves)
                totals[lane] += (lower + upper) / 2
                findings: list[str] = []
                try:
                    certificate = asdict(certify_curvature(route, self.case.diameter_mm))
                except UnsafeRibbon as error:
                    certificate = {"rejected": str(error)}
                    findings.append("branch_curvature")
                if upper > 0.06 * trunk_lower + 1e-9:
                    findings.append("branch_length")
                gap = magnitude(difference(route.curves[-1].end, shape.lanes[lane][index]))
                if gap > 1e-7:
                    findings.append("cap_position")
                normal = fit.approach_normal
                alignment = (
                    abs(dot(unit(route.curves[-1].derivative(1)), unit(normal)))
                    if normal is not None and magnitude(normal) > 1e-12
                    else 0.0
                )
                angle = math.degrees(math.acos(min(1.0, max(0.0, alignment))))
                if alignment < 1 - 1e-7:
                    findings.append("cap_approach_direction")
                failures.extend(f"end_{label}_lane_{lane + 1}:{reason}" for reason in findings)
                endings.append(
                    {
                        "end": label,
                        "lane": lane + 1,
                        "findings": findings,
                        "curvature": certificate,
                        "cap_gap_mm": gap,
                        "cap_normal_error_degrees": angle,
                        "length_upper_mm": upper,
                    }
                )
        spread = (max(totals) - min(totals)) / max(totals)
        if spread > 0.01 + 1e-9:
            failures.append("complete_sampled_lane_length_spread")
        return {
            "verdict": "reject" if failures else "unresolved",
            "failures": failures,
            "trunk_curvature": trunk_certificate,
            "internal_end_lead_mm": shape.end_lead_mm,
            "maximum_end_region_mm": 0.06 * trunk_lower,
            "complete_sampled_lane_spread": spread,
            "endings": endings,
            "construction": "Unmodified copied reverse loft; planned routes reused verbatim.",
            "kernel_prediction": "unresolved",
            "unresolved": [
                "continuous final-path curvature and strain",
                "global clearance",
                "shortest feasible route",
                "native loft interpolation and join continuity",
            ],
        }
