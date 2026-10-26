"""
Screen a frozen nine-policy edge-shape grid,then display one ranked path per pose.

All outcomes remain in memory. Rankings select diagnostics,not generalized
successes;three cached controls remain visible and are never relabeled as new.
"""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from pathlib import Path
from time import perf_counter, process_time
from typing import Any, cast
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from . import edge_shapes_native
from .edge_display import draw
from .edge_first import EdgeCandidate, construct
from .event_cases import cases
from .native_budget import NativeBudget, resident_kib

NAME = "Edge speed-curvature grid - selected paths40-44"
OLD_EDGE_HASH = "00df33fa4cac4e39b6c7bdf200a23ca4c7183c22dcdbf31301e577a5a666d0cb"
EDGE_PATH = "experiments/experiment_ribbon_cap_transition/edge_first.py"
SPEEDS = (1.5, 2.0, 2.5)
RATIOS = (0.2, 0.4, 0.6)
_state: dict[str, Any] | None = None
_candidates: list[EdgeCandidate] = []


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Freeze previous sources plus this bounded shape-grid adapter.
    """
    path = Path(__file__)
    inherited = edge_shapes_native._sources()
    relative_path = str(path.relative_to(PROJECT_ROOT))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {**inherited, relative_path: digest}


def _rank(candidate: EdgeCandidate) -> tuple[bool, float]:
    """
    Prefer all-gate compatibility,then larger sampled material-coordinate margin.

    Stable input ordering breaks ties. This ranking is declared before the grid
    runs and never changes a failed result into a passing one.
    """
    return candidate.companion_allowed, float(
        candidate.metrics.get("minimum_sampled_material_jacobian", -math.inf)
    )


def _rank_index(index: int) -> tuple[bool, float]:
    """
    Rank a retained candidate index with explicit integer indexing.
    """
    return _rank(_candidates[index])


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Evaluate45new spatial shapes and draw five diagnostics within fixed limits.

    The same8development configurations include5spatial inputs and3cached controls;
    policy variants add no independent case coverage. Use257stations per shape,
    no solids/retries. This grid is a diagnostic search,not the final single-pass
    algorithm. Limits are10s math/30s draw/60s total/2GiB sampledRSS;stop first
    source,harness/API or resource failure.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Edge speed grid already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned scratch.")
    root = design.rootComponent
    if (
        root.occurrences.count != 4
        or root.occurrences.item(3).component.name != edge_shapes_native.NAME
    ):
        raise RuntimeError("Expected retained fixed-curvature comparison.")
    baseline = edge_shapes_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Complete fixed-curvature baseline unavailable.")
    if baseline["plan"]["sources"].get(EDGE_PATH) != OLD_EDGE_HASH:
        raise RuntimeError("Unexpected prior edge implementation.")
    sources = _sources()
    if any(
        sources.get(p) != digest
        for p, digest in baseline["plan"]["sources"].items()
        if p != EDGE_PATH
    ):
        raise RuntimeError("Unreviewed source drift.")
    inputs = cases()
    spatial = [case for i, case in enumerate(inputs) if i not in (2, 3, 7)]
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "direct-edge-speed-curvature-grid-v1",
            "hypothesis": "More endpoint departure/arrival travel permits stronger distributed spatial bending without moving A targets;test whether any fixed shape policy supports the full width.",
            "inputs": deepcopy(baseline["plan"]["inputs"]),
            "sources": sources,
            "baseline_rows": deepcopy(baseline["rows"]),
            "profiles": [(speed, ratio) for speed in SPEEDS for ratio in RATIOS],
            "procedure": "Five spatial cases x9fixed profiles,45constructions. Endpoint speed=D*speedratio,curvature=ratio/reach,acceleration=speed^2*k*N,jerk=-speed^3*k^2*T. Same arrival/compatibility gates. Select5displays by all-gates-allowed then maxminimumJacobian,stable profile order. Record all failed,undrawn and selected candidates.",
            "reviewed_change": "Only edge_first speed-ratio parameter and additional Jacobian-location/slope metrics;default geometry and acceptance unchanged.",
            "limits": "45shape evaluations/5spatial inputs+3cached controls,257stations/shape,no retries/solids,5native path displays,10s math/30s draw/60s total/2GiB sampledRSS",
            "scope": "8examined development configurations,no holdouts/invalid controls. A-side permanent,no event handoffs. Not final single-pass solver;native physical compliance unmeasured.",
        },
        "controls": deepcopy(baseline["controls"]),
        "rows": [
            {
                "case": case.name,
                "speed": speed,
                "ratio": ratio,
                "evaluated": False,
                "drawn": False,
                "overall": "unattempted",
            }
            for case in spatial
            for speed in SPEEDS
            for ratio in RATIOS
        ],
        "stop_reason": None,
    }
    _state = state
    try:
        numerical_started = perf_counter()
        for row in state["rows"]:
            budget.check("shape_" + row["case"])
            if perf_counter() - numerical_started >= 10 or _sources() != sources:
                raise RuntimeError("Numerical budget/source gate.")
            case = next(c for c in spatial if c.name == row["case"])
            started = perf_counter()
            candidate = construct(case, endpoint_ratio=row["ratio"], speed_ratio=row["speed"])
            _candidates.append(candidate)
            row.update(
                candidate.metrics,
                evaluated=True,
                solve_and_audit_seconds=perf_counter() - started,
                companion_allowed=candidate.companion_allowed,
                overall="unresolved" if candidate.companion_allowed else "failed",
            )
        state["numerical_seconds"] = perf_counter() - numerical_started
        if state["numerical_seconds"] >= 10:
            raise RuntimeError("Numerical budget exceeded.")
        selected = [
            max(
                (i for i, c in enumerate(_candidates) if c.case.name == case.name),
                key=_rank_index,
            )
            for case in spatial
        ]
        state["selected_indices"] = selected
        display_started = perf_counter()
        pitch = float(baseline["display_pitch_cm"])
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(0, -12 * pitch, 0)
        parent = root.occurrences.addNewComponent(matrix).component
        parent.name = NAME
        for slot, index in enumerate(selected):
            budget.check("draw_" + str(slot + 40))
            if perf_counter() - display_started >= 30 or _sources() != sources:
                raise RuntimeError("Drawing budget/source gate.")
            candidate, row = _candidates[index], state["rows"][index]
            started = perf_counter()
            placement = adsk.core.Matrix3D.create()
            placement.translation = adsk.core.Vector3D.create(slot * pitch, 0, 0)
            component = parent.occurrences.addNewComponent(placement).component
            component.name = f"{slot + 40:02d} - speed{row['speed']} ratio{row['ratio']} - {candidate.case.name} - {row['overall']}"
            draw(component, candidate, slot + 40)
            row.update(drawn=True, number=slot + 40, draw_seconds=perf_counter() - started)
        state["drawing_seconds"] = perf_counter() - display_started
        if state["drawing_seconds"] >= 30:
            raise RuntimeError("Drawing budget exceeded.")
        app.activeViewport.fit()
        app.activeViewport.refresh()
        budget.check("archive")
        started = perf_counter()
        directory = (
            PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/edge_speed" / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Edge speed grid image export failed.")
        state.update(
            directory=str(directory),
            display_pitch_cm=pitch,
            archive_seconds=perf_counter() - started,
        )
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state.update(
        overall_seconds=perf_counter() - budget.started,
        cpu_seconds=process_time() - cpu_started,
        maximum_sampled_rss_kib=max(cast(int, s["rss_kib"]) for s in budget.samples),
        final_rss_kib=resident_kib(),
    )
    return state
