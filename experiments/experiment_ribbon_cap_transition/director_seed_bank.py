"""
Rank a fixed generic intrinsic-shape bank using endpoint poses alone.

Only one selected seed receives nonlinear refinement. Seed screenings are counted
separately from refinement and do not add independent geometry configurations.
"""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, difference, dot

from .director_rotation_transport import integrate_rotation
from .director_routing_field import RoutingField
from .director_transport import DirectorPath
from .endpoint_first import EndpointCase


class NoAdmissibleSeed(ValueError):
    """
    Signal bounded initialization exhaustion,not infeasible endpoint geometry.
    """

    def __init__(self, message: str, *, seed_ranking: tuple[dict[str, Any], ...] = ()) -> None:
        """
        Preserve rejected screening outcomes when initialization cannot return metrics.
        """
        super().__init__(message)
        self.seed_ranking = seed_ranking


def candidates() -> tuple[tuple[float, ...], ...]:
    """
    Freeze44generic signed arc/return/reversal starts,independent of case identity.
    """
    result = []
    for angle in (-2 * math.pi, -math.pi, -math.pi / 2, math.pi / 2, math.pi, 2 * math.pi):
        for rule in (-0.4, 0.0, 0.4):
            result.append((angle, 0.0, 0.0, 0.0, 0.0, rule, 0.0, 0.0, 0.0, 1.0))
        for rule in (-0.5, 0.5):
            result.append((angle, 0.0, 0.0, 0.0, 0.0, 0.0, rule, 0.0, 0.0, 1.0))
    for angle in (-math.pi, math.pi):
        for rule in (-0.4, 0.0, 0.4):
            result.append((angle, -angle, 0.0, 0.0, 0.0, rule, 0.0, 0.0, 0.0, 1.0))
    for angle in (-1.5 * math.pi, -math.pi, math.pi, 1.5 * math.pi):
        for rule in (-0.5, 0.5):
            result.append((0.0, 0.0, angle, 0.0, 0.0, 0.0, rule, 0.0, 0.0, 1.0))
    return tuple(result)


def ranked_seed(
    case: EndpointCase,
    extra: tuple[tuple[float, ...], ...],
    build: Callable[[tuple[float, ...]], RoutingField],
    score: Callable[[DirectorPath], tuple[float, ...]],
    checkpoint: Callable[[], None],
    *,
    admissibility: Callable[[DirectorPath], bool] | None = None,
    minimum_length_ratio: Callable[[DirectorPath], float] | None = None,
    maximum_length_ratio: float = 5.0,
) -> tuple[tuple[float, ...], dict[str, Any]]:
    """
    Screen44fixed profiles plus two geometry-derived starts on64steps each.

    For each fixed normalized shape,choose arc length by one bounded scalar
    projection onto its A-edge displacement. Rotation is independent of length
    in the FREEfield family. Rescale positions/rates algebraically,then score
    the actual candidate with the same endpoint/geometry residual. No solver
    coordinates,witness geometry or prior result enters this bank. An optional
    admissibility filter restricts selection without adding seeds or screenings;
    all rejections remain in the ranking. NoAdmissibleSeed means this bank was
    exhausted,not that no valid route exists.
    A caller may supply a minimum length ratio from the normalized shape. The
    supplied upper ratio(default5)remains fixed;exceeding it rejects that seed.
    """
    if not math.isfinite(maximum_length_ratio) or maximum_length_ratio < 1:
        raise ValueError("Seed maximum length ratio must be finite and at least one.")
    started = perf_counter()
    half = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    initial = (
        case.start.x,
        case.start.y,
        case.start.z,
        case.start_tangent.x,
        case.start_tangent.y,
        case.start_tangent.z,
        case.start_width.x,
        case.start_width.y,
        case.start_width.z,
    )
    best = None
    best_error = math.inf
    rows = []
    for index, values in enumerate(candidates() + extra):
        checkpoint()
        normalized = values[:9] + (1.0,)
        path = integrate_rotation(build(normalized), 64, checkpoint, initial=initial)
        last = path.states[-1]
        delta = difference(Vector3(*last[:3]), case.start)
        target = case.end.translated(case.end_width, half).translated(Vector3(*last[6:9]), -half)
        target_delta = difference(target, case.start)
        denominator = dot(delta, delta)
        ratio = (
            max(1.0, min(maximum_length_ratio, dot(delta, target_delta) / denominator))
            if denominator > 1e-12
            else 1.0
        )
        floor = 1.0 if minimum_length_ratio is None else minimum_length_ratio(path)
        if not math.isfinite(floor) or floor < 1:
            raise ValueError("Seed length floors must be finite and at least one.")
        if floor > maximum_length_ratio:
            rows.append(
                {
                    "index": index,
                    "score": None,
                    "length_ratio": ratio,
                    "minimum_length_ratio": floor,
                    "admissible": False,
                    "disposition": "minimum length exceeds frozen upper bound",
                }
            )
            continue
        ratio = max(ratio, floor)
        selected = normalized[:9] + (ratio,)
        states = tuple(
            tuple(initial[j] + ratio * (s[j] - initial[j]) if j < 3 else s[j] for j in range(9))
            for s in path.states
        )
        rates = tuple(tuple(ratio * v if j < 3 else v for j, v in enumerate(r)) for r in path.rates)
        scaled = DirectorPath(build(selected), states, rates)
        errors = score(scaled)
        error = sum(value * value for value in errors)
        admissible = admissibility is None or admissibility(scaled)
        row = {"index": index, "score": error, "length_ratio": ratio}
        if admissibility is not None:
            row["admissible"] = admissible
        if minimum_length_ratio is not None:
            row["minimum_length_ratio"] = floor
        rows.append(row)
        if admissible and error < best_error:
            best, best_error = selected, error
    if best is None:
        if admissibility is not None or minimum_length_ratio is not None:
            raise NoAdmissibleSeed(
                "No admissible seed in the fixed generic bank.", seed_ranking=tuple(rows)
            )
        raise RuntimeError("No finite generic director seed.")
    return best, {
        "seed_screenings": len(rows),
        "seed_seconds": perf_counter() - started,
        "seed_ranking": rows,
        "seed_score": best_error,
    }
