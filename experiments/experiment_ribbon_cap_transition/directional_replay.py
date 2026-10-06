"""
Compare circular and directional bending proxies on frozen, already-banked data.

This replay neither solves nor changes a ribbon. Finite tangent differences are
not analytic curvature or a continuous macaroni certificate. Existing complete
case failures remain authoritative; no native prediction or acceptance is added.
"""

from __future__ import annotations

import hashlib
import json
import math
import resource
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame

SOURCE = (
    PROJECT_ROOT
    / "artifacts/verification/ribbon_cap_transition/authored_sections"
    / "e43b41466f8242db9a715a8718bfd666/report.json"
)


def bending_ratios(
    curvature: Vector3, frame: RibbonFrame, half_width_mm: float, half_thickness_mm: float
) -> tuple[float, float, float]:
    """
    Return circular, oriented rectangular and unconstrained ideal-bank proxies.

    The rectangular support bounds the full enclosing rectangle, not an ellipse.
    Ideal-bank support is only a pointwise lower bound: it ignores endpoint roll,
    twist-rate limits and continuity, and is not an achievable route claim.
    """
    if any(not math.isfinite(v) or v <= 0 for v in (half_width_mm, half_thickness_mm)):
        raise ValueError("Directional envelope dimensions must be positive and finite.")
    if not all(math.isfinite(v) for v in (curvature.x, curvature.y, curvature.z)):
        raise ValueError("Curvature components must be finite.")
    k = magnitude(curvature)
    circular = math.hypot(half_width_mm, half_thickness_mm) * k
    directional = half_width_mm * abs(dot(curvature, frame.width)) + half_thickness_mm * abs(
        dot(curvature, frame.thickness)
    )
    return circular, directional, min(half_width_mm, half_thickness_mm) * k


def measure_frames(
    frames: tuple[RibbonFrame, ...], half_width_mm: float, half_thickness_mm: float
) -> dict[str, object]:
    """
    Measure both proxies on identical finite nodes and record bank-rate estimates.

    Curvature proxy is projected finite dT/d(chord distance). Bank increments use
    projected previous width in the next node plane, removing approximate frame
    transport. Neither quantity bounds between-node extrema or conductor strain.
    """
    if len(frames) < 3:
        raise ValueError("Directional replay requires three section nodes.")
    distances = [0.0]
    for left, right in zip(frames, frames[1:]):
        span = magnitude(difference(right.origin, left.origin))
        if span <= 1e-8:
            raise ValueError("Directional replay requires positive node spans.")
        distances.append(distances[-1] + span)
    ratios = []
    for index, frame in enumerate(frames):
        left, right = max(0, index - 1), min(len(frames) - 1, index + 1)
        delta = difference(frames[right].tangent, frames[left].tangent)
        normal_delta = delta.translated(frame.tangent, -dot(delta, frame.tangent))
        span = distances[right] - distances[left]
        curvature = Vector3(normal_delta.x / span, normal_delta.y / span, normal_delta.z / span)
        ratios.append(bending_ratios(curvature, frame, half_width_mm, half_thickness_mm))
    bank_rates = []
    for index, (left, right) in enumerate(zip(frames, frames[1:])):
        transported = left.width.translated(right.tangent, -dot(left.width, right.tangent))
        if magnitude(transported) <= 1e-8:
            raise ValueError("Width transport is degenerate; no fallback.")
        transported = unit(transported)
        angle = math.atan2(
            dot(cross(transported, right.width), right.tangent),
            dot(transported, right.width),
        )
        bank_rates.append(abs(angle) / (distances[index + 1] - distances[index]))
    circular = max(row[0] for row in ratios)
    directional = max(row[1] for row in ratios)
    return {
        "stations": len(frames),
        "maximum_circular_proxy": circular,
        "maximum_directional_proxy": directional,
        "maximum_pointwise_ideal_bank_lower_bound": max(row[2] for row in ratios),
        "worst_proxy_reduction_fraction": 1 - directional / circular if circular > 1e-12 else None,
        "circular_proxy_exceeds_0_8": circular > 0.8,
        "directional_proxy_exceeds_0_8": directional > 0.8,
        "maximum_projected_bank_rate_radians_per_mm": max(bank_rates),
        "station_ratios": ratios,
        "scope": "Finite frame proxies only. Not continuous certification, a twist limit, conductor curvature, native acceptance or a new bank solution.",
    }


def _vector(value: object) -> Vector3:
    """
    Parse finite coordinates without accepting missing, boolean or null components.
    """
    if not isinstance(value, dict):
        raise ValueError("Replay vectors must be coordinate objects.")
    components = tuple(value.get(name) for name in ("x", "y", "z"))
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in components
    ):
        raise ValueError("Replay vectors must have finite numeric x/y/z coordinates.")
    return Vector3(*components)


def _frames(value: object) -> tuple[RibbonFrame, ...]:
    """
    Validate the archived orthonormal section scaffold before evaluating proxies.
    """
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("Replay scaffold must contain three section frames.")
    frames = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Replay frame must be an object.")
        frame = RibbonFrame(
            *(_vector(item.get(name)) for name in ("origin", "tangent", "width", "thickness"))
        )
        axes = (frame.tangent, frame.width, frame.thickness)
        if any(abs(magnitude(axis) - 1) > 1e-7 for axis in axes) or any(
            abs(dot(a, b)) > 1e-7
            for a, b in ((axes[0], axes[1]), (axes[0], axes[2]), (axes[1], axes[2]))
        ):
            raise ValueError("Archived section axes must be orthonormal.")
        frames.append(frame)
    return tuple(frames)


def run() -> Path:
    """
    Replay at most eleven frozen cases with zero solves, refinements or native work.

    Stop scheduling at 60 seconds, 512 MiB macOS peak RSS, source drift or malformed
    data. No original report is edited, and absent invalid-control samples remain
    unmeasured rather than being manufactured after a conservative rejection.
    """
    started = perf_counter()
    raw = SOURCE.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    source = json.loads(raw)
    if not isinstance(source, dict) or not isinstance(source.get("cases"), list):
        raise ValueError("Replay source must contain a case list.")
    original_plan = source.get("plan")
    if not isinstance(original_plan, dict):
        raise ValueError("Replay source must retain its frozen plan.")
    inputs = original_plan.get("cases_and_targets")
    rows = source["cases"]
    if not isinstance(inputs, list) or len(rows) != 11 or len(inputs) != 11:
        raise ValueError("Replay requires exactly eleven frozen case records.")
    for row, registered in zip(rows, inputs):
        if not isinstance(row, dict) or not isinstance(registered, dict):
            raise ValueError("Replay case records must be objects.")
        baseline, case = row.get("baseline"), registered.get("case")
        if not isinstance(baseline, dict) or not isinstance(case, dict):
            raise ValueError("Replay cases must retain baseline results and fixed inputs.")
        if not isinstance(row.get("case_id"), str) or not isinstance(baseline.get("status"), str):
            raise ValueError("Replay case identity and baseline status must be strings.")
        shape = baseline.get("source_shape")
        if shape is not None and not isinstance(shape, dict):
            raise ValueError("Replay shape must be an object when present.")
        count, diameter = case.get("lines"), case.get("diameter_mm")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("Replay conductor count must be a positive integer.")
        if isinstance(diameter, bool) or not isinstance(diameter, (float, int)):
            raise ValueError("Replay diameter must be numeric.")
        if not math.isfinite(diameter) or diameter <= 0:
            raise ValueError("Replay diameter must be positive and finite.")
    directory = (
        PROJECT_ROOT
        / "artifacts/verification/ribbon_cap_transition/directional_replay"
        / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    production = verify_sources()
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    rule_hashes = {
        name: hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest()
        for name in ("experiment_testing_rules.txt", "rollback_end_loft_notes.txt")
    }
    plan = {
        "question": "Does oriented x/y support provide smaller bending proxies than the current enclosing-radius rule on the existing banked routes?",
        "source": str(SOURCE.relative_to(PROJECT_ROOT)),
        "source_sha256": source_hash,
        "code_sha256": code_hash,
        "current_rule_sha256": rule_hashes,
        "frozen_original_plan": source["plan"],
        "production": production,
        "limits": {
            "cases": 11,
            "solves": 0,
            "native_attempts": 0,
            "refinements": 0,
            "seconds": 60,
            "host_peak_rss_bytes": 512 * 1024 * 1024,
        },
        "method": "Same saved banked frames; finite projected tangent differences; rectangular support a|k_width|+b|k_thickness| compared with hypot(a,b)|k|. a=(lines+0.2)*diameter/2; b=diameter/2, matching existing lobe envelope dimensions. No changed rules or bank search.",
        "classification": "Cached development replay, not a solve benchmark or geometry validation. Exact cap and reverse-loft targets unchanged because geometry is untouched.",
        "unknowns": "Continuous curvature/clearance, twist feasibility, actual bank solution benefit, native construction, post-build compliance, total solver speed benefit and token cost.",
        "native_prediction": "unknown",
    }
    (directory / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    results: list[dict[str, object]] = []
    stop = None
    analysis_seconds = 0.0
    for row, registered in zip(rows, inputs):
        result: dict[str, object] = {
            "case_id": row["case_id"],
            "status": "not_attempted",
            "baseline_status": row["baseline"]["status"],
            "baseline_failures": row["baseline"].get("failures", []),
            "native": "not_attempted",
            "audit": "absent",
        }
        results.append(result)
        if stop is None and (
            perf_counter() - started >= 60
            or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >= 512 * 1024 * 1024
        ):
            stop = "Time or memory scheduling ceiling reached."
        if stop is not None:
            result["reason"] = stop
            continue
        if (
            hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_hash
            or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != code_hash
            or verify_sources() != production
            or any(
                hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() != checksum
                for name, checksum in rule_hashes.items()
            )
        ):
            stop = "Source/code/rule/production fingerprint drift."
            result["reason"] = stop
            continue
        if row["case_id"] != registered["case"]["name"]:
            stop = "Frozen case identity/order mismatch."
            result["reason"] = stop
            continue
        shape = row["baseline"].get("source_shape")
        if shape is None:
            result.update(
                status="unmeasured", reason=row["baseline"].get("reason", "No saved frames.")
            )
            continue
        measured = perf_counter()
        try:
            case = registered["case"]
            diameter = float(case["diameter_mm"])
            result.update(
                measure_frames(
                    _frames(shape.get("frames")), (case["lines"] + 0.2) * diameter / 2, diameter / 2
                )
            )
            result["status"] = "proxy_measured"
        except (TypeError, ValueError, KeyError) as error:
            result.update(status="harness_error", reason=str(error))
            stop = "Malformed replay data; no retry."
        analysis_seconds += perf_counter() - measured
    unchanged = hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    production_after = verify_sources()
    code_unchanged = hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == code_hash
    if not unchanged or not code_unchanged or production_after != production:
        stop = "Source/code/production fingerprint drift."
    report = {
        "plan": plan,
        "cases": results,
        "planned": 11,
        "proxy_evaluated": sum(row["status"] == "proxy_measured" for row in results),
        "solve_calls": 0,
        "native_attempts": 0,
        "built": 0,
        "fully_audited": 0,
        "native_failure_rate": "unmeasured",
        "analysis_seconds": analysis_seconds,
        "elapsed_seconds": perf_counter() - started,
        "host_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_unchanged": unchanged,
        "code_unchanged": code_unchanged,
        "production_unchanged": production_after == production,
        "stop_reason": stop
        or "Bounded cached replay complete; no geometry or rule changes authorized.",
    }
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return directory


if __name__ == "__main__":
    print(run())
