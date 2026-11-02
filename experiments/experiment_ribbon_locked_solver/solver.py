"""
Run the selected deterministic joint construction and composite aesthetic second pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, process_time
from typing import Any, Callable

from devtools.ribbon_analysis.contracts import TargetPose, Targets
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.solve import construct
from experiments.experiment_ribbon_spline_guide.guide import Guide

from .cleanup import remove_slivers
from .coordinates import metadata
from .settings import VERSION, Settings
from .smoothing import smooth


@dataclass(frozen=True)
class Result:
    """
    Keep numerical acceptance distinct from unattempted native construction/fidelity.
    """

    route: FoldRoute | None
    first_pass: FoldRoute | None
    detail: dict[str, Any]
    material_uv: dict[str, Any] | None


def solve(
    source: TargetPose,
    settings: Settings,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    minimum_radius_mm: float | None = None,
) -> Result:
    """
    Construct from endpoint inputs only, then optionally ease with one shared length budget.

    No archived route, seed bank, historical fallback or native repair is used.
    The optional declared radius supports exact frozen regression inputs; it never
    lowers the physical99.6%pinch floor. Six rotation families and twelve first-pass
    contact attempts retain the selected finite construction bounds.
    Numerical slivers undergo bounded fixed-direction reclosure before final
    validation and optional coordinate metadata, independently of smoothing.
    """
    started, cpu_started = perf_counter(), process_time()
    targets = Targets.capture(source)
    radius = targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    if minimum_radius_mm is not None:
        declared = Boundary(targets, minimum_radius_mm)
        radius = max(radius, declared.radius_mm)
    boundary = Boundary(targets, radius)
    guide = Guide.create(targets)
    checkpoint()
    first_started = perf_counter()
    first, details = construct(
        boundary,
        guide,
        checkpoint,
        record,
        first_pass_optimization=settings.first_pass_optimization,
    )
    first_seconds = perf_counter() - first_started
    if first is None:
        return Result(
            None,
            None,
            {
                "version": VERSION,
                "status": "unresolved",
                "construction": details,
                "first_pass_seconds": first_seconds,
                "elapsed_seconds": perf_counter() - started,
                "cpu_seconds": process_time() - cpu_started,
            },
            None,
        )
    smoothing_started = perf_counter()
    final, stages = smooth(first, settings.smoothing_percent, checkpoint, record)
    smoothing_seconds = perf_counter() - smoothing_started
    cleanup_started = perf_counter()
    cleaned = remove_slivers(final, checkpoint)
    cleanup_seconds = perf_counter() - cleanup_started
    cleanup_detail = {
        "status": cleaned.status,
        "removed_lengths_mm": cleaned.removed_lengths_mm,
        "linear_projections": cleaned.projections,
    }
    if cleaned.removed_lengths_mm or cleaned.route is None:
        record(
            {
                "stage": "numerical_cleanup",
                **cleanup_detail,
                "route": snapshot(cleaned.route or final),
            }
        )
    if cleaned.route is None:
        return Result(
            None,
            first,
            {
                "version": VERSION,
                "status": "unresolved",
                "construction": details,
                "cleanup": cleanup_detail,
                "cleanup_seconds": cleanup_seconds,
                "first_pass_seconds": first_seconds,
                "smoothing_seconds": smoothing_seconds,
                "elapsed_seconds": perf_counter() - started,
                "cpu_seconds": process_time() - cpu_started,
            },
            None,
        )
    final = cleaned.route
    contact = inspect_contact(final, checkpoint=checkpoint)
    metric = material_error(final)
    if (
        contact.status != "separated"
        or cap_error(final) > 1e-7
        or metric > 1e-10
        or final.targets != targets
        or final.material_length_mm
        > first.material_length_mm * (1 + settings.smoothing_percent / 100)
        + 1e-8 * targets.diameter_mm
    ):
        raise ArithmeticError("Selected solver lost its numerical material/cap/contact contract")
    uv_started = perf_counter()
    material_uv = metadata(final) if settings.material_uv else None
    uv_seconds = perf_counter() - uv_started
    return Result(
        final,
        first,
        {
            "version": VERSION,
            "status": "numerically_accepted",
            "construction": details,
            "stages": stages,
            "cleanup": cleanup_detail,
            "cleanup_seconds": cleanup_seconds,
            "first_pass_seconds": first_seconds,
            "smoothing_seconds": smoothing_seconds,
            "material_uv_seconds": uv_seconds,
            "cap_error_mm": cap_error(final),
            "material_metric_error": metric,
            "contact": contact.status,
            "elapsed_seconds": perf_counter() - started,
            "cpu_seconds": process_time() - cpu_started,
            "native_construction": "unattempted",
            "native_fidelity": "unmeasured",
            "full_physical_audit": "unmeasured",
        },
        material_uv,
    )
