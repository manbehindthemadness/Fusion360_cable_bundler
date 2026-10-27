"""
Dispatch exact neutral boundary runs before the unchanged broad routing experiment.

This is a reusable experimental entry,not production routing. A handoff still
requires independent intrinsic/cubic analysis before native construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Literal

from cable_bundler.routing.geometry import cross, difference, dot, magnitude
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_shooting import endpoint_metrics
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import broad_chart, broad_search
from .active_clearance import sample
from .broad_search import SearchLedger


@dataclass(frozen=True)
class Handoff:
    """
    Retain a measured pose/contact-clear path and the mechanism that produced it.
    """

    path: CompatiblePath
    metrics: dict[str, Any]
    contact: dict[str, Any]
    method: Literal["neutral", "broad"]


def neutral_boundary(case: EndpointCase) -> bool:
    """
    Recognize forward collinear runs without erasing roll or reversing conductor order.

    Frame equality is exact;relative cross-product allowance covers floating
    subtraction of translated endpoints. Actual strict closure is checked later.
    """
    Targets.capture(case)
    displacement = difference(case.end, case.start)
    length = magnitude(displacement)
    return (
        length > 0
        and case.start_tangent == case.end_tangent
        and case.start_width == case.end_width
        and dot(displacement, case.start_tangent) > 0
        and magnitude(cross(displacement, case.start_tangent)) <= 1e-12 * length
    )


def solve(
    case: EndpointCase, checkpoint: Callable[[], None], ledger: SearchLedger
) -> Handoff | None:
    """
    Avoid numerical search only when the neutral chart satisfies strict fixed poses.

    Preserve resource exceptions and one-use ledger semantics. Bent,rolled,reverse
    and sideways targets receive the unchanged broad policy;no fixture lookup or
    fitted coordinate cache participates. Physical/native acceptance stays external.
    """
    if ledger.started is not None:
        raise ValueError("Search ledgers are one-use;preserve prior outcomes.")
    started = perf_counter()
    checkpoint()
    if neutral_boundary(case):
        ledger.started = started
        ledger.stage = "neutral transport"
        try:
            coordinates = (0.0,) * 9 + (1.0,)
            path = broad_chart.integrate(case, coordinates, 512, checkpoint)
            metrics: dict[str, Any] = endpoint_metrics(case, path)
            strict = max(metrics.values()) <= 1e-8
            metrics.update(strict_endpoint_gate=strict, coordinates=coordinates, evaluations=1)
            contact = sample(case, path, checkpoint).contacts
            if not strict or contact["contact_detected"] or not contact["strict_frame_gate"]:
                raise RuntimeError("Neutral boundary transport failed its measured gates.")
            checkpoint()
            ledger.stage = "neutral awaiting independent analysis"
            return Handoff(path, metrics, contact, "neutral")
        finally:
            ledger.seconds = perf_counter() - started
    broad_search.solve(case, checkpoint, ledger)
    candidate = ledger.candidate
    if candidate is None:
        return None
    return Handoff(candidate.path, candidate.metrics, candidate.contact, "broad")
