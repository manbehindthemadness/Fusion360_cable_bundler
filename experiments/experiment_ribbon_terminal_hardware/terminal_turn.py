"""
Select one early coupled turn reversal from actual terminal fold intrusion.
"""

from __future__ import annotations

from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .check import Report
from .feature_guidance import FeatureEvidence, IncidentGuidance
from .gate import Gate
from .joint_contact import recover as recover_joints
from .recovery_limits import Work, validate
from .reversal_model import incident_fold


def recover(
    original: FoldRoute,
    evidence: Report,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    maximum_updates: int,
) -> Result | None:
    """
    Replace signed-only fold recovery with one evidence-selected reflected joint action.

    The witnessed fold need not be terminal-most. Only that turn changes sign;
    existing runways, angles and banks reclose both ordered caps while independent
    occupied-member inequalities clear the fixed terminal proxies. The original
    construction length ceiling, radii, joined profile and material order remain.
    Unsupported evidence does no motion. A failed chosen action cannot start
    another sign, radius or signed-only fallback. All preparation, derivatives
    and certificates share the caller's genuinely remaining work and gate.
    """
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    if evidence.status != "blocked" or evidence.witness is None:
        return None
    witness = evidence.witness
    if not 0 <= witness.piece < len(original.pieces):
        raise ValueError("Terminal evidence must identify an existing material piece")
    if not isinstance(original.pieces[witness.piece].geometry, CylindricalFold):
        return None
    cpu, wall = process_time(), perf_counter()
    checkpoint()
    selected = incident_fold(original, witness)
    assert selected is not None
    guidance = IncidentGuidance(selected, (FeatureEvidence(original, evidence),))
    record(
        {
            "stage": "terminal_fold_reversal",
            "status": "selected",
            "selected_fold": selected,
            "source": snapshot(original),
            "evidence": asdict(evidence),
        }
    )
    left = Work(maximum_updates, remaining_pairs, maximum_cpu_seconds, maximum_seconds).remaining(
        updates=0,
        pairs=0,
        cpu_seconds=process_time() - cpu,
        wall_seconds=perf_counter() - wall,
    )
    if left is None:
        return Result(
            original,
            None,
            {
                "status": "unresolved",
                "stop_reason": "phase_budget",
                "iterations": 0,
                "newton_steps": 0,
                "contacts": 0,
                "contact_pairs": 0,
                "contact_seconds": 0.0,
                "cpu_seconds": process_time() - cpu,
                "elapsed_seconds": perf_counter() - wall,
            },
        )
    result = recover_joints(
        original,
        evidence,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=left.pairs,
        maximum_cpu_seconds=left.cpu_seconds,
        maximum_seconds=left.wall_seconds,
        maximum_updates=left.updates,
        mode=guidance,
    )
    if result is None:
        result = Result(
            original,
            None,
            {
                "status": "unresolved",
                "stop_reason": "unsupported_reflected_features",
                "iterations": 0,
                "newton_steps": 0,
                "contacts": 0,
                "contact_pairs": 0,
                "contact_seconds": 0.0,
            },
        )
    detail = {
        **result.detail,
        "purpose": "terminal_fold_reversal",
        "cpu_seconds": process_time() - cpu,
        "elapsed_seconds": perf_counter() - wall,
    }
    if detail["cpu_seconds"] >= maximum_cpu_seconds or detail["elapsed_seconds"] >= maximum_seconds:
        detail.update(status="unresolved", stop_reason="phase_budget")
        result = Result(original, None, detail)
    record({"stage": "terminal_fold_reversal", "status": detail["status"], "detail": detail})
    return Result(result.route if result.contact is not None else original, result.contact, detail)
