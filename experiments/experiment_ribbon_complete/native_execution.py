"""
Translate one prepared trunk and every ending under a single caller native allocation.

Bodies are transient and individually capped. No union, document persistence,
junction healing or physical-acceptance transfer occurs. A shared material interface
still needs its independent correspondence and flow measurements.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .contracts import IncompleteRibbonInput
from .execution import RibbonPlan
from .native_branch_body import NativeBranchBody
from .native_branch_body import build as build_branch


@dataclass(frozen=True)
class NativeTrunkBody:
    """
    Bind one transient body to its unchanged material route and native diagnostics.
    """

    source: FoldRoute
    body: Any
    outcome_info: tuple[str, ...]


def build_trunk(route: FoldRoute, checkpoint: Callable[[], None]) -> NativeTrunkBody:
    """
    Use the existing conditioned analytic-flat builder exactly once without persistence.

    Preserve the selected constructor's 1024 scale and return to physical size
    before checking positive volume. Encoding accuracy uses the current inclusive
    0.01mm policy. No fallback scale, healing or kernel retry is introduced.
    """
    checkpoint()
    # noinspection PyUnresolvedReferences
    import adsk.core

    # noinspection PyUnresolvedReferences
    import adsk.fusion

    from experiments.experiment_ribbon_fold_route.material_native import (
        circular_flat_surface,
        define_material_body,
    )
    from experiments.experiment_ribbon_fold_route.material_profile import material_profile
    from experiments.experiment_ribbon_fold_route.material_scale import NativeScale, construction
    from experiments.experiment_ribbon_fold_route.material_surfaces import (
        MaterialPatch,
        material_patches,
    )

    profile = material_profile(route.targets.lines, route.targets.diameter_mm)
    patches = material_patches(route.pieces, profile)
    if not patches or any(not 0 <= patch.error_bound_mm <= 0.01 for patch in patches):
        raise ValueError("Complete trunk representation exceeds0.01mm")
    inputs = construction(route.pieces, patches, NativeScale.CONDITIONED, checkpoint)

    def surface(patch: MaterialPatch) -> Any:
        """
        Preserve the original analytic flat support and unchanged bend parametrization.
        """
        checkpoint()
        return circular_flat_surface(inputs.pieces[patch.piece_index], patch)

    authored = define_material_body(
        inputs.pieces, inputs.patches, checkpoint, surface_factory=surface
    )
    checkpoint()
    body = authored.definition.createBody()
    outcome = tuple(authored.definition.outcomeInfo)
    if body is None:
        raise RuntimeError(f"Complete native trunk construction failed: {outcome}")
    checkpoint()
    transform = adsk.core.Matrix3D.create()
    for index in range(3):
        if not transform.setCell(index, index, 1 / NativeScale.CONDITIONED.factor):
            raise RuntimeError("Native inverse construction scale matrix rejected")
    if not adsk.fusion.TemporaryBRepManager.get().transform(body, transform):
        raise RuntimeError("Native inverse construction scale rejected")
    checkpoint()
    if not body.isSolid or body.volume <= 0:
        raise RuntimeError("Complete native trunk requires a positive closed solid")
    return NativeTrunkBody(route, body, outcome)


def iter_bodies(
    plan: RibbonPlan,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Iterator[NativeTrunkBody | NativeBranchBody]:
    """
    Yield the trunk once and all original branches, preserving the prefix on a stop.

    Refuse incomplete plans before any SDK work. Each yielded part owns the exact
    prepared route/branch object; no new candidate is calculated during construction.
    Native times include translation, definition and the kernel, excluding the
    caller's ownership, development audits, display and recording overhead.
    """
    checkpoint()
    if plan.trunk.route is None or plan.unattempted_route_ids:
        raise IncompleteRibbonInput("Native execution requires the trunk and every prepared ending")
    if (
        len(plan.branches) != len(plan.captured.branches)
        or any(p.source is not b for p, b in zip(plan.branches, plan.captured.branches))
        or plan.trunk.route.targets != plan.captured.trunk
    ):
        raise IncompleteRibbonInput(
            "Native execution must preserve complete plan identity and order"
        )
    started = perf_counter()
    trunk = build_trunk(plan.trunk.route, checkpoint)
    record({"stage": "native_complete_trunk", "wall_seconds": perf_counter() - started})
    yield trunk
    for branch in plan.branches:
        checkpoint()
        started = perf_counter()
        native = build_branch(branch, checkpoint)
        if not native.body.isSolid or native.body.volume <= 0:
            raise RuntimeError("A complete ending requires a positive closed solid")
        record(
            {
                "stage": "native_complete_branch",
                "route_id": str(branch.source.source.leg.route_id),
                "wall_seconds": perf_counter() - started,
            }
        )
        yield native
