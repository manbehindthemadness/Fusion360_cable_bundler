"""
Prioritize strictly verified flat crossings without treating a missed probe as clearance.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute


def screen(
    source: FoldRoute,
    measurement: ContactResult,
    remaining_pairs: int,
    probe: FlatProbe,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> ContactResult:
    """
    Find negative evidence before an ambiguous depth box dictates a correction.

    Use one bounded probe in stable original material-pair order. Its strict
    inverse tests must establish every returned crossing. A miss or accelerator
    limit retains the original unresolved measurement. The caller owns the
    probe so even interrupted preparation can charge every comparison and all
    CPU/wall time to its existing allowance. No geometry is moved or accepted.
    """
    if type(remaining_pairs) is not int or not 0 < remaining_pairs <= 2048:
        raise ValueError("Supply positive remaining original contact work")
    if probe.comparisons or probe.supports or probe.inverse_tests:
        raise ValueError("Use one fresh probe owned by this existing allocation")
    if measurement.status != "unresolved" or measurement.limit != "depth":
        return measurement
    actual = None
    for first in range(len(source.pieces)):
        for second in range(first + 1, len(source.pieces)):
            checkpoint()
            found = probe(source, first, second, remaining_pairs - probe.comparisons, checkpoint)
            actual = found.witness
            if (
                actual is not None
                or found.limit is not None
                or probe.comparisons >= remaining_pairs
            ):
                break
        else:
            continue
        break
    record(
        {
            "stage": "depth_witness_probe",
            "witness": asdict(actual) if actual else None,
            "counters": asdict(probe),
            "remaining_pairs": remaining_pairs - probe.comparisons,
        }
    )
    if actual is None:
        return measurement
    return ContactResult(
        "penetration",
        probe.comparisons,
        witness=actual,
        reason="Strict negative-only flat witnesses on the unchanged depth-unresolved source.",
    )
