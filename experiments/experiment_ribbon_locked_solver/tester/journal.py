"""
Retain every tester input and disposition while keeping only current-case state in memory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from devtools.ribbon_analysis.gym.scene import Scene
from devtools.ribbon_analysis.inspection.archive import canonical, write_document


class Journal:
    """
    Own one write-once plan, append-only case ledger and replaceable reconnect status.
    """

    def __init__(self, directory: Path, plan: dict[str, Any]) -> None:
        """
        Require a new owned run directory before any drawing or solver launch.
        """
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        write_document(directory / "plan.json", plan)

    def begin(self, index: int, scene: Scene) -> Path:
        """
        Freeze the complete selected gym before passing it to the ordinary controller.
        """
        path = self.directory / f"case-{index + 1:06d}.json"
        write_document(path, {"index": index, "gym": scene.payload()})
        self.append({"event": "case_prepared", "index": index, "input": str(path)})
        return path

    def append(self, entry: dict[str, Any]) -> None:
        """
        Flush each case boundary independently so interruption retains the last known stage.
        """
        with (self.directory / "cases.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(canonical(entry) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def status(self, state: dict[str, Any]) -> None:
        """
        Atomically update a generated status file without replacing immutable case evidence.
        """
        temporary = self.directory / "status.tmp"
        temporary.write_text(json.dumps(state, allow_nan=False, indent=2), encoding="utf-8")
        temporary.replace(self.directory / "status.json")


def problem(state: dict[str, Any], stop_on_warnings: bool) -> str | None:
    """
    Require completed native fidelity and resolved contact, optionally stopping on precision warnings.
    """
    status = state.get("status")
    if status not in ("completed", "completed_with_warning"):
        label = status if isinstance(status, str) else "missing"
        return str(state.get("detail") or f"Case ended with status {label}.")
    native = state.get("native")
    if not isinstance(native, dict) or native.get("status") not in (
        "built_and_named_fidelity_checks_pass",
        "built_with_precision_warning",
    ):
        return "Case has no completed native build and fidelity result."
    job = state.get("job")
    if not isinstance(job, str) or not job:
        return "Completed case has no recorded job directory."
    path = Path(job) / "numerical-result.json"
    if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        return "Completed case has no bounded numerical result record."
    numerical = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(numerical, dict) or numerical.get("contact") != "separated":
        return "Contact is unresolved or unmeasured; tester stopped for inspection."
    if stop_on_warnings and (
        status == "completed_with_warning" or native.get("status") == "built_with_precision_warning"
    ):
        return "Native accuracy warning; tester stopped for inspection."
    return None
