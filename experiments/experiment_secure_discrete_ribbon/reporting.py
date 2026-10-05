"""
Keep deterministic matrix provenance and compare repeated outcome classifications.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict

from cable_bundler.routing.geometry import dot

from .cases import RibbonStressCase
from .frames import RibbonFrame


def maximum_frame_step(frames: tuple[RibbonFrame, ...]) -> float:
    """
    Measure complete neighboring bend-plus-bank rotations in degrees.

    This is diagnostic evidence, not an empirical threshold promoted to a rule.
    """
    angles = []
    for a, b in zip(frames, frames[1:]):
        trace = dot(a.tangent, b.tangent) + dot(a.width, b.width) + dot(a.thickness, b.thickness)
        angles.append(math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1) / 2)))))
    return max(angles, default=0.0)


def matrix_fingerprint(cases: tuple[RibbonStressCase, ...]) -> str:
    """
    Hash exact inputs and declared expectations independently of Fusion output.
    """
    serialized = json.dumps([asdict(case) for case in cases], sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def summarize(rows: list[dict[str, object]]) -> dict[str, int]:
    """
    Count each outcome without merging expected rejections into successful builds.
    """
    return dict(Counter(str(row["status"]) for row in rows))


def compare_outcomes(
    previous: list[dict[str, object]], current: list[dict[str, object]]
) -> list[str]:
    """
    Detect missing cases or changed status/stage on an identical input matrix.

    Timing and transient Fusion identity are excluded. A stable failure remains
    a failure: repeatability must never be reported as geometric correctness.
    """
    before = {str(row["name"]): (row["status"], row.get("stage")) for row in previous}
    after = {str(row["name"]): (row["status"], row.get("stage")) for row in current}
    return sorted(
        name for name in before.keys() | after.keys() if before.get(name) != after.get(name)
    )
