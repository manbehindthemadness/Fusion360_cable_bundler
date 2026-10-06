"""
Freeze historical connection targets before comparing the cap-transition candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_ribbon_diagnosis.compact import length_bounds
from experiments.experiment_ribbon_diagnosis.end_sections import CappedConnectionTurns
from experiments.experiment_ribbon_diagnosis.preflight import EndPlan
from experiments.experiment_secure_discrete_ribbon.bank import bank_ribbon_frames
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.frames import ribbon_frames
from experiments.experiment_secure_discrete_ribbon.shape import RibbonEndFit, RibbonShape

from .accuracy import separate_length_goals
from .checks import inspect_samples
from .ends import align_branch_cap
from .solver import solve_candidate


@dataclass
class FrozenTargetTurns(CappedConnectionTurns):
    """
    Adapt cap handles of registered branches without regenerating their targets.
    """

    fixed_routes: dict[str, RoutePreview] = field(default_factory=dict)

    def __call__(
        self, center: Vector3, inward: Vector3, bend: Vector3, radius_mm: float, name: str
    ) -> RoutePreview:
        """
        Reuse fixed connection geometry and change only the cap-side handle.
        """
        del bend
        original = self.fixed_routes.get(name)
        if original is None:
            raise ValueError("The candidate branch has no registered fixed target.")
        if (
            center != original.curves[-1].end
            or radius_mm != 8 * self.case.lines * self.case.diameter_mm
        ):
            raise ValueError("The candidate branch changed its registered cap or fixture radius.")
        return align_branch_cap(original, inward)


def freeze_targets(
    case: RibbonStressCase,
    start_fit: RibbonEndFit,
    end_fit: RibbonEndFit,
    *,
    fixture: CappedConnectionTurns | None = None,
) -> FrozenTargetTurns:
    """
    Author every historical connection before any candidate result is observed.
    """
    frames = bank_ribbon_frames(
        ribbon_frames(
            case.route,
            case.start_width,
            case.end_width,
            endpoint_tangents=(
                case.route.curves[0].derivative(0),
                case.route.curves[-1].derivative(1),
            )
            if fixture is not None
            else None,
        ),
        case.lines,
        case.diameter_mm,
    )
    historical = fixture or CappedConnectionTurns(case, turn_degrees=15)
    routes = {}
    for index, fit in ((0, start_fit), (-1, end_fit)):
        frame = frames[index]
        sign = 1 if index == 0 else -1
        inward = Vector3(sign * frame.tangent.x, sign * frame.tangent.y, sign * frame.tangent.z)
        bend = Vector3(sign * frame.thickness.x, sign * frame.thickness.y, sign * frame.thickness.z)
        for lane, center in enumerate(fit.centers):
            name = f"{case.name} end {index} pin {lane + 1}"
            routes[name] = historical(center, inward, bend, 8 * case.lines * case.diameter_mm, name)
    return FrozenTargetTurns(case, turn_degrees=15, fixed_routes=routes)


class ShortConnectionFixture(CappedConnectionTurns):
    """
    Author fixed fifteen-degree endings of radius four conductor diameters.

    No post-solve scaling or minimum-length clamping occurs. Every resulting
    branch still needs the same curvature, complete-length and boundary checks.
    """

    def __call__(
        self, center: Vector3, inward: Vector3, bend: Vector3, radius_mm: float, name: str
    ) -> RoutePreview:
        """
        Ignore the historical requested radius in favor of the declared fixture.
        """
        del radius_mm
        return self._turn(center, inward, bend, 4 * self.case.diameter_mm, name)


def inspect_candidate(shape: RibbonShape, plan: EndPlan) -> dict[str, object]:
    """
    Add a combined per-end sampled allowance check to the retained preflight.

    Material lengths follow sampled lanes through the end-lead support; branch
    lengths use cubic bounds. Native interpolation and continuous geometry remain
    unresolved. Both end portions are included in each complete-lane denominator.
    One-percent length goals warn but do not reject experimental geometry.
    """
    report = plan.inspect(shape)
    distances = [0.0]
    for left, right in zip(shape.frames, shape.frames[1:]):
        distances.append(distances[-1] + magnitude(difference(right.origin, left.origin)))
    complete_lower = list(shape.lengths_mm)
    branch_upper: dict[tuple[int, int], float] = {}
    for end_index in (0, -1):
        for lane in range(len(shape.lanes)):
            name = f"{plan.case.name} end {end_index} pin {lane + 1}"
            lower, upper = length_bounds(plan.routes[name].curves)
            complete_lower[lane] += lower
            branch_upper[end_index, lane] = upper
    failures = report["failures"]
    if not isinstance(failures, list):
        raise TypeError("End preflight failures must be a list.")
    historical = [
        failure
        for failure in failures
        if failure == "internal_end_region_exceeds_six_percent"
        or str(failure).endswith(":branch_length")
    ]
    failures[:] = [failure for failure in failures if failure not in historical]
    report["historical_trunk_only_allowance_findings"] = historical
    combined = []
    for end_index, label in ((0, "A"), (-1, "B")):
        for lane, points in enumerate(shape.lanes):
            fitted_length = 0.0
            for station, (left, right) in enumerate(zip(points, points[1:])):
                start_distance, end_distance = distances[station : station + 2]
                covered = (
                    min(end_distance, shape.end_lead_mm) - start_distance
                    if end_index == 0
                    else end_distance - max(start_distance, distances[-1] - shape.end_lead_mm)
                )
                if covered > 0:
                    fitted_length += (
                        magnitude(difference(right, left))
                        * covered
                        / (end_distance - start_distance)
                    )
            end_length = fitted_length + branch_upper[end_index, lane]
            maximum = 0.06 * complete_lower[lane]
            if end_length > maximum + 1e-9:
                failures.append(f"end_{label}_lane_{lane + 1}:combined_end_region_length")
            combined.append(
                {
                    "end": label,
                    "lane": lane + 1,
                    "sampled_internal_plus_branch_mm": end_length,
                    "maximum_mm": maximum,
                }
            )
    report["combined_end_regions"] = combined
    report["occupied_and_lane_checks"], sample_failures = inspect_samples(shape, plan)
    failures.extend(sample_failures)
    separate_length_goals(report, shape.spread)
    report["verdict"] = "reject" if failures else "unresolved"
    report["construction"] = (
        "Not attempted; fixed-target plans retained for later native construction."
    )
    return report


def prepare_candidate(
    case: RibbonStressCase,
    start_fit: RibbonEndFit,
    end_fit: RibbonEndFit,
    *,
    fixture: CappedConnectionTurns | None = None,
) -> tuple[RibbonShape, EndPlan, dict[str, object]]:
    """
    Freeze targets, solve once, and inspect the complete candidate branch plan.
    """
    turns = freeze_targets(case, start_fit, end_fit, fixture=fixture)
    shape = solve_candidate(case, start_fit, end_fit)
    plan = EndPlan(case, turns)
    return shape, plan, inspect_candidate(shape, plan)
