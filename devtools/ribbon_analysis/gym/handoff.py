"""
Freeze endpoint-only layouts for diagnostic replay without supplying a candidate route.
"""

from __future__ import annotations

import json
import math
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..contracts import Targets
from ..inspection.archive import SCHEMA, canonical, read_document, targets_payload, write_document
from .scene import Config, Goal, Scene


def _matches(actual: Any, expected: Any) -> bool:
    """
    Check generated topology and dimensions while allowing cross-runtime float roundoff.
    """
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(_matches(actual[key], value) for key, value in expected.items())
        )
    if isinstance(expected, (tuple, list)):
        return (
            isinstance(actual, (tuple, list))
            and len(actual) == len(expected)
            and all(_matches(a, b) for a, b in zip(actual, expected))
        )
    if isinstance(expected, float):
        return (
            type(actual) in (float, int)
            and math.isfinite(actual)
            and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-10)
        )
    return type(actual) is type(expected) and actual == expected


def validate(payload: Any, targets: Targets) -> dict[str, Any] | None:
    """
    Validate optional frozen gym geometry, retaining its original numerical coordinates.

    Reconstructing the input-only scene checks the bounded drawing contract. The
    original payload is returned as a detached JSON value, never regenerated for use
    by a solver. Endpoint equality is exact; neither validation nor replay fits a path.
    """
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Gym context must be a frozen layout object.")
    try:
        scene = Scene(Config(**payload["config"]), Goal(**payload["a"]), Goal(**payload["b"]))
    except (KeyError, TypeError) as error:
        raise ValueError("Gym context requires complete layout inputs.") from error
    if not _matches(payload, scene.payload()):
        raise ValueError("Gym geometry disagrees with its declared layout inputs.")
    if payload["targets"] != targets_payload(targets):
        raise ValueError("Gym context disagrees with the frozen endpoint targets.")
    return json.loads(canonical(payload))


def identity(payload: dict[str, Any]) -> str:
    """
    Identify a complete layout, including endpoint face and orientation choices.
    """
    return "gym-" + sha256(canonical(payload).encode("utf-8")).hexdigest()


def freeze(scene: Scene, directory: Path) -> Path:
    """
    Archive one immutable diagnostic input case; repeated handoffs reuse its identity.
    """
    payload = scene.payload()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / (identity(payload) + ".json")
    if destination.exists() and canonical(read_document(destination).get("gym")) != canonical(
        payload
    ):
        raise ValueError("An existing gym archive disagrees with this layout identity.")
    if not destination.exists():
        write_document(
            destination,
            {
                "schema": SCHEMA,
                "targets": targets_payload(scene.targets),
                "gym": payload,
                "solvers": [
                    {
                        "id": "input",
                        "label": "Gym endpoint layout",
                        "source": str(destination),
                        "status": "not_run",
                        "detail": "Frozen endpoints and environment; choose procedures and Run selected. No candidate route supplied.",
                        "rules": [],
                    }
                ],
            },
        )
    return destination
