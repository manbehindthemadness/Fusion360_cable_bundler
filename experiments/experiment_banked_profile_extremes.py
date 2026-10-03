"""
Measure both signed bend-normal extremes of banked sweep profiles.

Run locally with ``python -m experiments.experiment_banked_profile_extremes``.
The geometry calculation is independent of Fusion; the companion Fusion
experiment compares these predictions with actual solid-sweep outcomes.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from experiments.experiment_ph_quintic import HermiteCase, ph_hermite_candidates


@dataclass(frozen=True)
class ProfileShape:
    """
    Describe a convex cross-section in the starting normal/vertical plane.
    """

    name: str
    vertices_mm: tuple[tuple[float, float], ...] = ()
    circle_radius_mm: float = 0.0


SHAPES = (
    ProfileShape("circle_r2", circle_radius_mm=2.0),
    ProfileShape("rectangle_8x0p5", ((-0.25, -4.0), (0.25, -4.0), (0.25, 4.0), (-0.25, 4.0))),
    ProfileShape("triangle_8x1", ((-0.25, -4.0), (0.75, 0.0), (-0.25, 4.0))),
)
BANKS_DEGREES = (0.0, 30.0, 60.0, 90.0, 120.0, 150.0)
SEPARATIONS_MM = (5.0, 10.0)


def normal_extremes_mm(shape: ProfileShape, bank_degrees: float) -> tuple[float, float]:
    """
    Return positive reach toward the left and right path normals.

    Each polygon extremum occurs at a vertex. The circle is rotationally
    invariant. The two reaches need not agree for an asymmetric shape.
    """
    if shape.circle_radius_mm > 0.0:
        return shape.circle_radius_mm, shape.circle_radius_mm
    if len(shape.vertices_mm) < 3:
        raise ValueError("A polygon profile needs at least three vertices.")
    radians = math.radians(bank_degrees)
    projected = [
        normal * math.cos(radians) - vertical * math.sin(radians)
        for normal, vertical in shape.vertices_mm
    ]
    return max(projected), -min(projected)


def _curvature_bounds(separation_mm: float) -> tuple[float, float]:
    """
    Sample signed curvature on the established branch-zero PH reversal.
    """
    curve = ph_hermite_candidates(
        HermiteCase(
            f"bank_h{separation_mm:g}",
            complex(0.0, separation_mm),
            25.0 + 0j,
            -25.0 + 0j,
        )
    )[0]
    curvatures = [curve.curvature_at(index / 4096) for index in range(4097)]
    return min(curvatures), max(curvatures)


def cases() -> list[dict[str, float | str]]:
    """
    Build fixed-bank Fusion cases with exact cross-section support values.
    """
    rows: list[dict[str, float | str]] = []
    for separation in SEPARATIONS_MM:
        minimum_curvature, maximum_curvature = _curvature_bounds(separation)
        for shape in SHAPES:
            for bank in BANKS_DEGREES:
                left, right = normal_extremes_mm(shape, bank)
                local_load = max(maximum_curvature * left, -minimum_curvature * right)
                rows.append(
                    {
                        "name": f"bank_h{separation:g}_{shape.name}_a{bank:g}",
                        "separation_mm": separation,
                        "shape": shape.name,
                        "bank_degrees": bank,
                        "left_reach_mm": left,
                        "right_reach_mm": right,
                        "curvature_min_per_mm": minimum_curvature,
                        "curvature_max_per_mm": maximum_curvature,
                        "local_fold_load": local_load,
                        "return_leg_gap_estimate_mm": separation - 2.0 * left,
                    }
                )
    return rows


def twist_cases() -> list[dict[str, float | str]]:
    """
    Predict swept extremes under parameter- and distance-linear twist laws.

    Fusion does not document its internal twist distribution, so these are
    comparison hypotheses, not claims about its actual swept frame.
    """
    rows: list[dict[str, float | str]] = []
    intervals = 2048
    for separation in SEPARATIONS_MM:
        curve = ph_hermite_candidates(
            HermiteCase(
                f"twist_h{separation:g}",
                complex(0.0, separation),
                25.0 + 0j,
                -25.0 + 0j,
            )
        )[0]
        parameters = [index / intervals for index in range(intervals + 1)]
        speeds = [abs(curve.derivative_at(parameter)) for parameter in parameters]
        cumulative = [0.0]
        for first, second in zip(speeds, speeds[1:]):
            cumulative.append(cumulative[-1] + (first + second) / (2.0 * intervals))
        fractions = [distance / cumulative[-1] for distance in cumulative]
        curvatures = [curve.curvature_at(parameter) for parameter in parameters]
        for shape in SHAPES:
            for twist in (90.0, 180.0, 360.0):
                row: dict[str, float | str] = {
                    "name": f"twist_h{separation:g}_{shape.name}_a{twist:g}",
                    "separation_mm": separation,
                    "shape": shape.name,
                    "bank_degrees": 0.0,
                    "twist_degrees": twist,
                }
                for law, positions in (("parameter", parameters), ("distance", fractions)):
                    loads: list[float] = []
                    for curvature, position in zip(curvatures, positions):
                        left, right = normal_extremes_mm(shape, twist * position)
                        loads.append(max(curvature * left, -curvature * right))
                    row[f"{law}_local_fold_load"] = max(loads)
                start_left, _ = normal_extremes_mm(shape, 0.0)
                end_left, _ = normal_extremes_mm(shape, twist)
                row["return_leg_gap_estimate_mm"] = separation - start_left - end_left
                rows.append(row)
    return rows


def run() -> dict[str, object]:
    """
    Save a preregistered geometry prediction before any Fusion sweeps.
    """
    report: dict[str, object] = {
        "cases": cases(),
        "twist_cases": twist_cases(),
        "model": "signed normal support, fixed bank or hypothesized twist distribution",
    }
    root = Path(__file__).resolve().parents[1]
    output = root / "artifacts/verification/banked_profile_extremes_math.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "cases": len(report["cases"]),
                "twist_cases": len(report["twist_cases"]),
                "report": str(output),
            },
            sort_keys=True,
        )
    )
    return report


if __name__ == "__main__":
    run()
