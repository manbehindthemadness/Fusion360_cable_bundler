"""
Choose a continuous, aperture-aware bank for a discrete ribbon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .aperture import contains_disk
from .geometry import Vector3, cross, difference, dot, magnitude, unit
from .parallel import GateFrame
from .ribbon import RibbonFrame

_ANGLE_STEP = math.pi / 18.0
_FULL_TURN_STEPS = 36


@dataclass(frozen=True)
class RibbonBankGate:
    """
    Constrain one sampled section by a physical pathway aperture.
    """

    sample_index: int
    frame: GateFrame


def _rotated(frame: RibbonFrame, angle: float) -> RibbonFrame:
    """
    Rotate the signed width around its tangent without changing lane identity.
    """
    cosine, sine = math.cos(angle), math.sin(angle)
    width = unit(
        Vector3(
            frame.width.x * cosine + frame.thickness.x * sine,
            frame.width.y * cosine + frame.thickness.y * sine,
            frame.width.z * cosine + frame.thickness.z * sine,
        )
    )
    return RibbonFrame(frame.origin, frame.tangent, width, unit(cross(frame.tangent, width)))


def _fits_gate(section: RibbonFrame, gate: GateFrame, line_count: int, diameter_mm: float) -> bool:
    """
    Check every conductor disk in a gate plane, including profile holes.
    """
    half = (line_count - 1) / 2.0
    for index in range(line_count):
        center = section.origin.translated(section.width, (index - half) * diameter_mm)
        offset = difference(center, gate.origin)
        u, v = dot(offset, gate.u_direction), dot(offset, gate.v_direction)
        if gate.usable_radius_mm is not None:
            if math.hypot(u, v) + diameter_mm / 2.0 > gate.usable_radius_mm + 1e-6:
                return False
        elif not contains_disk((u, v), diameter_mm / 2.0, gate.boundary_loops_mm):
            return False
    return True


def bank_ribbon_frames(
    frames: tuple[RibbonFrame, ...],
    line_count: int,
    diameter_mm: float,
    gates: tuple[RibbonBankGate, ...] = (),
) -> tuple[RibbonFrame, ...]:
    """
    Minimize width-axis bending with a bounded continuous bank.

    The signed end frames are fixed. The angle lattice also admits an unwrapped
    full turn in either direction; conductor indices are never permuted. If an
    aperture or twist-rate constraint makes every candidate infeasible, the
    original frames are retained and the normal bend/fit warnings remain honest.
    """
    if len(frames) < 3 or line_count < 1 or not math.isfinite(diameter_mm) or diameter_mm <= 0:
        raise ValueError("Banking needs three frames and positive ribbon dimensions.")
    width_mm = line_count * diameter_mm
    by_index: dict[int, list[GateFrame]] = {}
    for gate in gates:
        if not 0 <= gate.sample_index < len(frames):
            raise ValueError("A ribbon gate sample is outside the route.")
        by_index.setdefault(gate.sample_index, []).append(gate.frame)
    turns = [
        difference(frames[min(i + 1, len(frames) - 1)].tangent, frames[max(i - 1, 0)].tangent)
        for i in range(len(frames))
    ]
    sections: list[dict[int, RibbonFrame]] = []
    for index, frame in enumerate(frames):
        candidates = range(-_FULL_TURN_STEPS, _FULL_TURN_STEPS + 1)
        if index == 0:
            candidates = (0,)
        elif index == len(frames) - 1:
            candidates = (-_FULL_TURN_STEPS, 0, _FULL_TURN_STEPS)
        sections.append(
            {
                step: section
                for step in candidates
                for section in (
                    frame if step % _FULL_TURN_STEPS == 0 else _rotated(frame, step * _ANGLE_STEP),
                )
                if all(
                    _fits_gate(section, gate, line_count, diameter_mm)
                    for gate in by_index.get(index, ())
                )
            }
        )
    if not sections[0]:
        return frames
    scores = {0: 0.0}
    parents: list[dict[int, int]] = [{}]
    for index in range(1, len(frames)):
        span_mm = magnitude(difference(frames[index].origin, frames[index - 1].origin))
        max_angle = min(math.pi / 6.0, max(_ANGLE_STEP, 2.0 * math.pi * span_mm / (3.0 * width_mm)))
        max_steps = max(1, math.ceil(max_angle / _ANGLE_STEP - 1e-9))
        next_scores: dict[int, float] = {}
        next_parents: dict[int, int] = {}
        for step, section in sections[index].items():
            hard = dot(turns[index], section.width)
            bend_cost = width_mm * width_mm * hard * hard
            neutral_cost = 0.002 * (step * _ANGLE_STEP) ** 2
            for previous, cost in scores.items():
                delta = step - previous
                if abs(delta) > max_steps:
                    continue
                twist_cost = 0.002 * width_mm * width_mm * (delta * _ANGLE_STEP) ** 2
                candidate = cost + bend_cost + neutral_cost + twist_cost
                if candidate < next_scores.get(step, math.inf):
                    next_scores[step] = candidate
                    next_parents[step] = previous
        if not next_scores:
            return frames
        scores = next_scores
        parents.append(next_parents)
    end_step = min(scores, key=lambda step: (scores[step], abs(step), step))
    selected = [end_step]
    for index in range(len(frames) - 1, 0, -1):
        selected.append(parents[index][selected[-1]])
    selected.reverse()
    return tuple(sections[index][step] for index, step in enumerate(selected))
