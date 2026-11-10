"""
Verify strict thickness witnesses on analytical strips and finite terminal boxes.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.contact_bounds import Span
from experiments.experiment_ribbon_fold_route.contact_inverse import profile_height
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.model import (
    Box,
    Dimensions,
    Hardware,
    Terminal,
)
from experiments.experiment_ribbon_terminal_hardware.witness_height import occupied_height
from tests.test_ribbon_terminal_hardware import _primitives, _straight


def _box(center: float, height: float = 0.0002) -> Box:
    """
    Intersect only a thin height band, with generous independent width and depth.
    """
    return Box(
        Terminal.START,
        Pose(Vector3(0, 0, center), Vector3(1, 0, 0), Vector3(0, 1, 0)),
        Dimensions(2, height, 2),
    )


@pytest.mark.parametrize("normal", (Vector3(0, 0, -1), Vector3(0, 0, 1), Vector3(0.6, 0, 0.8)))
@pytest.mark.parametrize("q", (0.0, 0.3))
def test_thin_occupied_band_is_found_when_fixed_midpoint_misses(normal: Vector3, q: float) -> None:
    """
    Find real profile material despite a height midpoint outside the finite box or circular lobe.
    """
    heights = Span(0.4, 0.5)
    box = _box(normal.z * 0.415)
    height = occupied_height(Vector3(-1, q, 0), normal, q, heights, box, 1, 1.0)
    assert height is not None and 0.4149 < height < 0.4151
    assert profile_height(q, 1, 1.0) - height > 1e-9
    assert abs(normal.z * height - box.pose.origin.z) < box.dimensions.height_mm / 2 - 1e-9
    if q:
        assert profile_height(q, 1, 1.0) < (heights.low + heights.high) / 2


def test_existing_valid_midpoint_is_preserved_exactly() -> None:
    """
    Retain the original witness coordinate rather than perturbing already valid evidence.
    """
    assert (
        occupied_height(
            Vector3(-1, 0, 0), Vector3(0, 0, 1), 0.0, Span(0.1, 0.2), _box(0.15, 0.1), 1, 1.0
        )
        == (0.1 + 0.2) / 2
    )


@pytest.mark.parametrize("center", (0.6, 0.5001, 0.3999))
def test_empty_or_boundary_only_intersections_supply_no_witness(center: float) -> None:
    """
    Never turn interval tangency or material outside the profile into intrusion.
    """
    assert (
        occupied_height(
            Vector3(-1, 0, 0), Vector3(0, 0, 1), 0.0, Span(0.4, 0.5), _box(center), 1, 1.0
        )
        is None
    )


@pytest.mark.parametrize("x", (0.0, -2.0, 1.0))
def test_parallel_slab_tangency_or_miss_cannot_be_fixed_by_height(x: float) -> None:
    """
    Preserve strict finite depth when thickness motion cannot change that coordinate.
    """
    assert (
        occupied_height(
            Vector3(x, 0, 0), Vector3(0, 0, 1), 0.0, Span(0.4, 0.5), _box(0.415), 1, 1.0
        )
        is None
    )


def test_full_detector_finds_thin_box_intrusion_within_original_cell_allowance() -> None:
    """
    Detect actual strip thickness inside a thin remote terminal, without a solved-route fixture.
    """
    route = _primitives((_straight(0, 0, 0, 10), _straight(5, 0, 0.25, 1)))
    hardware = Hardware.create(route.targets, Dimensions(3, 3, 5), Dimensions(3, 0.0002, 5))
    report = inspect(route, hardware, maximum_cells=8)
    assert report.status == "blocked" and report.witness is not None
    witness = report.witness
    assert witness.terminal == "end" and witness.piece == 0
    assert report.cells_checked <= 8
    assert 6 < witness.point.x < 11
    assert 0.2499 < witness.point.z < 0.2501
    assert profile_height(witness.material[1], 2, 1.0) - abs(witness.material[2]) > 1e-9
