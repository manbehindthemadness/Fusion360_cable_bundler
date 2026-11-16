"""
Execute one frozen trunk-and-ending input without changing candidate policies.

The caller supplies the selected trunk constructor and its original allocation.
Branch construction uses that same checkpoint; this module grants no recovery
reserve or physical acceptance. Missing input rejects before starting the trunk.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter, process_time
from typing import Any, Protocol
from uuid import UUID

from cable_bundler.domain import HarnessDefinition
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_locked_solver.solver import Result

from .branch_construction import BranchRoot, construct
from .branch_plan import SpatialBranchPlan
from .branch_targets import BranchTargets, capture_targets
from .contracts import CapPort, CompleteRibbonInput, IncompleteRibbonInput


class TrunkConstructor(Protocol):
    """
    Invoke one explicitly selected trunk algorithm under the caller's existing guard.
    """

    def __call__(
        self,
        targets: Targets,
        checkpoint: Callable[[], None],
        record: Callable[[dict[str, Any]], None],
        /,
    ) -> Result:
        """
        Return the original trunk result, including unresolved outcomes without fallback.
        """
        ...


@dataclass(frozen=True)
class RibbonTargets:
    """
    Freeze every terminal, ordered control and explicit material root before solving.

    Roots describe the supplied material cap frames. Their native correspondence
    remains a caller qualification; input completeness does not certify junctions.
    """

    definition: HarnessDefinition
    group_id: UUID
    trunk: Targets
    caps: tuple[CapPort, ...]
    branches: tuple[BranchTargets, ...]
    roots: tuple[BranchRoot, ...]


@dataclass(frozen=True)
class RibbonPlan:
    """
    Retain original complete input and all prepared geometry without a success flag.

    An unresolved trunk leaves every branch unattempted. A returned branch tuple
    covers all captured branches, but their outstanding physical gates remain.
    Timings include capture, constructor checks and branch preparation separately;
    neither native construction nor later development audits are included.
    """

    source: RibbonTargets
    captured: CompleteRibbonInput
    trunk: Result
    branches: tuple[SpatialBranchPlan, ...]
    wall_seconds: float
    cpu_seconds: float

    @property
    def unattempted_route_ids(self) -> tuple[UUID, ...]:
        """
        Report missing branch geometry explicitly rather than treating an empty prefix as complete.
        """
        prepared = {branch.source.source.leg.route_id for branch in self.branches}
        return tuple(
            branch.source.leg.route_id
            for branch in self.captured.branches
            if branch.source.leg.route_id not in prepared
        )


def prepare(
    source: RibbonTargets,
    trunk_constructor: TrunkConstructor,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> RibbonPlan:
    """
    Capture once, construct one trunk, and prepare every branch in original order.

    No alternate trunk, branch initializer, repair or internal budget is selected.
    Checkpoint/constructor/branch errors propagate; completed prefix events remain
    with the caller's recorder. A foreign-target trunk is a provenance error.
    This entry does not certify material, curvature, contact or native junctions.
    """
    started, cpu_started = perf_counter(), process_time()
    checkpoint()
    captured = capture_targets(
        source.definition, source.group_id, source.trunk, source.caps, source.branches, checkpoint
    )
    roots = {root.route_id: root for root in source.roots}
    if len(roots) != len(source.roots) or set(roots) != {
        branch.source.leg.route_id for branch in captured.branches
    }:
        raise IncompleteRibbonInput(
            "Every complete branch needs exactly one explicit material root"
        )
    for branch in captured.branches:
        if roots[branch.source.leg.route_id].profile.pin_number != branch.conductor.pin_number:
            raise IncompleteRibbonInput("A branch root cannot change its conductor identity")
    record({"stage": "complete_capture", "branches": len(captured.branches)})
    checkpoint()
    trunk = trunk_constructor(captured.trunk, checkpoint, record)
    checkpoint()
    record({"stage": "complete_trunk", "status": trunk.detail.get("status", "unreported")})
    branches = []
    if trunk.route is not None:
        if trunk.route.targets != captured.trunk:
            raise IncompleteRibbonInput(
                "Constructed trunk differs from the frozen complete targets"
            )
        for branch in construct(captured, source.roots, checkpoint):
            branches.append(branch)
            record(
                {
                    "stage": "complete_branch",
                    "route_id": str(branch.source.source.leg.route_id),
                    "outstanding": branch.outstanding,
                }
            )
    checkpoint()
    return RibbonPlan(
        source,
        captured,
        trunk,
        tuple(branches),
        perf_counter() - started,
        process_time() - cpu_started,
    )
