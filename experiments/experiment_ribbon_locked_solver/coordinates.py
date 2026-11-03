"""
Retain optional continuous material coordinates independently of Fusion texture creation.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, difference, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
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


def coordinates_for_face(
    route: FoldRoute, record: dict[str, Any], point: Vector3
) -> tuple[float, float, float]:
    """
    Recover continuous material coordinates when one native face covers several regions.

    Evaluate only explicitly retained source regions, rejecting out-of-region
    inverses. The smallest forward reconstruction residual chooses the physical
    source; near a shared material cap either inverse gives the same global U.
    Endcaps keep their separate mapping. No renderer chart or texture is created.
    """
    if not isinstance(record, dict):
        raise ValueError("Native material face record must be an object")
    sources = record.get("sources", [record])
    if not isinstance(sources, list) or not sources:
        raise ValueError("Native material face needs retained source regions")
    candidates = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("A material source region must be an object")
        index, region = source.get("piece_index"), source.get("region")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(route.pieces)
        ):
            continue
        if not isinstance(region, str) or region not in {"straight", "before", "bend", "after"}:
            continue
        piece = route.pieces[index]
        if (isinstance(piece.geometry, CylindricalFold) and region == "straight") or (
            not isinstance(piece.geometry, CylindricalFold) and region != "straight"
        ):
            continue
        s, q, b = material_coordinates(piece, region, point)
        length = piece.geometry.material_length_mm
        if not -1e-6 <= s <= length + 1e-6 or abs(q) > route.half_width_mm + 1e-6:
            continue
        u = min(1.0, max(0.0, s / length))
        q = min(route.half_width_mm, max(-route.half_width_mm, q))
        if isinstance(piece.geometry, CylindricalFold):
            entry, exit_fraction = piece.geometry.bend_interval(q)
            margin = 1e-6 / length
            if (
                region == "straight"
                or (region == "before" and u > entry + margin)
                or (region == "after" and u < exit_fraction - margin)
                or (region == "bend" and not entry - margin <= u <= exit_fraction + margin)
            ):
                continue
        elif region != "straight":
            continue
        position, velocity, across, _ = piece.surface(u, q)
        reconstructed = position.translated(unit(cross(velocity, across)), b)
        error = magnitude(difference(reconstructed, point))
        if error <= 1e-6:
            candidates.append(
                (
                    error,
                    (route.starts_mm[index] + u * length) / route.material_length_mm,
                    (q + route.half_width_mm) / (2 * route.half_width_mm),
                    b,
                )
            )
    if not candidates:
        raise ValueError("Point is outside the retained native material face regions")
    _, u, v, b = min(candidates)
    return u, v, b
