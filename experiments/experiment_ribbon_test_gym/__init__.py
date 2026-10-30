"""
Launch the endpoint-only Rubik gym preview in an explicitly owned Fusion component.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from devtools.ribbon_analysis.gym import Config, generate
from devtools.ribbon_analysis.inspection.archive import write_document
from experiments.experiment_ribbon_diagnostic_viewer.procedures import source_pins


def launch(component: Any, directory: Path, config: Config | None = None) -> Any:
    """
    Freeze a visual-only scope and return the retained viewer; Fusion must be idle.

    Requires Fusion's supplied adsk runtime and an explicitly owned component.
    No numerical search, native cable construction or new routing rules run.
    Callers keep this returned object alive for the palette event handlers.
    """
    from devtools.ribbon_analysis.gym.view import GymView

    if directory.exists():
        raise ValueError("Choose a new preview directory; old layouts must remain replayable.")
    directory.parent.mkdir(parents=True, exist_ok=True)
    write_document(
        directory.parent / (directory.name + "-plan.json"),
        {
            "scope": "Visual endpoint gym only: empty central cube >=3nominal cable widths,26outer zones,two virtual axis-aligned goal boxes and selectable faces. No path-first fixture, solver, routing rule or planar gym.",
            "sources": source_pins(),
            "seconds_per_edit": 10,
            "rss_kib": 4194304,
            "launch_rss_kib": 3984588,
            "numerical_runs": 0,
            "native_cable_attempts": 0,
        },
    )
    view = GymView(component, directory, generate(config))
    view.show()
    return view
