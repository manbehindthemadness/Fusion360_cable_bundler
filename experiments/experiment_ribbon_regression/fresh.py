"""
Reserve outcome-independent random runs using only seed and layout novelty fingerprints.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
from secrets import randbits
from time import monotonic
from typing import Any, Iterable

from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification


def _json(value: Any) -> str:
    """
    Serialize finite metadata deterministically without retaining geometry through alternate encodings.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def layout_fingerprint(targets: Targets) -> str:
    """
    Identify physical boundary inputs independently of names, seeds or run identifiers.

    Duplicate detection uses nine decimal places for millimeters and twelve for
    frame components. This conservatively merges floating roundoff aliases only
    in the novelty index; original solver inputs remain entirely unrounded.
    """
    if type(targets.lines) is not int or targets.lines < 1:
        raise ValueError("Layout identity requires a positive conductor count")

    def number(value: float, digits: int) -> float:
        """
        Reject nonfinite identity data and normalize signed zero without moving actual inputs.
        """
        if isinstance(value, bool) or not math.isfinite(value):
            raise ValueError("Layout identity requires finite geometry")
        rounded = round(value, digits)
        return rounded if rounded else 0.0

    payload: dict[str, Any] = {
        "lines": targets.lines,
        "diameter_mm": number(targets.diameter_mm, 9),
    }
    if targets.diameter_mm <= 0:
        raise ValueError("Layout identity requires positive thickness")
    for name in ("start", "end", "start_tangent", "end_tangent", "start_width", "end_width"):
        vector = getattr(targets, name)
        digits = 9 if name in ("start", "end") else 12
        payload[name] = [number(getattr(vector, axis), digits) for axis in "xyz"]
    return hashlib.sha256(_json(payload).encode()).hexdigest()


@dataclass(frozen=True)
class FreshRun:
    """
    Carry a finite precommitted input schedule without solving or retaining historical routes.
    """

    identifier: str
    specification: Specification
    fingerprints: tuple[str, ...]
    seed_proposals: int


class FreshRegistry:
    """
    Keep unique seed/layout fingerprints and aggregate run statistics across future campaigns.

    SQLite transactions reserve the complete schedule before any solver outcome.
    Even unattempted reservations remain used, so an interrupted run cannot turn
    its planned inputs into supposedly unseen inputs later. Case coordinates,
    reference routes and screenshots are never stored in this comparison index.
    """

    def __init__(self, path: Path) -> None:
        """
        Initialize an exclusively development-owned novelty/statistics database.
        """
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=1)) as connection:
            connection.executescript(
                "CREATE TABLE IF NOT EXISTS runs ("
                "identifier TEXT PRIMARY KEY, seed_hash TEXT UNIQUE, metadata TEXT NOT NULL, "
                "summary TEXT);"
                "CREATE TABLE IF NOT EXISTS layouts (digest TEXT PRIMARY KEY);"
            )

    def prepare(
        self, template: Specification, identifier: str, metadata: dict[str, Any]
    ) -> FreshRun:
        """
        Reserve a new seed and entirely novel finite schedule before any solve.

        Try at most sixteen random run seeds and thirty seconds of input authoring.
        A seed collision or layout duplicate rejects that whole proposed schedule
        independently of outcomes. Exhaustion stops preparation without starting
        geometry and does not establish that the input space is exhausted.
        """
        if template.mode != "random" or not 1 <= template.maximum_cases <= 10_000:
            raise ValueError(
                "Fresh validation requires random mode and a finite 1..10000 case limit"
            )
        if not isinstance(identifier, str) or not 0 < len(identifier) <= 128:
            raise ValueError("Supply a nonempty bounded run identifier")
        encoded = _json(metadata)
        deadline = monotonic() + 30
        with closing(sqlite3.connect(self.path, timeout=1)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM runs WHERE identifier=?", (identifier,)
            ).fetchone():
                raise ValueError("A fresh run identifier cannot be reused")
            for proposal in range(1, 17):
                seed = randbits(32)
                seed_hash = hashlib.sha256(str(seed).encode()).hexdigest()
                if connection.execute(
                    "SELECT 1 FROM runs WHERE seed_hash=?", (seed_hash,)
                ).fetchone():
                    continue
                specification = replace(template, seed=seed)
                fingerprints = []
                for index in range(specification.maximum_cases):
                    if monotonic() >= deadline:
                        raise TimeoutError(
                            "Fresh input preparation reached its thirty-second limit"
                        )
                    fingerprints.append(layout_fingerprint(specification.scene(index).targets))
                if len(set(fingerprints)) != len(fingerprints) or any(
                    connection.execute("SELECT 1 FROM layouts WHERE digest=?", (value,)).fetchone()
                    for value in fingerprints
                ):
                    continue
                connection.execute(
                    "INSERT INTO runs VALUES (?,?,?,NULL)", (identifier, seed_hash, encoded)
                )
                connection.executemany(
                    "INSERT INTO layouts VALUES (?)", ((value,) for value in fingerprints)
                )
                return FreshRun(identifier, specification, tuple(fingerprints), proposal)
        raise RuntimeError(
            "No entirely novel schedule within sixteen seed proposals; no solve started"
        )

    def remember(self, fingerprints: Iterable[str], *, seed: int | None = None) -> None:
        """
        Retire known inputs into duplicate-detection hashes without preserving replayable fixtures here.
        """
        values = set(fingerprints)
        if any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in values
        ):
            raise ValueError("Novelty history accepts only SHA-256 layout fingerprints")
        if seed is not None and (type(seed) is not int or not 0 <= seed < 2**32):
            raise ValueError("Historical seed identity must be an unsigned32-bit integer")
        with closing(sqlite3.connect(self.path, timeout=1)) as connection, connection:
            connection.executemany(
                "INSERT OR IGNORE INTO layouts VALUES (?)", ((v,) for v in values)
            )
            if seed is not None:
                seed_hash = hashlib.sha256(str(seed).encode()).hexdigest()
                connection.execute(
                    "INSERT OR IGNORE INTO runs VALUES (?,?,?,NULL)",
                    ("retired-seed-" + seed_hash, seed_hash, _json({"population": "retired_seed"})),
                )

    def record(self, identifier: str, metadata: dict[str, Any], summary: dict[str, Any]) -> None:
        """
        Store one aggregate outcome, rejecting replacement of an already finalized run.

        Imported historical statistics may have no seed entry. Prepared runs keep
        their original metadata and reserved seed hash when their summary is added.
        """
        encoded_metadata, encoded_summary = _json(metadata), _json(summary)
        with closing(sqlite3.connect(self.path, timeout=1)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT metadata,summary FROM runs WHERE identifier=?", (identifier,)
            ).fetchone()
            if previous is None:
                connection.execute(
                    "INSERT INTO runs VALUES (?,NULL,?,?)",
                    (identifier, encoded_metadata, encoded_summary),
                )
            elif previous[0] != encoded_metadata or previous[1] is not None:
                raise ValueError("Historical statistics or prepared metadata cannot be overwritten")
            else:
                connection.execute(
                    "UPDATE runs SET summary=? WHERE identifier=?", (encoded_summary, identifier)
                )

    def statistics(self) -> list[dict[str, Any]]:
        """
        Read finalized aggregate comparisons without exposing historical layouts or run seeds.
        """
        with closing(sqlite3.connect(self.path, timeout=1)) as connection:
            rows = connection.execute(
                "SELECT identifier,metadata,summary FROM runs WHERE summary IS NOT NULL ORDER BY rowid"
            )
            return [
                {
                    "identifier": name,
                    "metadata": json.loads(metadata),
                    "summary": json.loads(summary),
                }
                for name, metadata, summary in rows
            ]
