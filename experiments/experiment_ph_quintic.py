"""
Measure planar PH quintic Hermite candidates before attempting Fusion sweeps.

Run locally with the project interpreter. This experiment has no Fusion import,
changes no product code, and writes an ignored JSON report.
"""

from __future__ import annotations

import cmath
import json
import math
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from time import perf_counter_ns
from typing import Callable


@dataclass(frozen=True)
class HermiteCase:
    """
    Define one planar endpoint-and-derivative routing challenge in millimeters.
    """

    name: str
    end: complex
    start_derivative: complex
    end_derivative: complex
    wire_radius_mm: float = 1.5
    minimum_bend_radius_mm: float = 12.0
    clearance_mm: float = 0.5


@dataclass(frozen=True)
class PhQuintic:
    """
    Retain the complex quadratic preimage and exact quintic Bézier controls.
    """

    preimage: tuple[complex, complex, complex]
    controls: tuple[complex, complex, complex, complex, complex, complex]

    def preimage_at(self, parameter: float) -> complex:
        """
        Evaluate the quadratic preimage on the unit interval.
        """
        first, middle, last = self.preimage
        other = 1.0 - parameter
        return first * other * other + 2.0 * middle * other * parameter + last * parameter**2

    def preimage_derivative_at(self, parameter: float) -> complex:
        """
        Evaluate the derivative of the quadratic preimage.
        """
        first, middle, last = self.preimage
        return 2.0 * ((middle - first) * (1.0 - parameter) + (last - middle) * parameter)

    def point_at(self, parameter: float) -> complex:
        """
        Evaluate the exact quintic using de Casteljau interpolation.
        """
        return _bezier_at(self.controls, parameter)

    def derivative_at(self, parameter: float) -> complex:
        """
        Return the PH hodograph, the square of the preimage.
        """
        return self.preimage_at(parameter) ** 2

    def curvature_at(self, parameter: float) -> float:
        """
        Return signed curvature, or infinity at a stationary/cusp parameter.
        """
        preimage = self.preimage_at(parameter)
        squared_speed = abs(preimage) ** 2
        if squared_speed < 1e-16:
            return math.inf
        numerator = 2.0 * (preimage.conjugate() * self.preimage_derivative_at(parameter)).imag
        return numerator / squared_speed**2

    def exact_length_mm(self) -> float:
        """
        Integrate the polynomial speed in its degree-four Bernstein basis.
        """
        speed_controls = [0.0] * 5
        for first_index, first in enumerate(self.preimage):
            for second_index, second in enumerate(self.preimage):
                index = first_index + second_index
                factor = (
                    math.comb(2, first_index) * math.comb(2, second_index) / math.comb(4, index)
                )
                speed_controls[index] += factor * (first * second.conjugate()).real
        return sum(speed_controls) / 5.0


def _bezier_at(controls: tuple[complex, ...], parameter: float) -> complex:
    """
    Evaluate a Bézier control polygon without an external math dependency.
    """
    active = list(controls)
    while len(active) > 1:
        active = [
            left * (1.0 - parameter) + right * parameter for left, right in zip(active, active[1:])
        ]
    return active[0]


def ph_hermite_candidates(case: HermiteCase) -> tuple[PhQuintic, ...]:
    """
    Enumerate four planar C1 Hermite solutions from the PH preimage equation.

    The endpoint derivatives prescribe magnitudes as well as directions. A
    tangent-direction-only problem needs a separate choice of these magnitudes.
    """
    delta = case.end
    if abs(delta) < 1e-9 or abs(case.start_derivative) < 1e-9 or abs(case.end_derivative) < 1e-9:
        raise ValueError("PH Hermite interpolation needs distinct ends and nonzero derivatives.")
    first_root = cmath.sqrt(case.start_derivative)
    last_root = cmath.sqrt(case.end_derivative)
    candidates: list[PhQuintic] = []
    for last_sign in (1.0, -1.0):
        first = first_root
        last = last_root * last_sign
        discriminant = 120.0 * delta - 15.0 * (first**2 + last**2) + 10.0 * first * last
        discriminant_root = cmath.sqrt(discriminant)
        for middle_sign in (1.0, -1.0):
            middle = (-3.0 * (first + last) + middle_sign * discriminant_root) / 4.0
            hodograph = (
                first**2,
                first * middle,
                (first * last + 2.0 * middle**2) / 3.0,
                middle * last,
                last**2,
            )
            controls = [0j]
            for value in hodograph:
                controls.append(controls[-1] + value / 5.0)
            curve = PhQuintic((first, middle, last), tuple(controls))
            if abs(curve.controls[-1] - case.end) > 1e-8 * max(1.0, abs(case.end)):
                raise ArithmeticError("The PH control polygon missed its Hermite endpoint.")
            candidates.append(curve)
    return tuple(candidates)


def _cubic_controls(case: HermiteCase) -> tuple[complex, ...]:
    """
    Construct the ordinary cubic with the same endpoint derivative vectors.
    """
    return (
        0j,
        case.start_derivative / 3.0,
        case.end - case.end_derivative / 3.0,
        case.end,
    )


def _cubic_derivative(controls: tuple[complex, ...], parameter: float) -> complex:
    """
    Differentiate a cubic Bézier control polygon analytically.
    """
    derivative = tuple(3.0 * (right - left) for left, right in zip(controls, controls[1:]))
    return _bezier_at(derivative, parameter)


def _cubic_curvature(controls: tuple[complex, ...], parameter: float) -> float:
    """
    Evaluate signed curvature of the ordinary cubic comparator.
    """
    derivative = _cubic_derivative(controls, parameter)
    if abs(derivative) < 1e-8:
        return math.inf
    second_controls = tuple(
        6.0 * (controls[index + 2] - 2.0 * controls[index + 1] + controls[index])
        for index in range(2)
    )
    second_derivative = _bezier_at(second_controls, parameter)
    return (derivative.conjugate() * second_derivative).imag / abs(derivative) ** 3


def _simpson(values: list[float]) -> float:
    """
    Integrate uniformly sampled values over the unit interval.
    """
    intervals = len(values) - 1
    if intervals % 2:
        raise ValueError("Simpson integration requires an even interval count.")
    return (values[0] + values[-1] + 4.0 * sum(values[1:-1:2]) + 2.0 * sum(values[2:-1:2])) / (
        3.0 * intervals
    )


def _sample_metrics(
    point_at: Callable[[float], complex],
    derivative_at: Callable[[float], complex],
    curvature_at: Callable[[float], float],
    case: HermiteCase,
    exact_length_mm: float | None = None,
) -> dict[str, object]:
    """
    Compare analytic PH length with sampled curvature and clearance heuristics.

    The sampled maxima and nonlocal distance are exploratory, not certified
    extrema or a proof that a three-dimensional swept envelope is disjoint.
    """
    intervals = 512
    parameters = [index / intervals for index in range(intervals + 1)]
    points = [point_at(parameter) for parameter in parameters]
    derivatives = [derivative_at(parameter) for parameter in parameters]
    speeds = [abs(value) for value in derivatives]
    curvatures = [curvature_at(parameter) for parameter in parameters]
    sampled_length = _simpson(speeds)
    length = exact_length_mm if exact_length_mm is not None else sampled_length
    energy_values = [
        curvature**2 * speed if math.isfinite(curvature) else math.inf
        for curvature, speed in zip(curvatures, speeds)
    ]
    bending_energy = _simpson(energy_values)
    maximum_curvature = max(abs(value) for value in curvatures)
    cumulative = [0.0]
    for first, second in zip(speeds, speeds[1:]):
        cumulative.append(cumulative[-1] + (first + second) / (2.0 * intervals))
    nonlocal_cutoff = 0.25 * length
    minimum_nonlocal = math.inf
    for first_index, first in enumerate(points):
        for second_index in range(first_index + 1, len(points)):
            if cumulative[second_index] - cumulative[first_index] < nonlocal_cutoff:
                continue
            minimum_nonlocal = min(minimum_nonlocal, abs(points[second_index] - first))
    absolute_turn_degrees = sum(
        abs(
            math.degrees(
                math.atan2(
                    (first.conjugate() * second).imag,
                    (first.conjugate() * second).real,
                )
            )
        )
        for first, second in zip(derivatives, derivatives[1:])
        if abs(first) > 1e-9 and abs(second) > 1e-9
    )
    minimum_radius = 1.0 / maximum_curvature if maximum_curvature > 0.0 else math.inf
    local_margin = 1.0 - case.wire_radius_mm * maximum_curvature
    nonlocal_margin_mm = minimum_nonlocal - (2.0 * case.wire_radius_mm + case.clearance_mm)
    return {
        "exact_length_mm": exact_length_mm,
        "sampled_length_mm": sampled_length,
        "relative_length_error": (
            abs(sampled_length - exact_length_mm) / exact_length_mm
            if exact_length_mm is not None
            else None
        ),
        "maximum_sampled_curvature_per_mm": maximum_curvature,
        "minimum_sampled_radius_mm": minimum_radius if math.isfinite(minimum_radius) else None,
        "start_curvature_per_mm": curvatures[0],
        "end_curvature_per_mm": curvatures[-1],
        "sampled_bending_energy_per_mm": bending_energy if math.isfinite(bending_energy) else None,
        "sampled_absolute_turn_degrees": absolute_turn_degrees,
        "sampled_nonlocal_distance_mm": minimum_nonlocal,
        "nonlocal_exclusion_arclength_mm": nonlocal_cutoff,
        "local_profile_margin": local_margin,
        "sampled_nonlocal_clearance_margin_mm": nonlocal_margin_mm,
        "sampled_legal": (
            minimum_radius >= case.minimum_bend_radius_mm
            and local_margin > 0.0
            and nonlocal_margin_mm > 0.0
        ),
    }


def benchmark_cases() -> tuple[HermiteCase, ...]:
    """
    Return the fixed planar cases shared by local and live Fusion experiments.
    """
    root_two = math.sqrt(2.0)
    return (
        HermiteCase("straight", 80 + 0j, 80 + 0j, 80 + 0j),
        HermiteCase("turn_90", 60 + 60j, 80 + 0j, 80j),
        HermiteCase("turn_135", 40 + 80j, 85 + 0j, 85 * (-1 + 1j) / root_two),
        HermiteCase("hairpin_180", 0 + 60j, 75 + 0j, -75 + 0j),
        HermiteCase("tight_hairpin_180", 0 + 5j, 25 + 0j, -25 + 0j),
        HermiteCase("s_turn", 80 + 20j, 90 + 0j, 90 + 0j),
        HermiteCase("offset_reversal", 20 + 30j, 65 + 0j, -65 + 0j),
    )


def run() -> dict[str, object]:
    """
    Benchmark known endpoint states and every PH branch against a cubic.
    """
    report: dict[str, object] = {"cases": []}
    for case in benchmark_cases():
        started = perf_counter_ns()
        candidates = ph_hermite_candidates(case)
        construction_ms = (perf_counter_ns() - started) / 1e6
        assessed: list[dict[str, object]] = []
        for index, curve in enumerate(candidates):
            started = perf_counter_ns()
            metrics = _sample_metrics(
                curve.point_at,
                curve.derivative_at,
                curve.curvature_at,
                case,
                curve.exact_length_mm(),
            )
            metrics["analysis_ms"] = (perf_counter_ns() - started) / 1e6
            metrics["branch"] = index
            metrics["controls_mm"] = [[point.real, point.imag] for point in curve.controls]
            metrics["endpoint_error_mm"] = abs(curve.controls[-1] - case.end)
            metrics["start_derivative_error"] = abs(
                curve.derivative_at(0.0) - case.start_derivative
            )
            metrics["end_derivative_error"] = abs(curve.derivative_at(1.0) - case.end_derivative)
            assessed.append(metrics)
        cubic = _cubic_controls(case)
        cubic_metrics = _sample_metrics(
            partial(_bezier_at, cubic),
            partial(_cubic_derivative, cubic),
            partial(_cubic_curvature, cubic),
            case,
        )
        legal = [candidate for candidate in assessed if candidate["sampled_legal"]]
        pool = legal or assessed
        preferred = min(
            pool,
            key=lambda item: (
                item["sampled_absolute_turn_degrees"],
                item["sampled_bending_energy_per_mm"],
                item["sampled_length_mm"],
            ),
        )
        report["cases"].append(
            {
                "name": case.name,
                "end_mm": [case.end.real, case.end.imag],
                "start_derivative_mm": [case.start_derivative.real, case.start_derivative.imag],
                "end_derivative_mm": [case.end_derivative.real, case.end_derivative.imag],
                "wire_radius_mm": case.wire_radius_mm,
                "minimum_bend_radius_mm": case.minimum_bend_radius_mm,
                "candidate_construction_ms": construction_ms,
                "preferred_branch": preferred["branch"],
                "has_sampled_legal_branch": bool(legal),
                "candidates": assessed,
                "cubic": cubic_metrics,
            }
        )
    output = Path(__file__).resolve().parents[1] / "artifacts/verification/ph_quintic_math.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cases": len(report["cases"]),
                "sampled_legal": sum(case["has_sampled_legal_branch"] for case in report["cases"]),
                "report": str(output),
            },
            sort_keys=True,
        )
    )
    return report


if __name__ == "__main__":
    run()
