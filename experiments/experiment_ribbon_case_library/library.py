"""
Store immutable selected diagnostic recipes in a separate, explicitly identified SQLite database.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .recipe import inspection_document, validate

APPLICATION_ID = 0x52434231
SCHEMA_VERSION = 1


def canonical(value: Any) -> str:
    """
    Detach finite JSON values and bound each selected record to32KiB.
    """
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(text.encode("utf-8")) > 32768:
        raise ValueError("Selected case recipes must remain below32KiB")
    return text


def _check(connection: sqlite3.Connection) -> None:
    """
    Reject foreign or unsupported databases before any catalogue operation can alter them.
    """
    identity = connection.execute("PRAGMA application_id").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if identity != APPLICATION_ID or version != SCHEMA_VERSION:
        raise ValueError(
            "Not a supported selected-case catalogue; foreign databases remain untouched"
        )


# Each path owns its runtime schema; an IDE-configured database is not applicable.
# noinspection SqlNoDataSourceInspection
class CaseLibrary:
    """
    Own selected input values only, with no generation, solver, statistics or automatic replay hooks.

    Each identifier is immutable. SQLite application identity prevents this tool
    from opening the novelty/statistics database as a catalogue by mistake.
    """

    def __init__(self, path: Path) -> None:
        """
        Create a new catalogue or verify an existing one read-only before obtaining write access.
        """
        self.path = path.resolve()
        if self.path.exists():
            with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as connection:
                _check(connection)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=1)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if (
                connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                or connection.execute("PRAGMA application_id").fetchone()[0] != 0
                or connection.execute("PRAGMA user_version").fetchone()[0] != 0
            ):
                raise ValueError("A catalogue cannot replace an existing database")
            connection.execute(
                "CREATE TABLE cases (identifier TEXT PRIMARY KEY, record TEXT NOT NULL, digest TEXT NOT NULL)"
            )
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def save(self, identifier: str, recipe: dict[str, Any], provenance: dict[str, Any]) -> None:
        """
        Insert one selected immutable input/provenance record, never replacing a prior result.
        """
        if (
            not isinstance(identifier, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", identifier) is None
        ):
            raise ValueError("Use a bounded alphanumeric case identifier")
        if not isinstance(provenance, dict) or set(provenance) != {
            "run_id",
            "run_seed",
            "ordinal",
            "original_outcome",
            "sources_sha256",
            "evidence",
        }:
            raise ValueError("Retain complete original run/source/outcome provenance")
        if (
            not isinstance(provenance["run_id"], str)
            or not provenance["run_id"]
            or type(provenance["run_seed"]) is not int
            or not 0 <= provenance["run_seed"] < 2**32
            or type(provenance["ordinal"]) is not int
            or provenance["ordinal"] < 1
            or provenance["original_outcome"]
            not in ("passed", "failed", "unresolved", "unattempted")
            or not isinstance(provenance["sources_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", provenance["sources_sha256"]) is None
            or not isinstance(provenance["evidence"], str)
            or not provenance["evidence"]
        ):
            raise ValueError("Invalid selected-case provenance")
        record = canonical(
            {"recipe": validate(recipe), "provenance": provenance, "fresh_validation": False}
        )
        digest = hashlib.sha256(record.encode()).hexdigest()
        with (
            closing(
                sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=1)
            ) as connection,
            connection,
        ):
            _check(connection)
            connection.execute("INSERT INTO cases VALUES (?,?,?)", (identifier, record, digest))

    def load(self, identifier: str) -> dict[str, Any]:
        """
        Return detached selected data, rejecting corrupt records rather than guessing missing inputs.
        """
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as connection:
            _check(connection)
            row = connection.execute(
                "SELECT record,digest FROM cases WHERE identifier=?", (identifier,)
            ).fetchone()
        if row is None:
            raise KeyError(identifier)
        if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise ValueError("Selected-case record integrity mismatch")
        return json.loads(row[0])

    def identifiers(self) -> tuple[str, ...]:
        """
        List selected cases without interpreting them as a fresh testing schedule.
        """
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as connection:
            _check(connection)
            return tuple(
                row[0]
                for row in connection.execute("SELECT identifier FROM cases ORDER BY identifier")
            )

    def export(self, identifier: str, destination: Path) -> None:
        """
        Write a new endpoint-only diagnostic document, refusing to overwrite any existing evidence.
        """
        record = self.load(identifier)
        document = inspection_document(identifier, record["recipe"], record["provenance"])
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(document, stream, sort_keys=True, allow_nan=False)
