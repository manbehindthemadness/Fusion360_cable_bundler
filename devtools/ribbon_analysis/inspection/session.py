"""
Replay explicit solver dispositions and indexed search histories without solving.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..contracts import Targets
from .archive import (
    RuleObservation,
    _integer,
    _number,
    _object,
    _text,
    _vector,
    parse_snapshot,
    read_document,
    snapshot_payload,
)
from .capture import load_history_path, read_history
from .geometry import PathSnapshot

STATUSES = ("reference", "recorded", "unresolved", "stopped", "not_run", "invalidated")


class Session:
    """
    Keep solver identity, proposal selection and section selection in explicit order.

    A missing result remains selectable with its disposition. Histories load one
    snapshot at a time, and archive paths cannot escape the manifest directory.
    """

    def __init__(self, manifest: Path) -> None:
        """
        Validate the entire manifest before exposing any geometry to a viewer.
        """
        self.manifest = manifest.resolve()
        document = read_document(manifest)
        target = _object(document.get("targets"))
        name = target.get("name")
        if not isinstance(name, str):
            raise ValueError("Inspection targets need a name.")
        self.targets = Targets.capture(
            Targets(
                name,
                *(
                    _vector(target.get(k))
                    for k in (
                        "start",
                        "end",
                        "start_tangent",
                        "end_tangent",
                        "start_width",
                        "end_width",
                    )
                ),
                _integer(target.get("lines")),
                _number(target.get("diameter_mm")),
            )
        )
        methods = document.get("solvers")
        if not isinstance(methods, list) or not 1 <= len(methods) <= 64:
            raise ValueError("Inspection needs an explicit bounded solver inventory.")
        self.methods: list[dict[str, Any]] = []
        self._snapshots: dict[str, PathSnapshot] = {}
        self._histories: dict[str, tuple[Path, tuple[dict[str, Any], ...]]] = {}
        for item in methods:
            data = _object(item)
            identifier, label, detail, source = (
                _text(data.get(k)) for k in ("id", "label", "detail", "source")
            )
            if any(
                not isinstance(v, str) or not v.strip() for v in (identifier, label, detail, source)
            ):
                raise ValueError(
                    "Every solver needs identity, label, provenance and disposition detail."
                )
            if identifier in {m["id"] for m in self.methods} or data.get("status") not in STATUSES:
                raise ValueError("Solver identities must be unique with known dispositions.")
            observations = data.get("rules")
            if not isinstance(observations, list):
                raise ValueError("Every solver must explicitly report its rule observations.")
            rules = tuple(RuleObservation(**_object(rule)) for rule in observations)
            if data.get("snapshot") is not None:
                snapshot = parse_snapshot(data["snapshot"])
                if (snapshot.lines, snapshot.diameter_mm) != (
                    self.targets.lines,
                    self.targets.diameter_mm,
                ):
                    raise ValueError("Solver snapshot dimensions disagree with the frozen case.")
                self._snapshots[identifier] = snapshot
            history = data.get("history")
            history_count = 0
            if history is not None:
                if not isinstance(history, str) or not history.strip():
                    raise ValueError("History path must be nonempty text.")
                location = (self.manifest.parent / history).resolve()
                if self.manifest.parent not in location.parents:
                    raise ValueError("History path must remain inside its archive directory.")
                records = read_history(location, allow_interrupted_tail=True)
                self._histories[identifier] = (location, records)
                history_count = len(records)
            self.methods.append(
                {
                    "id": identifier,
                    "label": label,
                    "status": data["status"],
                    "detail": detail,
                    "source": source,
                    "rules": [asdict(rule) for rule in rules],
                    "history_count": history_count,
                    "has_result": identifier in self._snapshots,
                }
            )
        self.solver = self.methods[0]["id"]
        self.proposal = -1
        self.section = 0
        self.snapshot: PathSnapshot | None = None
        self.select(self.solver)

    def select(self, solver: str, proposal: int = -1) -> None:
        """
        Select a declared final/reference result or one indexed search proposal.
        """
        if solver not in {method["id"] for method in self.methods}:
            raise ValueError("Unknown inspection solver.")
        if isinstance(proposal, bool) or not isinstance(proposal, int) or proposal < -1:
            raise ValueError("Proposal index must be an integer or -1 for the result.")
        snapshot = self._snapshots.get(solver)
        if proposal >= 0:
            if solver not in self._histories or proposal >= len(self._histories[solver][1]):
                raise ValueError("Search proposal is outside the recorded history.")
            path, records = self._histories[solver]
            snapshot = load_history_path(path, records[proposal])
            if (snapshot.lines, snapshot.diameter_mm) != (
                self.targets.lines,
                self.targets.diameter_mm,
            ):
                raise ValueError("Search dimensions disagree with the frozen case.")
        self.solver, self.proposal, self.section, self.snapshot = solver, proposal, 0, snapshot

    def select_section(self, index: int) -> None:
        """
        Move the same local XYZ basis to a distinct ordered recorded section.
        """
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or self.snapshot is None
            or not 0 <= index < len(self.snapshot.sections)
        ):
            raise ValueError("Section index is outside the selected geometry.")
        self.section = index

    def state(self) -> dict[str, Any]:
        """
        Return finite palette data, including missing outcomes and proposal metadata.
        """
        records = self._histories.get(self.solver, (None, ()))[1]
        proposal = records[self.proposal] if self.proposal >= 0 else None
        return {
            "case": self.targets.name,
            "diameter_mm": self.targets.diameter_mm,
            "solvers": self.methods,
            "solver": self.solver,
            "proposal": self.proposal,
            "proposal_info": proposal,
            "section": self.section,
            "snapshot": snapshot_payload(self.snapshot)["geometry"]
            if self.snapshot is not None
            else None,
            "notice": "Diagnostic geometry. Search proposals are unaudited. No overall physical acceptance is inferred.",
        }
