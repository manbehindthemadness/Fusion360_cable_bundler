"""
Pin gym execution to the authorized advisory-screen candidate and complete pipeline.
"""

from __future__ import annotations

from pathlib import Path

from artifacts.verification.resume3227 import manifest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "artifacts/verification/resume3374/advisory-runtime-final-plan.json"


def capture() -> dict[str, str]:
    """
    Check inherited executable/policy pins, then capture new experimental modules.

    Documentation and historical result receipts are not executable dependencies.
    Their original manifests remain immutable; this runtime lock retains every
    inherited Python and safeguard byte, including all361 selected solver files.
    No baseline source replacement or selected-source promotion is permitted.
    """
    baseline = manifest.read(BASELINE)
    pins = {
        path: value
        for path, value in baseline["pins"].items()
        if path.endswith(".py")
        or path in ("experiment_testing_rules.txt", "rollback_end_loft_notes.txt")
    }
    selected = manifest.read(ROOT / "artifacts/verification/resume3047/verified.json")["sources"]
    pins.update(selected)
    verify(pins)
    for package in ("experiment_ribbon_complete", "experiment_ribbon_complete_gym"):
        for path in (ROOT / "experiments" / package).iterdir():
            if path.suffix not in (".py", ".html"):
                continue
            relative = str(path.relative_to(ROOT))
            value = manifest.digest(path)
            if relative in pins and pins[relative] != value:
                raise RuntimeError(f"Complete gym inherited source drift: {relative}")
            pins[relative] = value
    return pins


def verify(pins: dict[str, str]) -> None:
    """
    Refuse changed or missing runtime bytes before proceeding with an owned job.
    """
    for relative, value in pins.items():
        path = (ROOT / relative).resolve()
        if ROOT not in path.parents or manifest.digest(path) != value:
            raise RuntimeError(f"Complete gym source drift: {relative}")
