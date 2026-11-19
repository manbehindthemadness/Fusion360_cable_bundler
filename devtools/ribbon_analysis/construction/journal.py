"""
Flush bounded trace prefixes and replay them without importing a solver or Fusion.
"""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter, process_time
from typing import Any

from . import records


class TraceLimit(RuntimeError):
    """
    Preserve the existing prefix when a finite trace resource allowance is exhausted.
    """


class Journal:
    """
    Own an exclusive append-only JSONL stream with independently bounded display sampling.

    Observer errors propagate instead of silently losing diagnostic evidence.
    Callers must include observer cost in their aggregate resource accounting.
    The journal neither decides route acceptance nor grants a physical certificate.
    """

    def __init__(self, path: Path, run_id: str, provenance: dict[str, Any]) -> None:
        """
        Create a new trace without overwriting a previous execution or its failure prefix.
        """
        self.path = path
        self.known: dict[str, Any] = {}
        self.steps = self.points = self.bytes = 0
        self.started, self.cpu_started = perf_counter(), process_time()
        self.stream = path.open("x", encoding="utf-8")
        self._append(
            {
                "type": "header",
                "schema": records.SCHEMA,
                "run_id": records.text(run_id),
                "units": "mm",
                "provenance": provenance,
            }
        )

    def _append(self, value: dict[str, Any]) -> dict[str, Any]:
        """
        Freeze one finite record before writing, flushing and exposing its detached copy.
        """
        line = records.canonical(value) + "\n"
        size = len(line.encode("utf-8"))
        if self.bytes + size > records.MAX_BYTES:
            raise TraceLimit("Construction trace reached32MiB; prefix retained")
        self.stream.write(line)
        self.stream.flush()
        self.bytes += size
        return json.loads(line)

    def define(
        self, identifier: str, label: str, kind: str, parents: tuple[str, ...], source: str
    ) -> None:
        """
        Register one stable feature once; identical redefinitions retain its original identity.
        """
        value = {
            "id": identifier,
            "label": label,
            "kind": kind,
            "parents": parents,
            "source": source,
        }
        frozen = json.loads(records.canonical(value))
        if identifier in self.known and self.known[identifier] == frozen:
            return
        if len(self.known) >= 1024:
            raise TraceLimit("Construction trace reached1024feature definitions")
        records.feature(value, self.known)
        self._append({"type": "feature", "feature": value})
        self.known[identifier] = frozen

    def emit(
        self,
        phase: str,
        title: str,
        status: str,
        basis: str,
        scene: list[dict[str, Any]],
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Seal a complete stage scene, distinguishing observed decisions from reconstructed assembly.
        """
        if (
            phase not in records.PHASES
            or status not in records.STATUSES
            or basis not in records.BASES
        ):
            raise ValueError("Unknown trace phase, disposition or evidence basis")
        count = records.objects(scene, self.known)
        if self.steps >= records.MAX_STEPS or self.points + count > records.MAX_POINTS:
            raise TraceLimit("Construction trace reached its512stage/300000point allowance")
        self._append(
            {
                "type": "step",
                "index": self.steps,
                "phase": phase,
                "title": records.text(title),
                "status": status,
                "basis": basis,
                "scene": scene,
                "details": details or {},
                "elapsed_wall_seconds": perf_counter() - self.started,
                "elapsed_cpu_seconds": process_time() - self.cpu_started,
            }
        )
        self.steps += 1
        self.points += count

    def close(self) -> None:
        """
        Release only this trace stream, retaining even an unsuccessful execution's prefix.
        """
        self.stream.close()


def load(path: Path) -> dict[str, Any]:
    """
    Validate a bounded complete-line prefix; missing stages remain absent, never invented.
    """
    if path.stat().st_size > records.MAX_BYTES:
        raise TraceLimit("Trace exceeds32MiB")
    known: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []
    points = 0
    header: dict[str, Any] | None = None
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.endswith("\n"):
                raise ValueError("Truncated trace record; preserve and inspect the source prefix")
            row = json.loads(line)
            records.canonical(row)  # Reject nonfinite values anywhere, including metadata.
            if not isinstance(row, dict):
                raise ValueError("Trace records must be objects")
            if header is None:
                if (
                    row.get("type") != "header"
                    or row.get("schema") != records.SCHEMA
                    or row.get("units") != "mm"
                    or not isinstance(row.get("provenance"), dict)
                ):
                    raise ValueError("Unsupported construction trace header")
                records.text(row.get("run_id"))
                header = row
            elif row.get("type") == "feature":
                value = row.get("feature")
                if not isinstance(value, dict) or len(known) >= 1024:
                    raise ValueError("Invalid feature record")
                records.feature(value, known)
                known[value["id"]] = value
            elif row.get("type") == "step":
                if (
                    row.get("index") != len(steps)
                    or type(row.get("index")) is not int
                    or row.get("phase") not in records.PHASES
                    or row.get("basis") not in records.BASES
                    or row.get("status") not in records.STATUSES
                ):
                    raise ValueError("Invalid or reordered construction stage")
                records.text(row.get("title"))
                points += records.objects(row.get("scene"), known)
                if len(steps) >= records.MAX_STEPS or points > records.MAX_POINTS:
                    raise TraceLimit("Trace stage/point allowance exceeded")
                if not isinstance(row.get("details"), dict):
                    raise ValueError("Stage details must be an object")
                steps.append(row)
            else:
                raise ValueError("Unknown construction trace record")
    if header is None or not steps:
        raise ValueError("No construction stages were recorded")
    return {"header": header, "features": known, "steps": steps}
