"""
Keep sampled admissibility separate from endpoint fitting and soft penalties.

This is a conservative experimental search domain,not an adopted physical law
or continuous/native certificate. It can exclude feasible endpoint solutions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, difference, magnitude

from .director_transport import DirectorPath
from .endpoint_first import EndpointCase


@dataclass(frozen=True)
class EdgeFeasibility:
    """
    Require existing33station search margins and129station both-edge macaroni.

    Search margins remain center.78,radius3.1D,sphere.97and minimumJ.1.
    Both-edge curvature times original profile reach must be<=.78. This is
    stronger than choosing the locally larger-Jedge;folded maps always reject.
    No repair,extra search,contact audit or tolerance adjustment occurs.
    """

    case: EndpointCase

    def minimum_length_ratio(self, normalized: DirectorPath) -> float:
        """
        Derive a sampled seed-length floor before endpoint projection shortens it.

        FREEtransport keeps normalized bend/ruling shapes independent of length.
        Both-edge curvature requires L>=half*abs(eta_u)+abs(bend_u)*reach/.78;
        J>=.1and radius>=3.1Dadd their own lower bounds. A fixed1%initialization
        margin does not alter acceptance. Containment still needs the actual filter.
        """
        length = normalized.field.length_mm
        half = normalized.field.half_width_mm
        reach = math.hypot(half, self.case.diameter_mm / 2)
        required = 0.0
        for i in range(129):
            k, _, eta_s = normalized.field.sample(i / 128)
            bend, ruling = abs(k) * length, half * abs(eta_s) * length
            required = max(
                required,
                ruling / 0.9,
                ruling + bend * max(reach / 0.78, 3.1 * self.case.diameter_mm),
            )
        return max(1.0, 1.01 * required / length)

    def __call__(self, path: DirectorPath) -> bool:
        """
        Reject before seed selection or accepting a proposed optimizer update.
        """
        return all(value >= 0 for value in self.slacks(path))

    def slacks(self, path: DirectorPath) -> tuple[float, ...]:
        """
        Expose unrectified inequalities for finite-difference constrained steps.

        Values>=0mean the same sampled search domain as the filter. Unlike clipped
        soft penalties,their derivatives remain visible inside the feasible region.
        No extra transport evaluations or continuous certificate are implied.
        """
        half = path.field.half_width_mm
        reach = math.hypot(half, self.case.diameter_mm / 2)
        required_radius = max(reach / 0.78, 3.1 * self.case.diameter_mm)
        result: list[float] = []
        for i in range(129):
            k, _, eta_s = path.field.sample(i / 128)
            minimum_j = 1 - half * abs(eta_s)
            result.extend((minimum_j - 0.1, minimum_j - abs(k) * required_radius))
        midpoint = self.case.start.translated(difference(self.case.end, self.case.start), 0.5)
        sphere = 2.5 * self.case.lines * self.case.diameter_mm * 0.97
        for i in range(33):
            state, _ = path.pose(i / 32)
            _, eta, _ = path.field.sample(i / 32)
            p, t, w = Vector3(*state[:3]), Vector3(*state[3:6]), Vector3(*state[6:9])
            extent = max(
                magnitude(difference(p.translated(w, q).translated(t, q * eta), midpoint))
                + self.case.diameter_mm / 2
                for q in (-half, half)
            )
            result.append(1 - extent / sphere)
        return tuple(result)
