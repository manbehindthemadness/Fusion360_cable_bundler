"""
Accept only shorter, closed, contact-separated fixed-fold material routes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import magnitude
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight

from .linear import shortening_direction


@dataclass(frozen=True)
class Trial:
    """
    Retain every proposed length change and its acceptance evidence.
    """

    iteration: int
    backtrack: int
    route: FoldRoute
    contact: ContactResult
    accepted: bool
    gain_mm: float


def cap_error(route: FoldRoute) -> float:
    """
    Check both ordered side lanes and the center against unchanged target frames.
    """
    from cable_bundler.routing.geometry import difference, unit

    target = route.targets
    errors = []
    for u, origin, tangent, width in (
        (0.0, target.start, target.start_tangent, target.start_width),
        (1.0, target.end, target.end_tangent, target.end_width),
    ):
        for q in (-route.half_width_mm, 0.0, route.half_width_mm):
            point, velocity, across, _ = route.surface(u, q)
            errors.extend(
                (
                    magnitude(difference(point, origin.translated(width, q))),
                    magnitude(difference(unit(velocity), tangent)),
                    magnitude(difference(across, width)),
                )
            )
    return max(errors)


def reposition(route: FoldRoute, lengths: tuple[float, ...]) -> FoldRoute:
    """
    Recompose immutable folds and replacement straight lengths from the fixed cap.
    """
    expected = sum(isinstance(piece.geometry, Straight) for piece in route.pieces)
    if len(lengths) != expected:
        raise ValueError("Supply one positive length per existing straight.")
    values = iter(lengths)
    pose = Pose(route.targets.start, route.targets.start_tangent, route.targets.start_width)
    pieces = []
    for original in route.pieces:
        geometry = original.geometry
        if isinstance(geometry, Straight):
            geometry = Straight(next(values))
        piece = PlacedPiece(pose, geometry, original.label)
        pieces.append(piece)
        pose = piece.end_pose()
    return FoldRoute(route.targets, tuple(pieces), route.radius_mm)


def contract(
    route: FoldRoute,
    *,
    maximum_iterations: int = 4,
    maximum_backtracks: int = 8,
    checkpoint: Callable[[], None] | None = None,
    record: Callable[[Trial], None] | None = None,
) -> tuple[FoldRoute, str]:
    """
    Shorten straight runs in a fixed topology using deterministic feasible descent.

    Existing fold objects, their order, angles, banks, leads and radii never change.
    A positive1e-7D straight floor is a declared numerical representation bound,
    not a physical minimum. Full steps hit this floor; rejected contact steps are
    halved at most eight times per iteration. Contact need not vary monotonically.
    No accepted candidate may worsen length or exceed the existing1e-7cap check.
    The caller must establish the initial route's physical/contact acceptance.
    Return a stopping reason rather than claiming a global or contact optimum.
    """
    if not 1 <= maximum_iterations <= 4 or not 1 <= maximum_backtracks <= 8:
        raise ValueError("Use at most four iterations and eight backtracks.")
    if cap_error(route) > 1e-7:
        raise ValueError("The initial route must close its unchanged caps.")
    floor = route.targets.diameter_mm * 1e-7
    current = route
    for iteration in range(maximum_iterations):
        if checkpoint is not None:
            checkpoint()
        straights = tuple(p for p in current.pieces if isinstance(p.geometry, Straight))
        lengths = tuple(p.geometry.material_length_mm for p in straights)
        active = tuple(i for i, length in enumerate(lengths) if length > floor * (1 + 1e-6))
        directions = tuple(straights[i].pose.tangent for i in active)
        delta = shortening_direction(directions)
        if math.fsum(delta) >= -1e-10:
            return current, "no_linear_descent"
        displacement = [0.0] * len(lengths)
        for index, value in zip(active, delta):
            displacement[index] = value
        limits = [
            (length - floor) / -change
            for length, change in zip(lengths, displacement)
            if change < -1e-12
        ]
        if not limits:
            raise ArithmeticError("A shortening direction needs a decreasing straight.")
        step = min(limits)
        for backtrack in range(maximum_backtracks):
            if checkpoint is not None:
                checkpoint()
            candidate = reposition(
                current,
                tuple(
                    max(floor, length + step * change)
                    for length, change in zip(lengths, displacement)
                ),
            )
            gain = current.material_length_mm - candidate.material_length_mm
            if gain <= floor:
                return current, "numerical_gain_floor"
            if cap_error(candidate) > 1e-7:
                raise ArithmeticError("Projected contraction lost endpoint closure.")
            contact = inspect_contact(candidate, checkpoint=checkpoint)
            accepted = contact.status == "separated"
            if record is not None:
                record(Trial(iteration, backtrack, candidate, contact, accepted, gain))
            if accepted:
                current = candidate
                break
            step /= 2
        else:
            return current, "contact_step_budget"
    return current, "iteration_budget"
