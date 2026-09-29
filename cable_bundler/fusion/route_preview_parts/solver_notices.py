"""
Format route-solve warnings for the Fusion palette.
"""

from __future__ import annotations

from typing import Optional

from ...routing import RouteCollision, TransitionAdjustment


def _adjustment_notice(adjustment: TransitionAdjustment) -> str:
    """
    Format a dynamic transition correction for the palette event console.
    """
    if adjustment.applied_bend_radius_mm is not None:
        return (
            f"Warning — Cable {adjustment.cable_number}: clamped transitions between profiles "
            f"{adjustment.start_profile} and {adjustment.end_profile} from "
            f"{adjustment.required_mm:.3f} mm to {adjustment.applied_mm:.3f} mm; "
            f"the {adjustment.minimum_bend_radius_mm:.3f} mm minimum sweep radius was "
            f"sacrificed (achieved {adjustment.applied_bend_radius_mm:.3f} mm). "
            "Fusion may reject the resulting solid."
        )
    return (
        f"Cable {adjustment.cable_number}: dynamically adjusted transitions between profiles "
        f"{adjustment.start_profile} and {adjustment.end_profile} from "
        f"{adjustment.required_mm:.3f} mm to {adjustment.applied_mm:.3f} mm; "
        f"the {adjustment.minimum_bend_radius_mm:.3f} mm sweep radius is preserved."
    )


def _straight_route_notice(cable_number: str, error: ValueError) -> str:
    """
    Explain when only an ordered straight-segment preview could be retained.
    """
    return (
        f"Warning — Cable {cable_number}: showing straight segments through the ordered "
        f"crossings because curved fairing failed ({error}). Profile tangents and bend "
        "clearance are not preserved; Fusion may reject the resulting solid."
    )


def _adjustment_below_cable_radius(
    adjustments: list[TransitionAdjustment], cable_radius_mm: float
) -> Optional[TransitionAdjustment]:
    """
    Find a clamped span whose local curvature would invert a circular sweep.
    """
    return next(
        (
            adjustment
            for adjustment in adjustments
            if adjustment.applied_bend_radius_mm is not None
            and adjustment.applied_bend_radius_mm <= cable_radius_mm + 1e-9
        ),
        None,
    )


def _straight_for_sweep_notice(
    cable_number: str, adjustment: TransitionAdjustment, diameter_mm: float
) -> str:
    """
    Explain a whole-leg straight fallback chosen to avoid a self-inverting sweep.
    """
    return (
        f"Warning — Cable {cable_number}: the clamped bend between profiles "
        f"{adjustment.start_profile} and {adjustment.end_profile} reached "
        f"{adjustment.applied_bend_radius_mm:.3f} mm, below the cable radius "
        f"{diameter_mm / 2.0:.3f} mm. Showing straight segments through the ordered "
        "crossings for the solid sweep; profile tangents and bend clearance are not preserved."
    )


def _collision_notice(collision: RouteCollision) -> str:
    """
    Format one residual member collision for the event console.
    """
    return (
        f"{collision.left_label} and {collision.right_label} remain "
        f"{collision.clearance_shortfall_mm:.3f} mm inside the requested separation; "
        "the original deterministic route is retained."
    )
