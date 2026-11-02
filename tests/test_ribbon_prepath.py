"""
Verify that the reference display uses the solver's exact directed endpoint cubic.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from devtools.ribbon_analysis.gym import Config, generate
from devtools.ribbon_analysis.prepath import controls, drawing
from experiments.experiment_ribbon_spline_guide.guide import Guide


@pytest.mark.parametrize("seed,diameter", [(2026110101, 0.75), (2026110102, 1.5), (2026110103, 3)])
def test_prepath_matches_solver_controls_and_directed_caps(seed: int, diameter: float) -> None:
    """
    Preserve both directed tangents and every control across scaled spatial gym layouts.
    """
    targets = generate(Config(seed=seed, diameter_mm=diameter)).targets
    guide = Guide.create(targets)
    payload = drawing(targets)
    assert tuple(Vector3(**p) for p in payload["controls"]) == guide.controls == controls(targets)
    assert payload["points"][0] == asdict(targets.start)
    assert payload["points"][-1] == asdict(targets.end)
    for i, point in enumerate(payload["points"]):
        assert magnitude(difference(Vector3(**point), guide.sample(i / 128)[0])) < 1e-12
    assert dot(
        unit(difference(guide.controls[1], guide.controls[0])), targets.start_tangent
    ) == pytest.approx(1)
    assert dot(
        unit(difference(guide.controls[3], guide.controls[2])), targets.end_tangent
    ) == pytest.approx(1)
