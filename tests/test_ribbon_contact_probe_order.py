"""
Keep optional negative probes within the original material traversal and proof budgets.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_fold_route.contact import (
    ProbeOrder,
    ProbeResult,
    inspect_contact,
)
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from tests.test_ribbon_flat_contact import load_routes


@pytest.mark.parametrize("name", ("overlap", "separated"))
def test_missed_material_order_probe_preserves_the_exact_original_measurement(name: str) -> None:
    """
    Retain every original comparison and witness when the optional probe supplies no evidence.
    """
    route = load_routes()[name]
    plain = inspect_contact(route, maximum_pairs=1024, cap_policy=CapPolicy.ANALYTIC_SUPPORT)
    probe = Mock(return_value=ProbeResult(0))
    measured = inspect_contact(
        route,
        maximum_pairs=1024,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        witness_probe=probe,
        probe_order=ProbeOrder.MATERIAL_CELLS,
    )
    assert asdict(measured) == asdict(plain)


@pytest.mark.parametrize("invalid", (None, True, "material_cells"))
def test_probe_order_requires_a_typed_policy(invalid: Any) -> None:
    """
    Reject malformed policy values before contact work, including when no probe is supplied.
    """
    with pytest.raises(ValueError, match="probe order"):
        inspect_contact(load_routes()["overlap"], probe_order=invalid)


@pytest.mark.parametrize(
    "seed,lines,a,b",
    (
        (240828600, 3, (8, 4, 295), (21, 0, 56)),
        (1104480256, 3, (3, 5, 289), (24, 4, 66)),
        (1517160563, 5, (24, 7, 48), (4, 8, 48)),
    ),
)
def test_v2_compact_recovery_preserves_distinct_mating_and_contact_mechanics(
    seed: int, lines: int, a: tuple[int, int, int], b: tuple[int, int, int]
) -> None:
    """
    Reject long-fallback regressions across three fixed inputs while retaining strict physical checks.

    The60mm assertion is a regression oracle for these fixtures, not a solver
    limit or a general geometric feasibility rule.
    """
    scene = Scene(Config(seed, lines, 0.75, 300, 300), Goal.from_degrees(*a), Goal.from_degrees(*b))
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, events.append
    )
    assert result.route is not None and result.route.targets == scene.targets
    assert result.route.material_length_mm < 60
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
    construction = result.detail["construction"]
    assert construction["contact_pairs"] <= 2048
    initial = sum(
        event["contact"]["pairs_checked"]
        for event in events
        if event.get("stage") == "feature_contact" and "contact" in event
    )
    recovery = construction["recovery"]
    assert recovery["iterations"] <= 4
    recovery_pairs = recovery.get("contact_pairs", recovery.get("pairs"))
    assert isinstance(recovery_pairs, int)
    assert initial + recovery_pairs == construction["contact_pairs"]
