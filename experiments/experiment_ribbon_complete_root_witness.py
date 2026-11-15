"""
Qualify unchanged roots using explicit scoped trimmed-witness measurement strategy.

Requires live Fusion and new resume3233 plan. Both prior stopped scopes remain
immutable. Bindings restore in finally; no reload, function reconstruction or CAD.
"""

from __future__ import annotations

import time
from typing import Any

from artifacts.verification.resume3201.bindings import Binding, installed
from artifacts.verification.resume3227 import manifest
from experiments import experiment_ribbon_complete_root_context as prior
from experiments.experiment_ribbon_complete.native_distance import trimmed_distance_mm
from experiments.experiment_ribbon_complete.native_membership import witness_distance_mm

FOLDER = manifest.ROOT / "artifacts/verification/resume3233"
ORIGINAL_CURRENT = prior.current


def checked_current(function: Any, _qualified_name: str) -> None:
    """
    Verify the actual strategy's own qualified body instead of an imported alias's spelling.
    """
    ORIGINAL_CURRENT(function, function.__qualname__)


def collect(started: float) -> None:
    """
    Reuse the unchanged cap audit with a frozen generic correspondence strategy and new scope.
    """
    prior.current(checked_current, "checked_current")
    prior.current(collect, "collect")
    bindings = (
        Binding(prior, "FOLDER", manifest.ROOT / "artifacts/verification/resume3232", FOLDER),
        Binding(prior, "trimmed_distance_mm", trimmed_distance_mm, witness_distance_mm),
        Binding(prior, "current", ORIGINAL_CURRENT, checked_current),
    )
    with installed(bindings):
        prior.collect(started)
    assert prior.current is ORIGINAL_CURRENT and prior.trimmed_distance_mm is trimmed_distance_mm
    prior.write(
        FOLDER / "strategy-restoration.json",
        {
            "restored": True,
            "wall_seconds": time.perf_counter() - started,
            "measurement": "On-trim witness distance upper bound for accepted rawmembership; assembly-context native minimum only for misses.",
        },
    )
