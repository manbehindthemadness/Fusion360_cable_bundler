"""
Retain actual moving-hardware evidence inside one original paired correction allocation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.separation import regions
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    FeatureEvidence,
    member_planes,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import (
    FeatureCoverage,
    FeaturePlane,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.moving_probe import moving_domain
from experiments.experiment_ribbon_terminal_hardware.terminal_protection import Protection

from .allocation import HardwareRow, MaterialRow
from .hardware_axes import reorient
from .ledger import Ledger
from .native_model import NativeJoints

Equation = Callable[[tuple[float, ...]], float]


@dataclass(frozen=True)
class Refresh:
    """
    Preserve all existing equations or stop without a partial capacity admission.
    """

    rows: tuple[Equation, ...]
    stop: str | None = None


class Discovery:
    """
    Share the owning sequence's gate, evidence catalogue and nonrenewable ledger.

    Negative discovery supplies guidance only. A new blocker retains its exact
    open pose even if capacity or subsequent correction fails. Final complete
    hardware and material certificates remain the owning sequence's obligation.
    """

    def __init__(
        self,
        terminal: Gate,
        features: dict[tuple[object, ...], FeatureEvidence],
        ledger: Ledger,
        record: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Bind original ownership without starting clocks, actions, roots or projections.
        """
        self.terminal, self.features, self.ledger, self.record = terminal, features, ledger, record
        self.latest: FeatureEvidence | None = None
        self.last_proof: tuple[FoldRoute, Report] | None = None
        self.model: NativeJoints | None = None
        self.screened: tuple[float, ...] | None = None

    def begin(self, model: NativeJoints, ledger: Ledger) -> None:
        """
        Retire previous local pose state while retaining the same shared evidence and charges.
        """
        if ledger is not self.ledger or model.original.targets != self.terminal.hardware.targets:
            raise ValueError("Moving discovery requires its original ledger and fixed targets")
        self.model, self.screened, self.latest = model, None, None
        self.last_proof = None

    def certify_stalled(self, route: FoldRoute) -> bool:
        """
        Resolve conservative guidance only with actual hardware proof on an unchanged closed proposal.

        This ends the correction stage: no further motion or new constraints
        may follow its request. Full self-contact remains the owning sequence's
        obligation. Preserve incomplete and blocked reports with their exact pose.
        """
        if (
            self.model is None
            or route.targets != self.model.original.targets
            or not ordered_mating_caps(route.pieces, route.targets)
        ):
            raise ValueError("Request actual proof only for this correction's closed proposal")
        report = self.terminal.certify(route, "paired_stalled_material")
        self.last_proof = route, report
        if report.status == "blocked" and report.witness is not None:
            self.latest = FeatureEvidence(route, report)
        return report.status == "clear"

    def _scan(
        self,
        model: NativeJoints,
        route: FoldRoute,
        values: tuple[float, ...],
        retained: tuple[Equation, ...],
    ) -> Refresh:
        """
        Probe each accepted moving pose once and add complete member rows before material rows.

        Capacity declines whole, and existing inequalities never disappear.
        The public scan may refresh a satisfied member axis after this measurement.
        No new correction or action follows merely from discovering evidence; the caller must spend its next original charged Newton slot.
        """
        if self.model is not model:
            raise ValueError("Bind this exact correction model before discovery")
        self.ledger.checkpoint()
        if self.screened == values:
            return Refresh(retained)
        self.screened = values
        planes = tuple(row.plane for row in retained if isinstance(row, (HardwareRow, Protection)))
        domain = moving_domain(
            route, model, values, self.terminal.hardware, planes, self.ledger.checkpoint
        )
        if domain is None:
            return Refresh(retained)
        report = self.terminal.probe(
            route, "paired_moving_material", domain=domain, checkpoint=self.ledger.checkpoint
        )
        self.ledger.checkpoint()
        if report.status != "blocked" or report.witness is None:
            return Refresh(retained)
        observed = FeatureEvidence(route, report)
        self.latest = observed
        key = (report.witness.terminal, regions(route)[report.witness.piece])
        if key in self.features:
            return Refresh(retained)
        if len(self.features) >= 3:
            return Refresh(retained, "hardware_feature_capacity")
        whole = FeaturePlane.create(
            model,
            route,
            report,
            self.terminal.hardware,
            values,
            coverage=FeatureCoverage.ADJOINING_INTERNAL,
        )
        if whole is None:
            return Refresh(retained, "hardware_guidance_unresolved")
        covered = {(part.box.terminal, member) for part in planes for member in part.members}
        additions = tuple(
            HardwareRow(part)
            for part in member_planes([whole], model, values)
            if (part.box.terminal, part.reference) not in covered
        )
        if len(retained) + len(additions) > 13:
            return Refresh(retained, "hardware_row_capacity")
        self.features[key] = observed
        rows = (
            *(row for row in retained if not isinstance(row, MaterialRow)),
            *additions,
            *(row for row in retained if isinstance(row, MaterialRow)),
        )
        self.record(
            {
                "stage": "paired_hardware_discovery",
                "status": "retained",
                "newton": self.ledger.newton_steps,
                "report": asdict(report),
                "added_rows": len(additions),
                "physical_rows": len(rows),
                "hardware_features": len(self.features),
            }
        )
        return Refresh(rows)

    def scan(
        self,
        model: NativeJoints,
        route: FoldRoute,
        values: tuple[float, ...],
        retained: tuple[Equation, ...],
    ) -> Refresh:
        """
        Retain negative discovery and refresh satisfied member axes once per accepted pose.

        Keep all member, gap and row identities; select an axis only between
        Newton steps, never during their derivatives or nonlinear trials.
        Actual whole-route hardware and material certificates remain mandatory.
        A discovery capacity decline returns unchanged without axis selection.
        """
        already_screened = self.screened == values
        result = self._scan(model, route, values, retained)
        if result.stop is not None or already_screened:
            return result
        refreshed: list[Equation] = []
        for row in result.rows:
            self.ledger.checkpoint()
            replacement = (
                reorient(row, values, self.ledger.checkpoint)
                if isinstance(row, HardwareRow)
                else row
            )
            refreshed.append(replacement)
            if replacement is not row:
                assert isinstance(row, HardwareRow) and isinstance(replacement, HardwareRow)
                self.record(
                    {
                        "stage": "paired_hardware_axis",
                        "status": "refreshed",
                        "newton": self.ledger.newton_steps,
                        "terminal": row.plane.box.terminal.value,
                        "member": asdict(row.plane.reference),
                        "from_family": row.plane.family,
                        "from_side": row.plane.side.value,
                        "to_family": replacement.plane.family,
                        "to_side": replacement.plane.side.value,
                        "old_gap_mm": row.plane.gap(values) * model.scale,
                        "new_gap_mm": replacement.plane.gap(values) * model.scale,
                    }
                )
        if all(new is old for new, old in zip(refreshed, result.rows)):
            return result
        return Refresh(tuple(refreshed))
