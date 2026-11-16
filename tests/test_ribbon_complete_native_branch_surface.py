"""
Verify whole-grid encoding bounds and the native SDK argument boundary without Fusion.
"""

from __future__ import annotations

import sys
from fractions import Fraction
from math import comb
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.native_branch_surface import (
    NativeSurfaceGrid,
    UnsupportedNativeSurface,
    create,
)
from experiments.experiment_ribbon_complete.spatial_transition import Net
from tests.test_ribbon_complete_lengths import checkpoint


def source(offset: Fraction = Fraction(0), scale: Fraction = Fraction(1)) -> Net:
    """
    Supply a spatial, nonseparable rational tensor with independently specified Cartesian controls.
    """
    return tuple(
        tuple(
            (
                (offset + u * 10 + Fraction(1, 7)) * weight,
                v * 5 * weight,
                (u * v * 2 + Fraction(1, 3)) * weight,
                weight,
            )
            for v, weight in enumerate(tuple(scale * w for w in weights))
        )
        for u, weights in enumerate(
            ((Fraction(1), Fraction(2, 3), Fraction(1)), (Fraction(1), Fraction(3, 5), Fraction(1)))
        )
    )


def evaluate(rows: Net, u: Fraction, v: Fraction) -> tuple[Fraction, ...]:
    """
    Independently evaluate the Bernstein tensor by binomial basis sums.
    """
    degree_u, degree_v = len(rows) - 1, len(rows[0]) - 1
    values = tuple(
        sum(
            (
                point[k]
                * comb(degree_u, i)
                * u**i
                * (1 - u) ** (degree_u - i)
                * comb(degree_v, j)
                * v**j
                * (1 - v) ** (degree_v - j)
                for i, row in enumerate(rows)
                for j, point in enumerate(row)
            ),
            Fraction(0),
        )
        for k in range(4)
    )
    return tuple(value / values[3] for value in values[:3])


@pytest.mark.parametrize("offset", (Fraction(0), Fraction(10**6)))
def test_encoding_bound_covers_interior_and_boundary_values_of_nonseparable_tensor(
    offset: Fraction,
) -> None:
    """
    Independent rational evaluation is enclosed even with a substantial translated source origin.
    """
    rows = source(offset)
    grid = NativeSurfaceGrid(rows, checkpoint)
    decoded = tuple(
        tuple(
            (
                Fraction(p.x) * 10 * Fraction(w),
                Fraction(p.y) * 10 * Fraction(w),
                Fraction(p.z) * 10 * Fraction(w),
                Fraction(w),
            )
            for p, w in zip(grid.points_cm[i * 3 : (i + 1) * 3], grid.weights[i * 3 : (i + 1) * 3])
        )
        for i in range(2)
    )
    for u in (Fraction(0), Fraction(1, 7), Fraction(1, 2), Fraction(1)):
        for v in (Fraction(0), Fraction(1, 7), Fraction(1, 2), Fraction(1)):
            actual, expected = evaluate(decoded, u, v), evaluate(rows, u, v)
            assert (
                sum((abs(a - b) for a, b in zip(actual, expected)), Fraction(0))
                <= grid.distance_upper_mm
            )
    assert grid.rows is rows and grid.distance_upper_mm < Fraction(1, 10**6)


def test_common_weight_scale_preserves_the_encoding_bound_and_actual_weight_ratios() -> None:
    """
    Binary scaling changes every supplied weight without secretly replacing the weight grid.
    """
    original = NativeSurfaceGrid(source(), checkpoint)
    scaled = NativeSurfaceGrid(source(scale=Fraction(2**20)), checkpoint)
    assert original.points_cm == scaled.points_cm
    assert scaled.weights == tuple(w * 2**20 for w in original.weights)
    assert scaled.distance_upper_mm == original.distance_upper_mm
    assert original.weights[1] != original.weights[4]


@pytest.mark.parametrize("kind", ("empty", "ragged", "zero_weight", "float_control"))
def test_invalid_source_grids_do_not_acquire_a_native_encoding(kind: str) -> None:
    """
    Structural and exact-coordinate premises must hold before a grid reaches the SDK.
    """
    rows = source()
    if kind == "empty":
        rows = ()
    elif kind == "ragged":
        rows = (rows[0], rows[1][:-1])
    elif kind == "zero_weight":
        rows = ((rows[0][0][:3] + (Fraction(0),),) + rows[0][1:], rows[1])
    else:
        rows = cast(Net, cast(object, ((rows[0][0][:3] + (1.0,),) + rows[0][1:], rows[1])))
    with pytest.raises(ValueError, match="tensor|controls|weights"):
        NativeSurfaceGrid(rows, checkpoint)


@pytest.mark.parametrize("kind", ("overflow", "weight_underflow", "inaccurate"))
def test_unavailable_binary_representation_is_not_a_physical_infeasibility_claim(kind: str) -> None:
    """
    Unrepresentable finite source data is refused without rounding, fitting or rescaling it.
    """
    rows = source(Fraction(10**400) if kind == "overflow" else Fraction(10**20 + 1))
    if kind == "weight_underflow":
        rows = source(scale=Fraction(1, 10**400))
    with pytest.raises(UnsupportedNativeSurface):
        NativeSurfaceGrid(rows, checkpoint)


@pytest.mark.parametrize("refused", (False, True))
def test_sdk_receives_every_weight_point_and_knot_once_without_fallback(
    monkeypatch: pytest.MonkeyPatch, refused: bool
) -> None:
    """
    The real API boundary uses complete U-major control data; SDK refusal causes no alternate construction.
    """
    calls: list[tuple[Any, ...]] = []
    result = object()

    def factory(*arguments: Any) -> object | None:
        """
        Capture one call at the external SDK boundary, optionally refusing construction.
        """
        calls.append(arguments)
        return None if refused else result

    adsk, core = ModuleType("adsk"), ModuleType("adsk.core")
    monkeypatch.setitem(vars(adsk), "core", core)
    monkeypatch.setitem(vars(core), "Point3D", SimpleNamespace(create=Vector3))
    monkeypatch.setitem(vars(core), "NurbsSurface", SimpleNamespace(create=factory))
    monkeypatch.setitem(
        vars(core),
        "NurbsSurfaceProperties",
        SimpleNamespace(OpenNurbsSurface=1, RationalNurbsSurface=2),
    )
    monkeypatch.setitem(sys.modules, "adsk", adsk)
    monkeypatch.setitem(sys.modules, "adsk.core", core)
    grid = NativeSurfaceGrid(source(), checkpoint)
    if refused:
        with pytest.raises(RuntimeError, match="creation failed"):
            create(grid, checkpoint)
    else:
        assert create(grid, checkpoint) is result
    assert len(calls) == 1
    args = calls[0]
    assert args[:4] == (1, 2, 2, 3)
    assert args[4] == list(grid.points_cm)
    assert args[5:8] == ([0, 0, 1, 1], [0, 0, 0, 1, 1, 1], list(grid.weights))
    assert args[8:] == (3, 3)


def test_callers_latched_stop_prevents_native_work() -> None:
    """
    A resource failure cannot be converted into a valid encoding or native fallback.
    """
    grid = NativeSurfaceGrid(source(), checkpoint)

    def stopped() -> None:
        """
        Simulate the original caller's exhausted allocation.
        """
        raise RuntimeError("latched resource stop")

    with pytest.raises(RuntimeError, match="latched"):
        NativeSurfaceGrid(source(), stopped)
    with pytest.raises(RuntimeError, match="latched"):
        create(grid, stopped)
