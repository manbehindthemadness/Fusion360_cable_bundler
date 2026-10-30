"""
Replay explicit solver dispositions and indexed search histories without solving.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..contracts import Targets
from ..gym.handoff import validate as validate_gym
from .archive import (
    RuleObservation,
    _integer,
    _number,
    _object,
    _text,
    _vector,
    canonical,
    parse_snapshot,
    read_document,
    snapshot_payload,
)
from .bends import inspect as inspect_bends
from .capture import load_history_path, read_history
from .geometry import PathSnapshot
from .measurements import observations
from .panels import witnesses
from .pinch_geometry import inspect as inspect_pinch
from .pinch_geometry import sample as sample_pinch
from .thickness import build as build_thickness

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
        self.gym = validate_gym(document.get("gym"), self.targets)
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
            source_rules = data.get("rules")
            if not isinstance(source_rules, list):
                raise ValueError("Every solver must explicitly report its rule observations.")
            rules = tuple(RuleObservation(**_object(rule)) for rule in source_rules)
            disabled = data.get("disabled_rules", [])
            if (
                not isinstance(disabled, list)
                or any(not isinstance(value, str) for value in disabled)
                or len(set(disabled)) != len(disabled)
            ):
                raise ValueError("Recorded disabled rules require unique text identifiers.")
            comparison = data.get("comparison")
            if comparison is not None:
                comparison = _object(comparison)
                if comparison.get("role") not in ("baseline", "ablation"):
                    raise ValueError("Unknown recorded comparison role.")
                for key in ("baseline", "origin"):
                    _text(comparison.get(key))
            metrics = _object(data.get("metrics", {}))
            settings = _object(data.get("settings", {}))
            if settings and data.get("procedure", identifier.rsplit(":", 1)[-1]) in (
                "ordinary",
                "redistribution",
                "tightening",
                "combined",
                "compatible",
                "discovery",
                "broad",
                "generalized",
            ):
                settings = dict(settings)
                settings.setdefault("bend_model", "legacy")
                settings.setdefault("pinch_percent", 99.6)
            canonical({"metrics": metrics, "settings": settings})
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
                    "procedure": _text(data["procedure"])
                    if data.get("procedure") is not None
                    else identifier.rsplit(":", 1)[-1]
                    if isinstance(data.get("settings"), dict) and identifier.startswith("run-")
                    else "",
                    "settings": settings,
                    "metrics": {
                        key: metrics[key]
                        for key in (
                            "coordinates",
                            "evaluations",
                            "score",
                            "seed_screenings",
                            "endpoint_gate_passed",
                            "strict_endpoint_gate",
                            "center_endpoint_error_mm",
                            "edge_position_error_mm",
                            "edge_tangent_error",
                            "terminal_width_error",
                            "procedure_completed",
                            "work",
                            "allocation",
                            "coordinate_scales",
                        )
                        if key in metrics
                    },
                    "disabled_rules": disabled,
                    "comparison": comparison,
                }
            )
        self.solver = self.methods[0]["id"]
        self.proposal = -1
        self.section = 0
        self.snapshot: PathSnapshot | None = None
        self._inspection_snapshot: PathSnapshot | None = None
        self._inspection_rules: list[dict[str, Any]] = []
        self._inspection_witnesses: list[dict[str, Any]] = []
        self._inspection_thickness: dict[str, Any] | None = None
        self._inspection_pinch: dict[str, Any] | None = None
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

    def import_results(self, manifest: Path) -> tuple[str, ...]:
        """
        Append immutable results for the same fixed targets without replacing history.
        """
        incoming = Session(manifest)
        if incoming.targets != self.targets:
            raise ValueError("Run results do not match this session's fixed endpoint inputs.")
        if canonical(incoming.gym) != canonical(self.gym):
            raise ValueError("Run results do not match this session's frozen gym layout.")
        identifiers = tuple(method["id"] for method in incoming.methods)
        existing = {method["id"] for method in self.methods}
        if existing.intersection(identifiers) or len(self.methods) + len(identifiers) > 64:
            raise ValueError("Run results would duplicate identities or exceed 64 method entries.")
        self.methods.extend(incoming.methods)
        self._snapshots.update(incoming._snapshots)
        self._histories.update(incoming._histories)
        return identifiers

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

    def baseline(self) -> PathSnapshot | None:
        """
        Return the recorded matched baseline only for a selected ablation result.
        """
        method = next(item for item in self.methods if item["id"] == self.solver)
        comparison = method["comparison"]
        if not isinstance(comparison, dict) or comparison.get("role") != "ablation":
            return None
        return self._snapshots.get(_text(comparison.get("baseline")))

    def comparison_state(self) -> dict[str, Any] | None:
        """
        Compare independent measurements without filtering out disabled constraints.
        """
        method = next(item for item in self.methods if item["id"] == self.solver)
        comparison = method["comparison"]
        if not isinstance(comparison, dict):
            return None
        baseline = next(
            (item for item in self.methods if item["id"] == comparison.get("baseline")), None
        )
        if baseline is None:
            return dict(
                comparison,
                measurements=[],
                detail="Baseline geometry unavailable after a stopped comparison.",
            )
        previous = {rule["name"]: rule for rule in baseline["rules"]}
        measurements = []
        for rule in method["rules"]:
            prior = _object(previous.get(rule["name"], {}))
            prior_value, current_value = prior.get("value"), rule["value"]
            if current_value is not None and prior_value is not None:
                baseline_number, current_number = _number(prior_value), _number(current_value)
                measurements.append(
                    {
                        "name": rule["name"],
                        "baseline": baseline_number,
                        "current": current_number,
                        "delta": current_number - baseline_number,
                    }
                )
        return dict(
            comparison,
            measurements=measurements,
            detail="Fresh runs use identical inputs, settings, initialization and source pins. Measurements retain the full reference rules. Baseline ghost is its recorded result; proposals are not matched iteration pairs.",
        )

    def state(self) -> dict[str, Any]:
        """
        Return finite palette data, including missing outcomes and proposal metadata.
        """
        records = self._histories.get(self.solver, (None, ()))[1]
        proposal = records[self.proposal] if self.proposal >= 0 else None
        snapshot = self.snapshot
        method = next(item for item in self.methods if item["id"] == self.solver)
        percent = (
            _number(method["settings"].get("pinch_percent", 99.6))
            if method["settings"].get("bend_model") == "pinch percent"
            else None
        )
        geometry_data, bend_data = None, None
        if isinstance(snapshot, PathSnapshot):
            frozen: PathSnapshot = snapshot
            if snapshot is not self._inspection_snapshot:
                self._inspection_pinch = (
                    inspect_pinch(frozen, self.section, percent) if percent is not None else None
                )
                self._inspection_rules = [
                    asdict(rule)
                    for rule in observations(
                        frozen,
                        self.targets,
                        3 * self.targets.diameter_mm,
                        pinch_percent=percent,
                        pinch_data=self._inspection_pinch,
                    )
                ]
                self._inspection_witnesses = [
                    asdict(overlay)
                    for overlay in witnesses(
                        frozen, self.targets, pinch_percent=percent, section=self.section
                    )
                ]
                self._inspection_thickness = asdict(build_thickness(frozen))
                self._inspection_snapshot = snapshot
            geometry_data = snapshot_payload(frozen)["geometry"]
            if percent is not None and self._inspection_pinch is not None:
                bend_data = dict(
                    self._inspection_pinch,
                    selected=sample_pinch(frozen, frozen.sections[self.section].u, percent),
                )
                self._inspection_witnesses = [
                    asdict(overlay)
                    for overlay in witnesses(
                        frozen, self.targets, pinch_percent=percent, section=self.section
                    )
                ]
            else:
                bend_data = inspect_bends(frozen, self.section)
        elif snapshot is not None:
            raise TypeError("Inspection selection must contain frozen geometry.")
        return {
            "case": self.targets.name,
            "gym": self.gym,
            "bend_policy": {
                "model": "pinch percent" if percent is not None else "legacy",
                "pinch_percent": percent,
            },
            "diameter_mm": self.targets.diameter_mm,
            "solvers": self.methods,
            "solver": self.solver,
            "proposal": self.proposal,
            "proposal_info": proposal,
            "comparison": self.comparison_state(),
            "rules": self._inspection_rules
            if snapshot is not None
            else next(method["rules"] for method in self.methods if method["id"] == self.solver),
            "section": self.section,
            "snapshot": geometry_data,
            "bends": bend_data,
            "witnesses": self._inspection_witnesses if snapshot is not None else [],
            "thickness": self._inspection_thickness if snapshot is not None else None,
            "notice": "Sampled frozen geometry inspection. Disabled search constraints remain measured. No continuous or overall physical acceptance is inferred.",
        }
