"""
Run the approved photo-inspired edge cases beside the seven retained candidates.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT

from .endpoint_reference import REFERENCE_IMAGES, reference_cases
from .lateral_native import create_batch, finish_batch, run_case

_state: dict[str, Any] | None = None


def start() -> dict[str, object]:
    """
    Freeze image/source provenance and poses before one unchanged procedural pass.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Reference batch already registered; no restart.")
    state = create_batch(reference_cases(), 7, 7, (32, -112, 0))
    state["plan"]["hypothesis"] = (
        "The unchanged endpoint-first rule can construct photo-inspired broad returns, banked crossovers and a compact reverse-heading case."
    )
    state["plan"]["reference_images"] = {
        name: hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest()
        for name in REFERENCE_IMAGES
    }
    state["plan"]["reference_sources"] = {
        str(p.relative_to(PROJECT_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__), Path(__file__).with_name("endpoint_reference.py"))
    }
    _state = state
    return state["plan"]


def run_next() -> dict[str, Any]:
    """
    Check frozen reference provenance before consuming the next approved slot.
    """
    state = _state
    if state is None:
        raise RuntimeError("No reference batch.")
    provenance = {**state["plan"]["reference_images"], **state["plan"]["reference_sources"]}
    if any(
        hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() != expected
        for name, expected in provenance.items()
    ):
        state["stop_reason"] = "Reference/source provenance changed; no further case scheduled."
        raise RuntimeError(state["stop_reason"])
    return run_case(state)


def finish() -> dict[str, object]:
    """
    Preserve the combined model and read timings without creating a report file.
    """
    if _state is None:
        raise RuntimeError("No reference batch.")
    return finish_batch(_state)
