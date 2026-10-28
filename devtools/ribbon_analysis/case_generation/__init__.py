"""
Generate fixed boundary challenges and adapt solved paths to shared diagnostics.

Generation does not run a solver,Fusion,screening or native construction. Interior
scenario events remain intent until a separate event-coverage measurement exists.
"""

from __future__ import annotations

from ..api import Candidate
from ..contracts import RibbonPath
from .codec import fingerprint, read, write
from .generator import generate
from .installations import FAMILIES, Connector, Installation
from .models import Case, Event, GenerationMode, Manifest, RandomBounds

__all__ = [
    "Case",
    "Connector",
    "Event",
    "FAMILIES",
    "GenerationMode",
    "Installation",
    "Manifest",
    "RandomBounds",
    "candidate_for",
    "fingerprint",
    "generate",
    "read",
    "write",
]


def candidate_for(
    manifest: Manifest, case: Case, path: RibbonPath, *, solver_source: str
) -> Candidate:
    """
    Attach a solved or partially solved path to its exact frozen target challenge.

    Do not substitute a repaired path or different dimensions. Endpoint failures
    remain analyzable;this adapter does not require success or certify compliance.
    Callers must separately retain exhausted,failed and unattempted dispositions
    when no path exists. Source fingerprints for the solver remain caller-owned.
    """
    if manifest.by_identifier.get(case.identifier) != case:
        raise ValueError("Case is not in this manifest.")
    if not isinstance(solver_source, str) or not solver_source.strip():
        raise ValueError("Supply the solver source revision/pin.")
    if path.field.lines != case.targets.lines or path.field.diameter_mm != case.targets.diameter_mm:
        raise ValueError("Solved path dimensions differ from frozen targets.")
    digest = fingerprint(manifest)
    source = f"solver:{solver_source};batch:{digest};generator:{manifest.generator_digest};mode:{manifest.mode};stratum:{case.stratum};reference:{case.reference};events:intent-only"
    return Candidate(digest[:12] + ":" + case.identifier, path, case.targets, source)
