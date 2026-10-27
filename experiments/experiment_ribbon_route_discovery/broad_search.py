"""
Provide67's deterministic broad routing policy without global experiment state.

The returned handoff passes sampled pose/contact gates only. A caller must run
independent intrinsic/cubic checks before construction and preserve that evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter
from typing import Any, Callable, Literal

from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import box_fit, broad_chart, projected_clearance
from .active_clearance import sample
from .families import Seed, select

Phase = Literal["short", "deep", "width"]


class RecoveryPolicy(Enum):
    """
    Bound optional exploration after every historical search stage has exhausted.
    """

    NONE = 0
    FOUR_UNUSED_STARTS = 4


@dataclass(frozen=True)
class Trial:
    """
    Retain one complete fit,its actual path and all sampled acceptance measurements.
    """

    seed: Seed
    phase: Phase
    path: CompatiblePath
    metrics: dict[str, Any]
    contact: dict[str, Any]
    rank: float
    ready_for_analysis: bool


@dataclass
class SearchLedger:
    """
    Let the caller retain completed trials and current stage after an interruption.

    One ledger is valid for one invocation only. Exceptions propagate rather than
    converting source/resource/API errors into geometry rejection or silent retry.
    """

    started: float | None = None
    stage: str = "not started"
    seed_bank: tuple[Seed, ...] = ()
    selected_short: tuple[int, ...] = ()
    selected_deep: list[int] = field(default_factory=list)
    trials: list[Trial] = field(default_factory=list)
    chosen: int | None = None
    seconds: float | None = None

    @property
    def candidate(self) -> Trial | None:
        """
        Return the handoff only after a completed search selected a measured trial.
        """
        if self.chosen is None or self.stage != "awaiting independent analysis":
            return None
        return self.trials[self.chosen]


def _observe(
    case: EndpointCase,
    seed: Seed,
    path: CompatiblePath,
    metrics: dict[str, Any],
    phase: Phase,
    checkpoint: Callable[[], None],
) -> Trial:
    """
    Measure current occupied width without reusing a previous path's witnesses.
    """
    snapshot = sample(case, path, checkpoint)
    contact = snapshot.contacts
    ready = (
        not contact["contact_detected"]
        and contact["position_connected"]
        and contact["strict_frame_gate"]
    )
    rank = metrics["score"] + sum(value * value for value in snapshot.deficits)
    return Trial(seed, phase, path, metrics, contact, rank, ready)


def solve(
    case: EndpointCase,
    checkpoint: Callable[[], None],
    ledger: SearchLedger,
    *,
    recovery: RecoveryPolicy = RecoveryPolicy.NONE,
) -> SearchLedger:
    """
    Run110cold screens,up to16short/4deep fits,then queued closed-route width repair.

    No case identifier affects search. At most18208historical fit transports are possible,
    subordinate to the caller's elapsed/RSS checkpoint. Preserve every completed
    failed trial;return an exhausted ledger when no pose/contact handoff exists.
    Independent physical acceptance and native construction are never implied.
    Optional recovery adds at most four unused deep fits and four width repairs
    (5024transports),after historical success opportunities are exhausted.
    """
    if ledger.started is not None:
        raise ValueError("Search ledgers are one-use;preserve prior outcomes.")
    ledger.started = perf_counter()
    pending: list[Trial] = []
    short_seeds: list[Seed] = []

    def retain(trial: Trial) -> bool:
        """
        Queue colliding closed paths while selecting the first measured handoff.
        """
        ledger.trials.append(trial)
        if (
            trial.phase != "width"
            and trial.metrics["strict_endpoint_gate"]
            and trial.contact["contact_detected"]
        ):
            pending.append(trial)
        if trial.ready_for_analysis:
            ledger.chosen = len(ledger.trials) - 1
        return trial.ready_for_analysis

    try:
        ledger.stage = "cold screens"
        ledger.seed_bank = broad_chart.screen(case, checkpoint)
        selected = select(ledger.seed_bank, maximum=16)
        ledger.selected_short = tuple(seed.index for seed in selected)
        for seed in selected:
            ledger.stage = f"short seed{seed.index}"
            path, metrics = box_fit.refine(case, seed, checkpoint, box_fit.SHORT)
            trial = _observe(case, seed, path, metrics, "short", checkpoint)
            ready = retain(trial)
            short_seeds.append(
                Seed(
                    seed.index,
                    metrics["coordinates"],
                    trial.rank,
                    broad_chart.descriptor(case, path),
                )
            )
            if ready:
                break
        if ledger.chosen is None:
            for seed in select(tuple(short_seeds), maximum=4):
                ledger.stage = f"deep seed{seed.index}"
                path, metrics = box_fit.refine(case, seed, checkpoint, box_fit.DEEP)
                trial = _observe(case, seed, path, metrics, "deep", checkpoint)
                ledger.selected_deep.append(seed.index)
                if retain(trial):
                    break
        if ledger.chosen is None:
            for original in sorted(pending, key=lambda trial: (trial.rank, trial.seed.index)):
                ledger.stage = f"width seed{original.seed.index}"
                path, metrics = projected_clearance.refine(
                    case, original.seed, original.metrics, checkpoint
                )
                metrics["base_metrics"] = original.metrics
                if retain(_observe(case, original.seed, path, metrics, "width", checkpoint)):
                    break
        if ledger.chosen is None and recovery is not RecoveryPolicy.NONE:
            unused = tuple(seed for seed in short_seeds if seed.index not in ledger.selected_deep)
            recovery_pending = len(pending)
            for seed in select(unused, maximum=recovery.value):
                ledger.stage = f"recovery deep seed{seed.index}"
                path, metrics = box_fit.refine(case, seed, checkpoint, box_fit.DEEP)
                metrics["recovery"] = recovery.name
                ledger.selected_deep.append(seed.index)
                if retain(_observe(case, seed, path, metrics, "deep", checkpoint)):
                    break
            if ledger.chosen is None:
                for original in sorted(
                    pending[recovery_pending:], key=lambda trial: (trial.rank, trial.seed.index)
                ):
                    ledger.stage = f"recovery width seed{original.seed.index}"
                    path, metrics = projected_clearance.refine(
                        case, original.seed, original.metrics, checkpoint
                    )
                    metrics.update(base_metrics=original.metrics, recovery=recovery.name)
                    if retain(_observe(case, original.seed, path, metrics, "width", checkpoint)):
                        break
        checkpoint()
        ledger.stage = "awaiting independent analysis" if ledger.chosen is not None else "exhausted"
        return ledger
    finally:
        ledger.seconds = perf_counter() - ledger.started
