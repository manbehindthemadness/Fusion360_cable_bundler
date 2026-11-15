"""
Verify the external measurement boundary uses matching assembly context and units.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from experiments.experiment_ribbon_complete.native_distance import trimmed_distance_mm


@dataclass
class Point:
    """
    Track a copied centimeter point under a known occurrence translation.
    """

    x: float
    y: float
    z: float

    def copy(self) -> Point:
        """
        Preserve the caller's component-local point while returning a mutable temporary.
        """
        return Point(self.x, self.y, self.z)

    def transform_by(self, transform: tuple[float, float, float]) -> bool:
        """
        Apply the synthetic assembly translation once.
        """
        self.x += transform[0]
        self.y += transform[1]
        self.z += transform[2]
        return True

    transformBy = transform_by


class Face:
    """
    Refuse measuring the local face directly; retain the exact requested occurrence.
    """

    def __init__(self) -> None:
        """
        Start with no assembly request and a distinct proxy identity.
        """
        self.occurrence: Any = None
        self.proxy = object()

    def create_for_assembly_context(self, occurrence: Any) -> object:
        """
        Record the owning occurrence without modifying the native face.
        """
        self.occurrence = occurrence
        return self.proxy

    createForAssemblyContext = create_for_assembly_context


@pytest.mark.parametrize("value", (0.0, 0.0005))
def test_distance_uses_copied_point_and_face_in_the_same_assembly_context(value: float) -> None:
    """
    A610cm display translation affects both arguments once;0.0005cm reports0.005mm.
    """
    point = Point(1, 2, 3)
    occurrence = SimpleNamespace(transform2=(610, -7, 4))
    face = Face()

    class Manager:
        """
        Validate the measurement arguments before returning a centimeter scalar.
        """

        def __init__(self) -> None:
            """
            Retain the synthetic external distance for this manager instance.
            """
            self.distance = value

        def measure_minimum_distance(self, world: Point, proxy: object) -> SimpleNamespace:
            """
            Accept only the aligned root-context arguments.
            """
            assert world == Point(611, -5, 7) and world is not point
            assert proxy is face.proxy and face.occurrence is occurrence
            return SimpleNamespace(value=self.distance)

        measureMinimumDistance = measure_minimum_distance

    assert trimmed_distance_mm(point, face, occurrence, Manager()) == value * 10
    assert point == Point(1, 2, 3)


@pytest.mark.parametrize("value", (None, float("nan"), -0.01, True))
def test_missing_or_invalid_native_distance_never_becomes_zero(value: Any) -> None:
    """
    Fail closed on malformed external measurement results.
    """

    class InvalidManager:
        """
        Return a deliberately malformed external result.
        """

        def __init__(self) -> None:
            """
            Retain one invalid external measurement result.
            """
            self.value = value

        def measure_minimum_distance(self, _point: Any, _face: Any) -> SimpleNamespace:
            """
            Preserve the supplied invalid value for boundary validation.
            """
            return SimpleNamespace(value=self.value)

        measureMinimumDistance = measure_minimum_distance

    with pytest.raises(RuntimeError, match="unavailable or invalid"):
        trimmed_distance_mm(
            Point(0, 0, 0), Face(), SimpleNamespace(transform2=(0, 0, 0)), InvalidManager()
        )
