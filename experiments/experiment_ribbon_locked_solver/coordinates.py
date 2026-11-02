"""
Retain optional continuous material coordinates independently of Fusion texture creation.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_optional_appearance.material import material_coordinates
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.material_profile import material_profile


def coordinates(
    route: FoldRoute, piece_index: int, region: str, point: Vector3
) -> tuple[float, float, float]:
    """
    Return global normalized longitudinal/transverse coordinates and physical thickness.

    U follows corresponding material distance from the fixed start, across piece
    seams. V follows ordered material width. These are application material
    coordinates, not writable replacements for Fusion's native per-face charts.
    """
    if (
        isinstance(piece_index, bool)
        or not isinstance(piece_index, int)
        or not 0 <= piece_index < len(route.pieces)
    ):
        raise ValueError("Choose an existing material piece")
    if region not in {"straight", "before", "bend", "after"}:
        raise ValueError("Choose a declared material surface region")
    s, q, b = material_coordinates(route.pieces[piece_index], region, point)
    return (
        (route.starts_mm[piece_index] + s) / route.material_length_mm,
        (q + route.half_width_mm) / (2 * route.half_width_mm),
        b,
    )


def metadata(route: FoldRoute) -> dict[str, Any]:
    """
    Serialize enough exact geometry and profile identity for later appearance work.

    Continuous s/q/b maps can be reconstructed with no texture files. Actual
    renderer UVs remain face-specific; a later optional appearance bake uses the
    verified physical inverse. Endcaps retain the accepted separate mapping scope.
    """
    return {
        "schema": "ribbon-material-coordinates-v1",
        "units": "millimeters",
        "uv": "U=s/total_length; V=(q+half_width)/(2*half_width); b retains thickness",
        "native_renderer_uv": "Read-only per-face chart; optional later appearance baking",
        "endcaps": "Separate mapping; accepted mismatch to longitudinal side texture",
        "profile_order": "negative q to positive q; no conductor relabeling",
        "profile": [
            asdict(arc) for arc in material_profile(route.targets.lines, route.targets.diameter_mm)
        ],
        "material_starts_mm": route.starts_mm,
        "route": snapshot(route),
    }
