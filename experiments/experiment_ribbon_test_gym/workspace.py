"""
Connect the optional endpoint gym to a retained diagnostic viewer in one owned design.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from devtools.ribbon_analysis.gym import Scene
from devtools.ribbon_analysis.gym.handoff import freeze, identity
from devtools.ribbon_analysis.gym.view import GymView
from devtools.ribbon_analysis.inspection.archive import write_document
from devtools.ribbon_analysis.inspection.fusion_view import DiagnosticViewer
from experiments.experiment_ribbon_diagnostic_viewer.procedures import source_pins


class Workspace:
    """
    Keep a mutable gym draft separate from immutable diagnostic cases and their histories.

    The caller retains this owner and supplies an existing diagnostic viewer and
    sibling occurrences owned exclusively by these viewers. No numerical job starts
    during layout generation or handoff; Run selected remains explicit.
    """

    def __init__(
        self,
        diagnostics: DiagnosticViewer,
        diagnostic_occurrence: Any,
        gym_occurrence: Any,
        directory: Path,
        scene: Scene | None = None,
    ) -> None:
        """
        Connect two palettes without replacing the diagnostic viewer's existing sessions.
        """
        if diagnostics.runner is None:
            raise ValueError("The diagnostic viewer needs a numerical controller.")
        if diagnostics.runner.state()["status"] in ("running", "cancelling"):
            raise ValueError("Stop and collect the active job before connecting a gym.")
        if diagnostic_occurrence.component != diagnostics.root:
            raise ValueError("Supply the occurrence belonging to this diagnostic viewer.")
        self.diagnostics = diagnostics
        self.diagnostic_occurrence, self.gym_occurrence = diagnostic_occurrence, gym_occurrence
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=False)
        write_document(
            directory / "workspace-plan.json",
            {
                "sources": source_pins(),
                "scope": "Optional endpoint-only gym handoff and frozen visual context. No route fixture or new physical rules. Numerical runs require Run selected and their own frozen worker plans.",
                "seconds_per_edit": 10,
                "rss_kib": 4194304,
                "launch_rss_kib": 3984588,
                "automatic_numerical_runs": 0,
                "native_cable_attempts": 0,
            },
        )
        self.gym = GymView(
            gym_occurrence.component, directory / "draft", scene, self.open_diagnostics
        )
        diagnostics.enable_gym(self.open_gym)

    def open_gym(self) -> None:
        """
        Show the retained draft; frozen diagnostic cases remain unchanged.
        """
        if self.gym.palette is None:
            self.gym.show()
        self.diagnostic_occurrence.isLightBulbOn = False
        self.gym_occurrence.isLightBulbOn = True
        self.diagnostics.palette.isVisible = False
        self.gym.palette.isVisible = True

    def open_diagnostics(self, scene: Scene) -> None:
        """
        Freeze and select the draft as inputs; show existing results on repeated handoffs.
        """
        manifest = freeze(scene, self.directory / "layouts")
        self.diagnostics.open_layout(
            manifest, f"Gym · seed {scene.config.seed} · {identity(scene.payload())[4:12]}"
        )
        self.gym_occurrence.isLightBulbOn = False
        self.diagnostic_occurrence.isLightBulbOn = True
        self.gym.palette.isVisible = False
        self.diagnostics.palette.isVisible = True
