"""
Capture every transported search path in an explicit, append-only recording scope.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterator

from ..contracts import RibbonPath
from .archive import _integer, canonical, parse_snapshot, snapshot_payload
from .geometry import PathSnapshot, freeze_path


@dataclass(frozen=True)
class CaptureLimits:
    """
    Bound path count, control points and persistent bytes without dropping proposals.
    """

    paths: int = 4096
    control_points: int = 2_000_000
    bytes: int = 256 * 1024 * 1024

    def __post_init__(self) -> None:
        """
        Require explicit positive integer budgets.
        """
        if any(
            isinstance(v, bool) or not isinstance(v, int) or v <= 0
            for v in (self.paths, self.control_points, self.bytes)
        ):
            raise ValueError("Capture limits must be positive integers.")


_active: contextvars.ContextVar[SearchRecorder | None] = contextvars.ContextVar(
    "ribbon_search_recorder", default=None
)
_stage: contextvars.ContextVar[str] = contextvars.ContextVar(
    "ribbon_search_stage", default="transport"
)


class SearchRecorder:
    """
    Preserve each completed transport before the solver can replace its path.

    The scoped observer never changes coordinates, objectives, decisions or return
    values. Capture failures propagate and stop the affected run. Its overhead is
    recorded explicitly and remains part of the caller's elapsed scheduling cap.
    """

    def __init__(
        self,
        path: Path,
        solver: str,
        checkpoint: Callable[[], None],
        limits: CaptureLimits | None = None,
    ) -> None:
        """
        Open a new history file;existing evidence and nested scopes are not reused.
        """
        if not solver.strip():
            raise ValueError("Declare the recorded solver identity.")
        self.path, self.solver, self.checkpoint = path, solver, checkpoint
        self.limits = limits if limits is not None else CaptureLimits()
        self.count = self.control_points = self.bytes = 0
        self.seconds = 0.0
        self.last: PathSnapshot | None = None
        self._stream = path.open("x", encoding="utf-8")

    @contextlib.contextmanager
    def recording(self) -> Iterator[SearchRecorder]:
        """
        Activate only this execution context and restore it after any exception.
        """
        if _active.get() is not None or self._stream.closed:
            raise RuntimeError("Search recording scopes cannot overlap or reopen.")
        token = _active.set(self)
        try:
            yield self
        finally:
            _active.reset(token)
            self._stream.close()

    def record(self, path: RibbonPath, intervals: int) -> None:
        """
        Freeze and flush a complete path, including derivative probes and rejected trials.
        """
        self.checkpoint()
        if self.count >= self.limits.paths:
            raise RuntimeError("Search path recording count cap.")
        expected_points = (1 if path.field.lines == 1 else 3) * (3 * intervals + 1)
        if self.control_points + expected_points > self.limits.control_points:
            raise RuntimeError("Search path recording control-point cap.")
        began = perf_counter()
        try:
            snapshot = freeze_path(f"{self.solver}:{self.count:05}", path, intervals=intervals)
            event = {
                "kind": "path",
                "sequence": self.count,
                "solver": self.solver,
                "stage": _stage.get(),
                "snapshot": snapshot_payload(snapshot),
            }
            encoded = canonical(event) + "\n"
            size = len(encoded.encode())
            if self.bytes + size > self.limits.bytes:
                raise RuntimeError("Search path recording byte cap.")
            self._stream.write(encoded)
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self.count += 1
            self.control_points += expected_points
            self.bytes += size
            self.last = snapshot
        finally:
            self.seconds += perf_counter() - began
        self.checkpoint()

    def decision(self, score: float, accepted: bool | None, coordinates: tuple[float, ...]) -> None:
        """
        Append the observed decision without modifying its already stored geometry.
        """
        if (
            not self.count
            or not math.isfinite(score)
            or any(not math.isfinite(v) for v in coordinates)
        ):
            raise ValueError("A recorded decision needs a completed path and finite values.")
        event = {
            "kind": "decision",
            "sequence": self.count - 1,
            "score": score,
            "accepted": accepted,
            "coordinates": coordinates,
        }
        encoded = canonical(event) + "\n"
        size = len(encoded.encode())
        if self.bytes + size > self.limits.bytes:
            raise RuntimeError("Search decision recording byte cap.")
        self._stream.write(encoded)
        self._stream.flush()
        self.bytes += size


@contextlib.contextmanager
def search_stage(name: str) -> Iterator[None]:
    """
    Attach an explicit caller stage to all transports within this bounded scope.
    """
    token = _stage.set(name)
    try:
        yield
    finally:
        _stage.reset(token)


def transported(path: RibbonPath, intervals: int) -> None:
    """
    Observe an unchanged path only when the caller explicitly activated recording.
    """
    recorder = _active.get()
    if recorder is not None:
        recorder.record(path, intervals)


def decision(score: float, accepted: bool | None, coordinates: tuple[float, ...]) -> None:
    """
    Append a fitter decision only to its own active recording context.
    """
    recorder = _active.get()
    if recorder is not None:
        recorder.decision(score, accepted, coordinates)


def read_history(path: Path, *, allow_interrupted_tail: bool = False) -> tuple[dict[str, Any], ...]:
    """
    Index a bounded append-only history, retaining file offsets rather than all paths.
    """
    if path.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("Search history exceeds256MiB.")
    records: list[dict[str, Any]] = []
    with path.open("rb") as stream:
        while True:
            offset = stream.tell()
            line = stream.readline(4 * 1024 * 1024 + 1)
            if not line:
                break
            if len(line) > 4 * 1024 * 1024:
                raise ValueError("Oversized or interrupted search history event.")
            if not line.endswith(b"\n"):
                if allow_interrupted_tail:
                    break
                raise ValueError("Interrupted search history event.")
            event = json.loads(line)
            if not isinstance(event, dict) or event.get("kind") not in ("path", "decision"):
                raise ValueError("Malformed search history event.")
            sequence = _integer(event.get("sequence"))
            if event["kind"] == "path":
                if sequence != len(records) or len(records) >= 4096:
                    raise ValueError("Search paths must retain contiguous explicit order.")
                records.append(
                    {
                        "sequence": sequence,
                        "offset": offset,
                        "stage": event.get("stage"),
                        "score": None,
                        "accepted": None,
                    }
                )
            elif sequence != len(records) - 1 or sequence < 0:
                raise ValueError("Search decision does not follow its path.")
            else:
                score = event.get("score")
                if (
                    isinstance(score, bool)
                    or not isinstance(score, (int, float))
                    or not math.isfinite(score)
                ):
                    raise ValueError("Search decision score must be finite.")
                if event.get("accepted") is not None and not isinstance(event["accepted"], bool):
                    raise ValueError("Search acceptance must be boolean or unknown.")
                records[-1].update(score=score, accepted=event.get("accepted"))
    return tuple(records)


def load_history_path(path: Path, record: dict[str, Any]) -> PathSnapshot:
    """
    Load one previously indexed geometry snapshot without running a solver.
    """
    offset = record.get("offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("Search record offset must be nonnegative.")
    with path.open("rb") as stream:
        stream.seek(offset)
        event = json.loads(stream.readline(4 * 1024 * 1024 + 1))
    if (
        not isinstance(event, dict)
        or event.get("kind") != "path"
        or event.get("sequence") != record.get("sequence")
    ):
        raise ValueError("Search index no longer matches its path file.")
    return parse_snapshot(event.get("snapshot"))
