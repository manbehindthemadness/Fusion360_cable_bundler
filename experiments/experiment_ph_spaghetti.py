"""
Define and screen a deterministic PH hairpin/twist stress matrix locally.

The corresponding live Fusion probe is experiment_ph_spaghetti_sweep.py.
These scenarios are experimental and do not change production routing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from experiments.experiment_ph_quintic import (
    HermiteCase,
    _sample_metrics,
    ph_hermite_candidates,
)


@dataclass(frozen=True)
class StressCase:
    """
    Specify one isolated PH-projection sweep and its cross section in mm.
    """

    name: str
    separation_mm: float
    profile: str
    twist_degrees: float = 0.0
    lateral_displacement_mm: float = 0.0


def stress_cases() -> tuple[StressCase, ...]:
    """
    Span tight reversals, roll, and lateral displacement with fixed tangents.
    """
    cases = [
        StressCase(f"radius_h{height:g}_{profile}", height, profile)
        for profile in ("circle_3mm", "ribbon_10x0p5mm")
        for height in (2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 30, 60)
    ]
    cases.extend(
        StressCase(f"roll_h{height:g}_a{angle:g}", height, "ribbon_10x0p5mm", angle)
        for height in (5, 10, 20)
        for angle in (45, 90, 135, 180, 270, 360)
    )
    cases.extend(
        StressCase(
            f"lateral_h{height:g}_d{displacement:g}_a{angle:g}",
            height,
            "ribbon_10x0p5mm",
            angle,
            displacement,
        )
        for height in (5, 10, 20)
        for displacement in (5, 15, 30)
        for angle in (0, 90, 180)
    )
    return tuple(cases)


def hermite_case(stress: StressCase) -> HermiteCase:
    """
    Hold both endpoint derivative magnitudes at 25 mm per parameter unit.
    """
    return HermiteCase(
        stress.name,
        complex(0.0, stress.separation_mm),
        25 + 0j,
        -25 + 0j,
    )


def run() -> dict[str, object]:
    """
    Record planar branch-0 screening for all 69 Fusion stress cases.
    """
    report: dict[str, object] = {"cases": []}
    for stress in stress_cases():
        case = hermite_case(stress)
        curve = ph_hermite_candidates(case)[0]
        metrics = _sample_metrics(
            curve.point_at,
            curve.derivative_at,
            curve.curvature_at,
            case,
            curve.exact_length_mm(),
        )
        curvature = float(metrics["maximum_sampled_curvature_per_mm"])
        report["cases"].append(
            {
                "name": stress.name,
                "separation_mm": stress.separation_mm,
                "profile": stress.profile,
                "twist_degrees": stress.twist_degrees,
                "lateral_displacement_mm": stress.lateral_displacement_mm,
                "curve_type": (
                    "planar_ph_quintic"
                    if stress.lateral_displacement_mm == 0.0
                    else "planar_ph_projection_with_non_ph_polynomial_z"
                ),
                "planar_exact_length_mm": curve.exact_length_mm(),
                "planar_minimum_sampled_radius_mm": metrics["minimum_sampled_radius_mm"],
                "planar_nonlocal_clearance_margin_for_circle_mm": metrics[
                    "sampled_nonlocal_clearance_margin_mm"
                ],
                "planar_circle_sampled_legal": metrics["sampled_legal"],
                "untwisted_planar_ribbon_local_fold_margin": 1.0 - 0.25 * curvature,
                "planar_absolute_turn_degrees": metrics["sampled_absolute_turn_degrees"],
            }
        )
    output = Path(__file__).resolve().parents[1] / "artifacts/verification/ph_spaghetti_math.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"cases": len(report["cases"]), "report": str(output)}, sort_keys=True))
    return report


if __name__ == "__main__":
    run()
