"""
Observe the unchanged shared certificate's first rejection without replacing it.

One frozen degree-nine crossover, one certificate call,257fixed analytic samples,
ten seconds/two GiB, no search/repair/retries/native builds/report files. The trace
hook captures the actual rejected interval's local variables and restores tracing.
"""

from __future__ import annotations

import hashlib
import math
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from types import FrameType
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, difference, lerp, magnitude
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon

from .clamped_comparison import _sources
from .endpoint_cap_acceleration import cap_acceleration_controls
from .endpoint_first import certify, derivative, evaluate
from .endpoint_reference import reference_cases
from .native_budget import NativeBudget

_state: dict[str, Any] | None = None


def probe_certificate(
    points: tuple[Vector3, ...], reach: float, center: Vector3, radius: float
) -> dict[str, Any]:
    """
    Observe one real certificate call and sample the same frozen analytic curve.

    Never override an existing debugger/tracer. A ten-second/4096interval observation
    ceiling stops this diagnostic rather than changing the certificate's decisions.
    Sampling can demonstrate violations; it cannot certify unsampled locations.
    """
    if sys.gettrace() is not None:
        raise RuntimeError("Existing tracing is active; leave it unchanged and stop.")
    started = perf_counter()
    rejected: dict[str, Any] = {}
    visited_ids: set[int] = set()
    retained_pieces = []

    def observe(frame: FrameType, event: str, _argument: Any) -> Any:
        """
        Restrict local tracing to the original certificate and snapshot its rejection.
        """
        if frame.f_code is not certify.__code__:
            return None
        local = frame.f_locals
        if perf_counter() - started > 10:
            raise RuntimeError("Certificate observation exceeded ten seconds.")
        piece = local.get("piece")
        if piece is not None and id(piece) not in visited_ids:
            visited_ids.add(id(piece))
            retained_pieces.append(piece)
            if len(visited_ids) > 4096:
                raise RuntimeError("Certificate observation exceeded4096intervals.")
        if event == "exception" and isinstance(_argument[1], (UnsafeRibbon, ValueError)):
            rejected.update(
                {
                    "depth": local.get("depth"),
                    "exception_type": type(_argument[1]).__name__,
                    "curvature_ratio_bound": local.get("ratio"),
                    "curvature_bound_ok": local.get("ratio", math.inf) <= 0.8,
                    "containment_ok": local.get("inside"),
                    "frame_regular": local.get("regular")
                    if isinstance(_argument[1], UnsafeRibbon)
                    else None,
                    "local_binormal_magnitude": magnitude(local["axis"])
                    if "axis" in local
                    else None,
                    "local_speed_lower_bound": local.get("speed"),
                    "occupied_hull_radius_mm": max(magnitude(difference(p, center)) for p in piece)
                    + reach,
                    "sphere_radius_mm": radius,
                    "interval_endpoints_mm": [asdict(piece[0]), asdict(piece[-1])],
                }
            )
        return observe

    result: dict[str, Any] = {}
    try:
        sys.settrace(observe)
        try:
            result["certificate"] = certify(points, reach, center, radius)
        except UnsafeRibbon as error:
            result["rejection"] = str(error)
        except ValueError as error:
            result["certificate_error"] = str(error)
    finally:
        sys.settrace(None)
    result["certificate_observation_seconds"] = perf_counter() - started
    result["visited_intervals"] = len(visited_ids)
    result["first_rejected_interval"] = rejected or None
    first, second = derivative(points), derivative(derivative(points))
    worst: dict[str, Any] = {"curvature_times_reach": 0.0}
    maximum_distance = 0.0
    minimum_speed = math.inf
    for index in range(257):
        if perf_counter() - started > 10:
            raise RuntimeError("Certificate diagnostic exceeded ten seconds.")
        u = index / 256
        position, velocity, acceleration = (
            evaluate(points, u),
            evaluate(first, u),
            evaluate(second, u),
        )
        speed = magnitude(velocity)
        if speed <= 1e-12:
            raise ValueError("Frozen curve has a zero-speed observation.")
        ratio = reach * magnitude(cross(velocity, acceleration)) / speed**3
        if ratio > worst["curvature_times_reach"]:
            worst = {
                "curvature_times_reach": ratio,
                "parameter": u,
                "radius_mm": reach / ratio,
                "position_mm": asdict(position),
            }
        maximum_distance = max(maximum_distance, magnitude(difference(position, center)) + reach)
        minimum_speed = min(minimum_speed, speed)
    result["sampled_worst_curvature"] = worst
    result["sampled_maximum_occupied_bound_mm"] = maximum_distance
    result["sampled_minimum_speed_mm"] = minimum_speed
    result["fixed_analytic_observations"] = 257
    return result


def run() -> dict[str, Any]:
    """
    Diagnose only the previously stopped degree-nine crossover and then stop.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Certificate diagnostic already started; no retry.")
    root = Path(__file__).parent
    sources = _sources()
    for name in ("endpoint_cap_acceleration.py", "certificate_diagnostic.py"):
        sources[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if (
        sources["endpoint_cap_acceleration.py"]
        != "60b1883341d6334864e6f695a79f0ffe21ad4764a3724d7e983e070cd10b9585"
    ):
        raise RuntimeError("Frozen degree-nine policy changed.")
    case = reference_cases()[1]
    budget = NativeBudget(maximum_seconds=10)
    _state = {
        "plan": {
            "case": asdict(case),
            "sources": sources,
            "seconds": 10,
            "rss_kib": 2097152,
            "certificate_calls": 1,
            "samples": 257,
            "native_attempts": 0,
            "search": 0,
            "retries": 0,
        },
        "stop_reason": None,
    }
    cpu = process_time()
    try:
        budget.check("frozen_certificate_diagnostic")
        points = cap_acceleration_controls(case)
        reach = math.hypot(
            case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
        )
        _state["result"] = probe_certificate(
            points, reach, lerp(case.start, case.end, 0.5), 2.5 * case.lines * case.diameter_mm
        )
        budget.check("complete")
    except (RuntimeError, ValueError) as error:
        _state["stop_reason"] = str(error)
    _state["overall_seconds"] = perf_counter() - budget.started
    _state["cpu_seconds"] = process_time() - cpu
    _state["maximum_sampled_rss_kib"] = max(
        (int(s["rss_kib"]) for s in budget.samples), default=None
    )
    return _state
