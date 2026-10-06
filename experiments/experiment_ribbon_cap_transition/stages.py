"""
Measure immutable intermediate lanes without claiming native tangent prediction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.shape import RibbonEndFit, ribbon_line_lengths


@dataclass
class StageRecorder:
    """
    Record ordered lane metrics and finite cap chords, never continuous tangents.
    """

    fits: tuple[RibbonEndFit, RibbonEndFit]
    stages: dict[str, dict[str, object]] = field(default_factory=dict)

    def __call__(self, stage: str, lanes: tuple[tuple[Vector3, ...], ...]) -> None:
        """
        Preserve lengths and signed cap-chord angles for one stage only.

        Signed comparison points into the trunk at either end. A finite chord
        angle is resolution-dependent and does not prove a tangent violation.
        """
        if stage in self.stages:
            raise ValueError("A diagnostic stage was observed more than once.")
        if not lanes or any(len(lane) < 2 for lane in lanes):
            raise ValueError("Stage diagnostics need nonempty lanes with two samples.")
        if len({len(lane) for lane in lanes}) != 1:
            raise ValueError("Stage lane sample counts must agree.")
        lengths = ribbon_line_lengths(lanes)
        if min(lengths) <= 0:
            raise ValueError("Stage lanes must have positive lengths.")
        caps = []
        for index, adjacent, fit in ((0, 1, self.fits[0]), (-1, -2, self.fits[1])):
            if fit.approach_normal is None or len(fit.centers) != len(lanes):
                raise ValueError("Stage diagnostics require every cap center and normal.")
            inward = unit(fit.approach_normal)
            if index == -1:
                inward = Vector3(-inward.x, -inward.y, -inward.z)
            angles = []
            for lane in lanes:
                chord = difference(lane[adjacent], lane[index])
                if magnitude(chord) <= 1e-12:
                    raise ValueError("A cap chord has no usable direction.")
                angles.append(
                    math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(chord), inward)))))
                )
            caps.append(
                {
                    "end": "A" if index == 0 else "B",
                    "maximum_center_gap_mm": max(
                        magnitude(difference(lane[index], center))
                        for lane, center in zip(lanes, fit.centers)
                    ),
                    "inward_chord_angles_degrees": angles,
                    "first_chord_lengths_mm": [
                        magnitude(difference(lane[adjacent], lane[index])) for lane in lanes
                    ],
                    "scope": "Finite chords, not analytic lane tangents or native skin flow.",
                }
            )
        self.stages[stage] = {
            "lane_lengths_mm": lengths,
            "relative_length_spread": (max(lengths) - min(lengths)) / max(lengths),
            "caps": caps,
        }
