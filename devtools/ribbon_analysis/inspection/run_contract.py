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

    def start(self, request: dict[str, Any], targets: Targets) -> None:
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
