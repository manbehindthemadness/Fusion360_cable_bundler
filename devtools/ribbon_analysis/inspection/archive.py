"""
Persist inspectable geometry as versioned JSON without executing solver code on replay.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from cable_bundler.routing.geometry import CubicBezier, Vector3

from ..contracts import TargetPose, Targets
from ..traces import TracePath
from .geometry import LocalFrame, PathSnapshot, Section
from .values import finite_number as _number
from .values import integer_value as _integer
from .values import json_object as _object

SCHEMA = "ribbon-inspection-v1"


def _text(value: Any) -> str:
    """
    Require nonempty text before using external data as a record identity.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Inspection text must be nonempty.")
    return value


def _vector(value: Any) -> Vector3:
    """
    Read an explicit finite XYZ object.
    """
    values = _object(value)
    if set(values) != {"x", "y", "z"}:
        raise ValueError("Inspection vectors require exactly XYZ.")
    return Vector3(*(_number(values[key]) for key in ("x", "y", "z")))


def canonical(value: Any) -> str:
    """
    Serialize deterministic finite JSON for identity and append-only evidence.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def snapshot_payload(snapshot: PathSnapshot) -> dict[str, Any]:
    """
    Store cubic controls once, with sections and a content digest.
    """
    payload = {
        "identifier": snapshot.identifier,
        "lines": snapshot.lines,
        "diameter_mm": snapshot.diameter_mm,
        "intervals": snapshot.intervals,
        "guides": [
            {"number": g.number, "controls": [asdict(p) for p in g.controls], "knots": g.knots}
            for g in snapshot.guides
        ],
        "sections": [asdict(section) for section in snapshot.sections],
    }
    return {"geometry": payload, "sha256": hashlib.sha256(canonical(payload).encode()).hexdigest()}


def parse_snapshot(value: Any) -> PathSnapshot:
    """
    Validate a content-addressed snapshot before rebuilding shared cubic objects.
    """
    wrapped = _object(value)
    payload = _object(wrapped.get("geometry"))
    if wrapped.get("sha256") != hashlib.sha256(canonical(payload).encode()).hexdigest():
        raise ValueError("Inspection geometry fingerprint mismatch.")
    intervals = _integer(payload.get("intervals"))
    if not 16 <= intervals <= 1024:
        raise ValueError("Inspection guide grid is outside16..1024.")
    source_guides, source_sections = payload.get("guides"), payload.get("sections")
    if not isinstance(source_guides, list) or not 1 <= len(source_guides) <= 3:
        raise ValueError("Inspection snapshot needs one to three guides.")
    if not isinstance(source_sections, list) or not 2 <= len(source_sections) <= 65:
        raise ValueError("Inspection snapshot needs2..65sections.")
    guides = []
    expected_knots = (
        (0.0,) * 4
        + tuple(i / intervals for i in range(1, intervals) for _ in range(3))
        + (1.0,) * 4
    )
    for item in source_guides:
        data = _object(item)
        points = data.get("controls")
        if not isinstance(points, list) or len(points) != 3 * intervals + 1:
            raise ValueError("Inspection cubic controls disagree with the grid.")
        knots = data.get("knots")
        if not isinstance(knots, list) or tuple(_number(k) for k in knots) != expected_knots:
            raise ValueError("Inspection knots disagree with the registered cubic chain.")
        controls = tuple(_vector(p) for p in points)
        curves = tuple(CubicBezier(*controls[i : i + 4]) for i in range(0, len(controls) - 1, 3))
        guides.append(TracePath(_integer(data.get("number")), curves, controls, expected_knots))
    sections = []
    for item in source_sections:
        data = _object(item)
        frame = _object(data.get("frame"))
        outline = data.get("outline")
        if not isinstance(outline, list) or not 2 <= len(outline) <= 129:
            raise ValueError("Inspection section contour is missing or oversized.")
        kind = data.get("kind")
        if kind not in ("circle", "material_ruling"):
            raise ValueError("Unknown inspection section kind.")
        sections.append(
            Section(
                _integer(data.get("index")),
                _number(data.get("u")),
                LocalFrame(*(_vector(frame.get(k)) for k in ("origin", "x", "y", "z"))),
                tuple(_vector(p) for p in outline),
                kind,
            )
        )
    identifier = payload.get("identifier")
    if not isinstance(identifier, str):
        raise ValueError("Inspection identity must be text.")
    return PathSnapshot(
        identifier,
        _integer(payload.get("lines")),
        _number(payload.get("diameter_mm")),
        intervals,
        tuple(guides),
        tuple(sections),
    )


@dataclass(frozen=True)
class RuleObservation:
    """
    Represent every rule explicitly, including withdrawn or unmeasured checks.
    """

    name: str
    status: Literal["measured", "unmeasured", "legacy", "not_applicable", "failed"]
    detail: str
    value: float | None = None
    limit: float | None = None

    def __post_init__(self) -> None:
        """
        Prevent unknown or nonfinite findings from masquerading as measured values.
        """
        if (
            not self.name.strip()
            or not self.detail.strip()
            or self.status not in ("measured", "unmeasured", "legacy", "not_applicable", "failed")
        ):
            raise ValueError("Rule observations require a name, scope and known status.")
        for value in (self.value, self.limit):
            if value is not None:
                _number(value)


def write_document(path: Path, payload: dict[str, Any]) -> None:
    """
    Write a new finite JSON document, never replacing historical evidence.
    """
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(payload))
        stream.flush()
        os.fsync(stream.fileno())


def read_document(path: Path) -> dict[str, Any]:
    """
    Read a bounded manifest and reject unsupported schemas before native work.
    """
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Inspection manifest exceeds32MiB.")
    payload = _object(json.loads(path.read_text(encoding="utf-8")))
    if payload.get("schema") != SCHEMA:
        raise ValueError("Unknown inspection archive schema.")
    return payload


def targets_payload(targets: TargetPose) -> dict[str, Any]:
    """
    Copy validated fixed poses and dimensions into an inspection manifest.
    """
    return asdict(Targets.capture(targets))
