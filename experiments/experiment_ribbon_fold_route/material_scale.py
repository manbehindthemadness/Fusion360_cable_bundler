"""
Condition native authoring with a fixed binary representation scale, never changing physical geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable

from cable_bundler.routing.geometry import Vector3

from .geometry import PlacedPiece, Straight
from .material_surfaces import MaterialPatch


class NativeScale(Enum):
    """
    Select one fixed representation before construction, without a retry or scale search.
    """

    UNIT = 0
    CONDITIONED = 10

    @property
    def factor(self) -> float:
        """
        Return the exact positive power of two used only for native construction.
        """
        return math.ldexp(1.0, self.value)


@dataclass(frozen=True)
class MaterialConstruction:
    """
    Retain ordered construction inputs separately from the original physical audit geometry.
    """

    policy: NativeScale
    pieces: tuple[PlacedPiece, ...]
    patches: tuple[MaterialPatch, ...]


def construction(
    pieces: tuple[PlacedPiece, ...],
    patches: tuple[MaterialPatch, ...],
    policy: NativeScale,
    checkpoint: Callable[[], None],
) -> MaterialConstruction:
    """
    Scale every dimensional authoring quantity together while retaining frames and material provenance.

    This is not routing or a changed physical target. The caller must apply the
    inverse scale to the one native transient before persistence and audit against
    the original inputs. Binary scaling is exact for representable coordinates;
    overflow/nonfinite arithmetic rejects instead of selecting another factor.
    Unit policy returns the original immutable tuples. Existing clocks cover all
    work, including checkpoints per piece and patch; no native attempt is made here.
    """
    if not isinstance(policy, NativeScale):
        raise ValueError("Select an explicit native construction scale")
    checkpoint()
    if policy is NativeScale.UNIT:
        return MaterialConstruction(policy, pieces, patches)

    def scalar(value: float) -> float:
        """
        Refuse unrepresentable construction dimensions without changing the selected scale.
        """
        result = math.ldexp(value, policy.value)
        if not math.isfinite(result):
            raise ValueError("Native construction dimension must remain finite")
        return result

    def point(value: Vector3) -> Vector3:
        """
        Transform an authored point in the same component coordinate frame.
        """
        return Vector3(scalar(value.x), scalar(value.y), scalar(value.z))

    scaled_pieces = []
    for piece in pieces:
        checkpoint()
        geometry = piece.geometry
        scaled_geometry = (
            replace(geometry, material_length_mm=scalar(geometry.material_length_mm))
            if isinstance(geometry, Straight)
            else replace(
                geometry,
                radius_mm=scalar(geometry.radius_mm),
                width_mm=scalar(geometry.width_mm),
                before_mm=scalar(geometry.before_mm),
                after_mm=scalar(geometry.after_mm),
            )
        )
        scaled_pieces.append(
            replace(
                piece,
                pose=replace(piece.pose, origin=point(piece.pose.origin)),
                geometry=scaled_geometry,
            )
        )
    scaled_patches = []
    for patch in patches:
        checkpoint()
        scaled_profile = replace(
            patch.profile,
            controls=tuple((scalar(q), scalar(b)) for q, b in patch.profile.controls),
        )
        scaled_patches.append(
            replace(
                patch,
                rows=tuple(tuple(point(value) for value in row) for row in patch.rows),
                profile=scaled_profile,
                error_bound_mm=scalar(patch.error_bound_mm),
            )
        )
    return MaterialConstruction(policy, tuple(scaled_pieces), tuple(scaled_patches))
