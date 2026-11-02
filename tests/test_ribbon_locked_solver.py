"""
Verify the selected cold solver, smoothing configuration and deferred material-coordinate contract.
"""

from __future__ import annotations

import math
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_locked_solver import Settings, solve
from experiments.experiment_ribbon_locked_solver.coordinates import coordinates


def _checkpoint() -> None:
    """
    Keep analytical unit cases independent of the host resource controller.
    """


def _record(event: dict[str, Any]) -> None:
    """
    Exercise the numerical API without adding artifact dependencies to unit tests.
    """
    del event


def _corner() -> Targets:
    """
    Declare fixed poses for a known feasible quarter turn without supplying a route.
    """
    return Targets(
        "cold analytical corner",
        Vector3(0, 0, 0),
        Vector3(10, 0, 12),
        Vector3(1, 0, 0),
        Vector3(0, 0, 1),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
        1,
        1.0,
    )


@pytest.mark.parametrize("value", [False, -1, 11, float("nan"), float("inf"), "5"])
def test_malformed_smoothing_settings_fail_before_work(value: Any) -> None:
    """
    Reject invalid settings rather than clamping or changing the selected algorithm.
    """
    with pytest.raises(ValueError):
        Settings.parse({"smoothing_percent": value, "material_uv": False})


def test_settings_require_exact_contract_and_explicit_uv_boolean() -> None:
    """
    Do not interpret stale controls or truthy strings as coordinate-generation consent.
    """
    with pytest.raises(ValueError):
        Settings.parse({"smoothing_percent": 5, "material_uv": "false"})
    with pytest.raises(ValueError):
        Settings.parse({"smoothing_percent": 5, "material_uv": False, "seed": 1})
    assert Settings.parse({"smoothing_percent": 0, "material_uv": True}) == Settings(0, True)


@pytest.mark.parametrize("value", (None, 0, 1, "false"))
def test_first_pass_optimization_requires_boolean(value: Any) -> None:
    """
    Reject truthy or missing-shaped control values while preserving legacy defaults.
    """
    with pytest.raises(ValueError, match="explicit boolean"):
        Settings.parse(
            {"smoothing_percent": 0, "material_uv": False, "first_pass_optimization": value}
        )


def test_first_pass_optimization_round_trips_and_legacy_records_default_on() -> None:
    """
    Retain explicit disabled settings without changing the meaning of existing two-control jobs.
    """
    settings = Settings(1, False, False)
    assert Settings.parse(asdict(settings)) == settings
    assert Settings.parse({"smoothing_percent": 1, "material_uv": False}).first_pass_optimization


@pytest.mark.parametrize("diameter_mm", [0.75, 1.0, 1.5, 3.0])
def test_cold_construction_needs_no_archived_successful_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, diameter_mm: float
) -> None:
    """
    Solve only from cap poses while working outside the repository's artifact directory.
    """
    monkeypatch.chdir(tmp_path)
    targets = replace(_corner(), diameter_mm=diameter_mm)
    result = solve(targets, Settings(), _checkpoint, _record)
    assert result.route is not None and result.first_pass is not None
    assert cap_error(result.route) < 1e-7
    assert result.route.targets == targets
    assert result.route.material_length_mm <= result.first_pass.material_length_mm * 1.05 + 1e-8
    assert result.detail["status"] == "numerically_accepted"
    assert result.detail["native_fidelity"] == "unmeasured"
    assert result.material_uv is None
    assert not list(tmp_path.iterdir())


def test_zero_smoothing_skips_every_second_pass_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve the exact first-pass object when the user disables aesthetic processing.
    """

    def forbidden(*args: Any, **kwargs: Any) -> None:
        """
        Fail if an explicitly disabled second-pass operation is called.
        """
        del args, kwargs
        raise AssertionError("Smoothing is disabled")

    for name in ("ease_radii", "ease_layout", "merge"):
        monkeypatch.setattr(
            "experiments.experiment_ribbon_locked_solver.smoothing." + name, forbidden
        )
    result = solve(_corner(), Settings(0), _checkpoint, _record)
    assert result.route is result.first_pass
    assert result.detail["stages"] == {"smoothing": "disabled"}


def test_optional_material_coordinates_follow_global_lane_distance_without_textures() -> None:
    """
    Recover ordered material coordinates on both straight and curved pieces without Fusion.
    """
    result = solve(_corner(), Settings(0, True), _checkpoint, _record)
    assert result.route is not None and result.material_uv is not None
    route = result.route
    assert result.material_uv["schema"] == "ribbon-material-coordinates-v1"
    assert result.material_uv["route"]["case"]["name"] == route.targets.name
    for index, piece in enumerate(route.pieces):
        q = route.half_width_mm * 0.3
        u, region = 0.5, "straight"
        if isinstance(piece.geometry, CylindricalFold):
            low, high = piece.geometry.bend_interval(q)
            u, region = (low + high) / 2, "bend"
        point = piece.surface(u, q)[0]
        along, across, height = coordinates(route, index, region, point)
        expected = (
            route.starts_mm[index] + u * piece.geometry.material_length_mm
        ) / route.material_length_mm
        assert along == pytest.approx(expected, abs=1e-11)
        assert across == pytest.approx(0.65, abs=1e-11)
        assert math.isclose(height, 0.0, abs_tol=1e-11)


def test_unresolved_construction_does_not_revert_to_a_retired_solver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Return an explicit no-route result when the finite joint families do not pass contact.
    """

    def unresolved(*args: Any, **kwargs: Any) -> tuple[None, dict[str, Any]]:
        """
        Represent an exhausted finite construction, not geometric impossibility.
        """
        del args, kwargs
        return None, {"stop_reason": "contact_budget"}

    monkeypatch.setattr("experiments.experiment_ribbon_locked_solver.solver.construct", unresolved)
    result = solve(_corner(), Settings(), _checkpoint, _record)
    assert result.route is result.first_pass is None
    assert result.detail["status"] == "unresolved"
