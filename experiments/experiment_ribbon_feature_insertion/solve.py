"""
Construct fixed-radius guide-feature chains with bounded exact-root and contact work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_spline_guide.guide import agreement

from .allocation import Allocation, fit
from .contact_measurement import ContactPolicy
from .features import chains
from .guide_frames import Frames
from .repair import changed, correction, nearest, reframed
from .selection import Branch, Policy, select


@dataclass(frozen=True)
class Result:
    """
    Separate guide/reference construction, contact acceptance and explicit unattempted roots.
    """

    route: FoldRoute | None
    allocation: Allocation | None
    status: str
    contacts: int
    contact_seconds: float
    closed_branches: int
    unattempted_contacts: int
    contact: ContactResult | None = None


def construct(
    boundary: Boundary,
    frames: Frames,
    parameters: tuple[float, ...],
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    selection_policy: Policy = Policy.MONOTONIC,
    contact_policy: ContactPolicy = ContactPolicy.STRICT,
) -> Result:
    """
    Fit one fixed frame sequence and certify at most two algebraic branches.

    This never samples additional guide stations, guessed angles or radii. The
    matched baseline and inserted variant each have the same two-contact budget.
    Contact is strict by default. The temporary gym policy may retain pair-budget
    exhaustion as an explicitly incomplete measurement; actual penetration and
    other unresolved outcomes reject. Resource/source errors always propagate.
    Initially unclosed branches receive at most two residual-derived angular
    corrections with two finite step halvings. Radius and station choices stay fixed.
    Original midpoint-ranked feasibility is preserved. If its first branch is
    separated, use the spare contact certificate only for a shorter branch whose
    ordered whole-guide RMS and direction loss are both non-increasing.
    """
    candidates: list[Allocation] = []
    branches: list[Branch] = []
    for chain in chains(boundary, frames, parameters, checkpoint, record):
        allocation = fit(boundary, chain, threshold_mm, checkpoint, record)
        if allocation is None:
            current = chain
            closure = nearest(Model(boundary, current.topology), checkpoint)
            for iteration in range(2):
                delta = correction(boundary, current, closure, checkpoint)
                if delta is None:
                    record(
                        {
                            "stage": "feature_reclosure",
                            "roots": chain.roots,
                            "iteration": iteration,
                            "status": "derivative_unresolved",
                            "position_error_diameters": closure.error,
                        }
                    )
                    break
                progressed = False
                for halving in range(2):
                    checkpoint()
                    probe = reframed(
                        boundary, current, changed(current.targets, delta, 0.5**halving)
                    )
                    if probe is None:
                        record(
                            {
                                "stage": "feature_reclosure",
                                "roots": chain.roots,
                                "iteration": iteration,
                                "halving": halving,
                                "status": "branch_unresolved",
                            }
                        )
                        continue
                    trial = nearest(Model(boundary, probe.topology), checkpoint)
                    record(
                        {
                            "stage": "feature_reclosure",
                            "roots": chain.roots,
                            "iteration": iteration,
                            "halving": halving,
                            "status": "residual_reduced"
                            if trial.error < closure.error - 1e-10
                            else "no_gain",
                            "position_error_diameters": trial.error,
                            "angular_delta": delta,
                        }
                    )
                    if trial.error < closure.error - 1e-10:
                        current, closure, progressed = probe, trial, True
                        if trial.error <= 1e-7 / boundary.targets.diameter_mm:
                            allocation = fit(boundary, current, threshold_mm, checkpoint, record)
                        break
                if allocation is not None or not progressed:
                    break
        if allocation is not None:
            score = agreement(allocation.route, frames.guide)
            record(
                {
                    "stage": "feature_branch",
                    "status": "closed",
                    "roots": chain.roots,
                    "features": chain.feature_count,
                    "primitives": len(chain.topology.folds),
                    "site_error_mm2": allocation.score,
                    "guide": asdict(score),
                    "route": snapshot(allocation.route),
                }
            )
            candidates.append(allocation)
            branches.append(Branch(chain.roots, allocation.route, score, allocation.score))
    allocations = {a.chain.roots: a for a in candidates}
    contacts = 0
    contact_seconds = 0.0
    measurements: dict[tuple[int, ...], ContactResult] = {}

    def measure(branch: Branch) -> bool:
        """
        Retain the raw contact measurement before applying the explicit geometry policy.
        """
        nonlocal contacts, contact_seconds
        checked = allocations[branch.roots]
        checkpoint()
        record({"stage": "feature_contact", "status": "started", "roots": checked.chain.roots})
        started = perf_counter()
        result = inspect_contact(checked.route, maximum_pairs=1024, checkpoint=checkpoint)
        contact_seconds += perf_counter() - started
        contacts += 1
        measurements[branch.roots] = result
        record(
            {
                "stage": "feature_contact",
                "status": result.status,
                "roots": checked.chain.roots,
                "contact": asdict(result),
                "route": snapshot(checked.route),
            }
        )
        return contact_policy.permits_geometry(result)

    selected = select(branches, measure, selection_policy)
    if selected is not None:
        allocation = allocations[selected.roots]
        measurement = measurements[selected.roots]
        return Result(
            allocation.route,
            allocation,
            "separated" if measurement.status == "separated" else "contact_measurement_incomplete",
            contacts,
            contact_seconds,
            len(candidates),
            len(candidates) - contacts,
            measurement,
        )
    return Result(
        None,
        None,
        "no_separated_chain" if candidates else "no_fixed_radius_closure",
        contacts,
        contact_seconds,
        len(candidates),
        max(0, len(candidates) - contacts),
    )
