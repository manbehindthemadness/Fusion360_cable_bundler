"""
Load the versioned development corpus with exact target and historical failure provenance.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_locked_solver.settings import Settings

CORPUS = Path(__file__).with_name("gym-v2.json")


def signature(target: dict[str, Any]) -> str:
    """
    Identify exact physical input values independently of the display name.
    """
    values = {key: value for key, value in target.items() if key != "name"}
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def targets(payload: dict[str, Any]) -> Targets:
    """
    Validate the saved fixed poses directly, without gym regeneration or rounding.
    """
    return Targets.capture(
        Targets(
            **{
                key: Vector3(**value) if isinstance(value, dict) else value
                for key, value in payload.items()
            }
        )
    )


def load(path: Path = CORPUS) -> dict[str, Any]:
    """
    Reject malformed, duplicate or unidentified cases before any numerical execution.

    Historical outcomes describe their original source and settings. They are
    not expected outcomes for a new solver, and the corpus is development evidence.
    """
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or payload.get("schema") != "ribbon-gym-regression-v1":
        raise ValueError("Unsupported gym regression corpus")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Regression corpus needs complete cases")
    identities: set[str] = set()
    inputs: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"]:
            raise ValueError("Regression case needs an identity")
        target = case.get("targets")
        if not isinstance(target, dict):
            raise ValueError("Regression case needs frozen targets")
        targets(target)
        Settings.parse(case.get("settings"))
        digest = signature(target)
        if digest != case.get("signature") or digest in inputs or case["id"] in identities:
            raise ValueError("Regression case identity or target digest mismatch")
        history = case.get("history")
        if not isinstance(history, list) or not history:
            raise ValueError("Regression case needs historical provenance")
        for event in history:
            if (
                not isinstance(event, dict)
                or not isinstance(event.get("job"), str)
                or not isinstance(event.get("plan_sha256"), str)
                or not isinstance(event.get("source_digest"), str)
                or not isinstance(event.get("disposition"), str)
            ):
                raise ValueError("Malformed regression provenance")
        inputs.add(digest)
        identities.add(case["id"])
    return payload
