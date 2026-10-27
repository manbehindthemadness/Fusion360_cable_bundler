"""
Freeze complete inputs in portable JSON;replay never depends on random state alone.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cable_bundler.routing.geometry import Vector3

from ..contracts import Targets
from .models import Case, Event, Manifest, RandomBounds


def target_from_data(data: Any) -> Targets:
    """
    Parse an external target object with explicit shape and numeric validation.
    """
    keys = {
        "name",
        "start",
        "end",
        "start_tangent",
        "end_tangent",
        "start_width",
        "end_width",
        "lines",
        "diameter_mm",
    }
    if not isinstance(data, dict) or set(data) != keys:
        raise ValueError("Malformed target fields.")
    parsed = dict(data)
    for key in keys - {"name", "lines", "diameter_mm"}:
        vector = data[key]
        if not isinstance(vector, dict) or set(vector) != {"x", "y", "z"}:
            raise ValueError("Malformed target vector.")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in vector.values()):
            raise ValueError("Target vectors need numeric coordinates.")
        parsed[key] = Vector3(**vector)
    if isinstance(data["diameter_mm"], bool) or not isinstance(data["diameter_mm"], (int, float)):
        raise ValueError("Diameter must be numeric.")
    return Targets.capture(Targets(**parsed))


def payload(manifest: Manifest) -> dict[str, Any]:
    """
    Encode all fixed poses and scenario lineage,excluding derived digest fields.
    """
    return asdict(manifest)


def compute_digest(manifest: Manifest) -> str:
    """
    Identify exact serialized inputs;this is a content digest,not a certificate.
    """
    encoded = json.dumps(payload(manifest), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def fingerprint(manifest: Manifest) -> str:
    """
    Reuse the immutable manifest's cached digest during per-case diagnostic handoff.
    """
    return manifest.content_digest


def write(manifest: Manifest, path: Path) -> None:
    """
    Write a new manifest once;never replace a previous frozen batch.
    """
    document = {**payload(manifest), "fingerprint": fingerprint(manifest)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, allow_nan=False)
        stream.write("\n")


def read(path: Path) -> Manifest:
    """
    Reject malformed/version-drifted/tampered manifests before any solver call.

    Complete saved values are authoritative for cross-runtime replay. Source
    revisions and solver settings must still be frozen separately by the runner.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or set(document) != {
            "version",
            "seed",
            "bounds",
            "cases",
            "fingerprint",
            "generator_digest",
        }:
            raise ValueError("Malformed manifest fields.")
        if not isinstance(document["bounds"], dict) or not isinstance(document["cases"], list):
            raise ValueError("Manifest needs bounds and case arrays.")
        bounds = RandomBounds(**document["bounds"])
        cases: list[Case] = []
        for item in document["cases"]:
            if not isinstance(item, dict) or set(item) != {
                "identifier",
                "stratum",
                "targets",
                "events",
                "reference",
                "note",
            }:
                raise ValueError("Malformed case fields.")
            if not isinstance(item["events"], list) or any(
                not isinstance(v, dict) or set(v) != {"kind", "degrees"} for v in item["events"]
            ):
                raise ValueError("Malformed event fields.")
            cases.append(
                Case(
                    item["identifier"],
                    item["stratum"],
                    target_from_data(item["targets"]),
                    tuple(Event(**v) for v in item["events"]),
                    item["reference"],
                    item["note"],
                )
            )
        manifest = Manifest(
            document["version"],
            document["seed"],
            bounds,
            tuple(cases),
            document["generator_digest"],
        )
        if document["fingerprint"] != fingerprint(manifest):
            raise ValueError("Manifest content digest mismatch.")
        return manifest
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError("Malformed manifest values.") from exc
