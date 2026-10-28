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
from .installations import Connector, Installation, validate_vector
from .models import Case, Event, Manifest, RandomBounds


def _vector_from_data(data: Any) -> Vector3:
    """
    Parse exact vector fields without accepting booleans or nonfinite coordinates.
    """
    if not isinstance(data, dict) or set(data) != {"x", "y", "z"}:
        raise ValueError("Malformed vector fields.")
    vector = Vector3(**data)
    validate_vector(vector)
    return vector


def _installation_from_data(data: Any) -> Installation | None:
    """
    Decode optional assembly context with exact keys and validated connector frames.
    """
    if data is None:
        return None
    if not isinstance(data, dict) or set(data) != {
        "family",
        "start",
        "end",
        "room_min",
        "room_max",
        "feasibility",
    }:
        raise ValueError("Malformed installation fields.")
    connectors: list[Connector] = []
    axes = {
        "exit_point",
        "exit_direction",
        "width_direction",
        "mount_point",
        "mount_normal",
        "mating_direction",
    }
    for key in ("start", "end"):
        raw = data[key]
        if not isinstance(raw, dict) or set(raw) != axes | {"mount_kind"}:
            raise ValueError("Malformed connector fields.")
        parsed = {name: _vector_from_data(raw[name]) for name in axes}
        connectors.append(Connector(**parsed, mount_kind=raw["mount_kind"]))
    return Installation(
        data["family"],
        connectors[0],
        connectors[1],
        _vector_from_data(data["room_min"]),
        _vector_from_data(data["room_max"]),
        data["feasibility"],
    )


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
        parsed[key] = _vector_from_data(data[key])
    if isinstance(data["diameter_mm"], bool) or not isinstance(data["diameter_mm"], (int, float)):
        raise ValueError("Diameter must be numeric.")
    return Targets.capture(Targets(**parsed))


def payload(manifest: Manifest) -> dict[str, Any]:
    """
    Encode all fixed poses and scenario lineage,excluding derived digest fields.
    """
    document = asdict(manifest)
    if manifest.version == 1:
        # Historical digests predate mode/context;their exact schema stays authoritative.
        del document["mode"]
        for case in document["cases"]:
            del case["installation"]
    return document


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
        keys = {
            "version",
            "seed",
            "bounds",
            "cases",
            "fingerprint",
            "generator_digest",
        }
        if not isinstance(document, dict):
            raise ValueError("Malformed manifest fields.")
        version = document.get("version")
        if version == 2:
            keys.add("mode")
        if set(document) != keys:
            raise ValueError("Malformed manifest fields.")
        if not isinstance(document["bounds"], dict) or not isinstance(document["cases"], list):
            raise ValueError("Manifest needs bounds and case arrays.")
        bounds = RandomBounds(**document["bounds"])
        cases: list[Case] = []
        for item in document["cases"]:
            case_keys = {
                "identifier",
                "stratum",
                "targets",
                "events",
                "reference",
                "note",
            }
            if version == 2:
                case_keys.add("installation")
            if not isinstance(item, dict) or set(item) != case_keys:
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
                    _installation_from_data(item["installation"]) if version == 2 else None,
                )
            )
        manifest = Manifest(
            document["version"],
            document["seed"],
            bounds,
            tuple(cases),
            document["generator_digest"],
            document["mode"] if version == 2 else "random",
        )
        if document["fingerprint"] != fingerprint(manifest):
            raise ValueError("Manifest content digest mismatch.")
        return manifest
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError("Malformed manifest values.") from exc
