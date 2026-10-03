"""
Compare a swept-profile local-fold screen with observed Fusion sweep outcomes.

Run locally as ``python -m experiments.experiment_ph_macaroni_limit`` after
the PH spaghetti Fusion experiments. This script creates no Fusion geometry.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from experiments.experiment_ph_quintic import HermiteCase, PhQuintic, ph_hermite_candidates


@dataclass(frozen=True)
class ObservedSweep:
    """
    Keep only the geometry and outcome required for a local-fold comparison.
    """

    name: str
    separation_mm: float
    derivative_mm: float
    profile: str
    roll_degrees: float
    result: str
    source: str
    ribbon_width_mm: float = 10.0


def _load_cases(path: Path, source: str) -> tuple[ObservedSweep, ...]:
    """
    Validate and select planar circular/ribbon sweeps from one Fusion report.
    """
    report = json.loads(path.read_text(encoding="utf-8"))
    entries = report.get("cases") if isinstance(report, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"{path} has no case list.")
    observations: list[ObservedSweep] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{path} contains a malformed case.")
        if entry.get("lateral_displacement_mm") != 0.0:
            continue
        profile = entry.get("profile")
        if profile not in ("circle_3mm", "ribbon_10x0p5mm"):
            continue
        name = entry.get("name")
        result = entry.get("result")
        separation = entry.get("separation_mm")
        derivative = entry.get("derivative_mm", 25.0)
        roll = entry.get("twist_degrees")
        ribbon_width = entry.get("ribbon_width_mm", 10.0)
        if (
            not isinstance(name, str)
            or result not in ("solid", "failed")
            or not isinstance(separation, (int, float))
            or not isinstance(derivative, (int, float))
            or not isinstance(roll, (int, float))
            or not isinstance(ribbon_width, (int, float))
            or ribbon_width <= 0.0
        ):
            raise ValueError(f"{path} contains incomplete geometry or outcome data.")
        observations.append(
            ObservedSweep(
                name,
                float(separation),
                float(derivative),
                profile,
                float(roll),
                result,
                source,
                float(ribbon_width),
            )
        )
    return tuple(observations)


def _arc_fractions(curve: PhQuintic, intervals: int) -> list[float]:
    """
    Approximate traveled distance fractions from the PH polynomial speed.
    """
    speeds = [abs(curve.derivative_at(index / intervals)) for index in range(intervals + 1)]
    cumulative = [0.0]
    for first, second in zip(speeds, speeds[1:]):
        cumulative.append(cumulative[-1] + (first + second) / (2.0 * intervals))
    length = cumulative[-1]
    if length <= 0.0:
        raise ValueError("The PH curve has no positive arc length.")
    return [distance / length for distance in cumulative]


def _inward_extent_mm(profile: str, ribbon_width_mm: float, roll_radians: float) -> float:
    """
    Return the rectangular support toward planar curvature, or circle radius.

    At zero roll the 10 mm ribbon width is vertical and only its 0.5 mm
    thickness projects into the XY bend plane.
    """
    if profile == "circle_3mm":
        return 1.5
    return (ribbon_width_mm / 2.0) * abs(math.sin(roll_radians)) + 0.25 * abs(
        math.cos(roll_radians)
    )


def _utilization(
    curve: PhQuintic, observation: ObservedSweep, fractions: list[float]
) -> dict[str, float]:
    """
    Find the largest curvature-times-inward-reach value along the centerline.
    """
    intervals = len(fractions) - 1
    best_score = -math.inf
    best_parameter = 0.0
    best_roll = 0.0
    for index, arc_fraction in enumerate(fractions):
        parameter = index / intervals
        angle = math.radians(observation.roll_degrees * arc_fraction)
        inward_extent = _inward_extent_mm(observation.profile, observation.ribbon_width_mm, angle)
        score = abs(curve.curvature_at(parameter)) * inward_extent
        if score > best_score:
            best_score = score
            best_parameter = parameter
            best_roll = math.degrees(angle)
    return {
        "maximum_curvature_times_inward_extent": best_score,
        "peak_parameter": best_parameter,
        "roll_at_peak_degrees": best_roll,
    }


def run() -> dict[str, object]:
    """
    Compare parameter-linear and arc-length-linear roll against Fusion results.
    """
    root = Path(__file__).resolve().parents[1]
    report_paths = (
        ("broad", root / "artifacts/verification/ph_spaghetti_fusion.json"),
        ("refine", root / "artifacts/verification/ph_spaghetti_refine.json"),
    )
    observations = tuple(
        observation for source, path in report_paths for observation in _load_cases(path, source)
    )
    cases: list[dict[str, object]] = []
    intervals = 8192
    for observation in observations:
        hermite = HermiteCase(
            observation.name,
            complex(0.0, observation.separation_mm),
            complex(observation.derivative_mm, 0.0),
            complex(-observation.derivative_mm, 0.0),
        )
        curve = ph_hermite_candidates(hermite)[0]
        by_parameter = _utilization(
            curve, observation, [index / intervals for index in range(intervals + 1)]
        )
        by_arc_length = _utilization(curve, observation, _arc_fractions(curve, intervals))
        cases.append(
            {
                "name": observation.name,
                "source": observation.source,
                "profile": observation.profile,
                "separation_mm": observation.separation_mm,
                "derivative_mm": observation.derivative_mm,
                "ribbon_width_mm": observation.ribbon_width_mm,
                "roll_degrees": observation.roll_degrees,
                "fusion_result": observation.result,
                "parameter_linear": by_parameter,
                "arc_length_linear": by_arc_length,
                "parameter_prediction": (
                    "failed"
                    if by_parameter["maximum_curvature_times_inward_extent"] >= 1.0
                    else "solid"
                ),
                "arc_length_prediction": (
                    "failed"
                    if by_arc_length["maximum_curvature_times_inward_extent"] >= 1.0
                    else "solid"
                ),
            }
        )
    report: dict[str, object] = {"cases": cases, "sample_intervals": intervals}
    for law, field in (
        ("parameter_linear", "parameter_prediction"),
        ("arc_length_linear", "arc_length_prediction"),
    ):
        mismatches = [case["name"] for case in cases if case[field] != case["fusion_result"]]
        report[f"{law}_mismatches"] = mismatches
    output = root / "artifacts/verification/ph_macaroni_limit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    holdouts = (
        ("h5_w10_roll25", 5.0, 10.0, 25.0),
        ("h5_w10_roll27p5", 5.0, 10.0, 27.5),
        ("h5_w10_roll32p5", 5.0, 10.0, 32.5),
        ("h5_w10_roll35", 5.0, 10.0, 35.0),
        ("h5_w10_roll37p5", 5.0, 10.0, 37.5),
        ("h10_w10_roll92", 10.0, 10.0, 92.0),
        ("h10_w10_roll95", 10.0, 10.0, 95.0),
        ("h10_w10_roll97", 10.0, 10.0, 97.0),
        ("h5_w8_roll35", 5.0, 8.0, 35.0),
        ("h5_w8_roll40", 5.0, 8.0, 40.0),
        ("h5_w12_roll25", 5.0, 12.0, 25.0),
        ("h5_w12_roll30", 5.0, 12.0, 30.0),
    )
    planned: list[dict[str, object]] = []
    for name, separation, width, roll in holdouts:
        observation = ObservedSweep(
            name, separation, 25.0, "ribbon_10x0p5mm", roll, "unrun", "holdout", width
        )
        curve = ph_hermite_candidates(
            HermiteCase(name, complex(0.0, separation), 25 + 0j, -25 + 0j)
        )[0]
        parameter = _utilization(
            curve, observation, [index / intervals for index in range(intervals + 1)]
        )
        arc_length = _utilization(curve, observation, _arc_fractions(curve, intervals))
        planned.append(
            {
                "name": name,
                "separation_mm": separation,
                "derivative_mm": 25.0,
                "ribbon_width_mm": width,
                "twist_degrees": roll,
                "parameter_linear": parameter,
                "arc_length_linear": arc_length,
                "parameter_prediction": (
                    "failed"
                    if parameter["maximum_curvature_times_inward_extent"] >= 1.0
                    else "solid"
                ),
                "arc_length_prediction": (
                    "failed"
                    if arc_length["maximum_curvature_times_inward_extent"] >= 1.0
                    else "solid"
                ),
            }
        )
    plan_output = root / "artifacts/verification/ph_macaroni_holdout_plan.json"
    plan_output.write_text(
        json.dumps({"cases": planned}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cases": len(cases),
                "parameter_mismatches": len(report["parameter_linear_mismatches"]),
                "arc_length_mismatches": len(report["arc_length_linear_mismatches"]),
                "report": str(output),
                "holdout_plan": str(plan_output),
            },
            sort_keys=True,
        )
    )
    return report


if __name__ == "__main__":
    run()
