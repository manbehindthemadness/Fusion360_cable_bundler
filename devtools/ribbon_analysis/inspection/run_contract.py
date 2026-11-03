"""
Define an optional execution boundary without coupling replay to experimental solvers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..contracts import Targets


class ProcedureRunner(Protocol):
    """
    Own one bounded asynchronous numerical job and expose its archived results.
    """

    def open_example(self, identifier: str) -> Path:
        """
        Return a separately archived authored example, refusing active-job switches.
        """
        ...

    def register_layout(self, manifest: Path, label: str) -> str:
        """
        Register frozen endpoint inputs as a selectable case, refusing active jobs.
        """
        ...

    def inspect_layout(self, manifest: Path, label: str) -> Path:
        """
        Select finished-run input geometry without clearing its retained execution disposition.
        """
        ...

    def start(
        self, request: dict[str, Any], targets: Targets, *, gym: dict[str, Any] | None = None
    ) -> None:
        """
        Validate selections, freeze a plan and start an explicitly requested job.
        """
        ...

    def poll(self) -> Path | None:
        """
        Return a completed result manifest once, without blocking on numerical work.
        """
        ...

    def cancel(self) -> None:
        """
        Request a cooperative stop of this runner's numerical worker only.
        """
        ...

    def state(self) -> dict[str, Any]:
        """
        Return available procedures/settings and the latest job disposition.
        """
        ...


class TesterControls(Protocol):
    """
    Expose optional owned range testing without coupling replay to its scheduler.
    """

    @property
    def active(self) -> bool:
        """
        Report whether manual layout/run controls must remain locked.
        """
        ...

    def dispatch(self, action: str, data: dict[str, Any]) -> None:
        """
        Apply an explicit tester start, poll, stop or inspection request.
        """
        ...

    def state(self) -> dict[str, Any]:
        """
        Return bounded form, progress and log-location data.
        """
        ...
