"""
Verify that reduced pathing uses macaroni and structural banking without auxiliary rules.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, dot
from devtools.ribbon_analysis.inspection.session import Session
from devtools.ribbon_analysis.pinch import BendModel
from experiments.experiment_ribbon_cap_transition import director_shooting
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
)
from experiments.experiment_ribbon_cap_transition.constraint_policy import (
    FULL,
    ConstraintPolicy,
    PathRules,
    configured,
    current,
    scope,
)
from experiments.experiment_ribbon_cap_transition.director_route_objective import (
    free_penalties,
    routing_penalties,
)
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_diagnostic_viewer import examples, procedures
from experiments.experiment_ribbon_route_discovery import broad_chart, broad_search, generalized
from experiments.experiment_ribbon_route_discovery.families import Seed

MINIMAL = ConstraintPolicy(bend_model=BendModel.PINCH, path_rules=PathRules.MACARONI)


def _case() -> EndpointCase:
    """
    Freeze a straight boundary control without supplying an interior path.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase("minimal control", Vector3(0, 0, 0), Vector3(80, 0, 0), x, x, y, y, 3, 1.5)


def test_fresh_controls_use_two_rules_and_historical_configuration_stays_explicit() -> None:
    """
    Default new runs consistently while preserving the historical API and scope isolation.
    """
    choices = procedures.demonstration()
    assert len(choices) == 9
    assert all(item["settings"]["path_rules"] == PathRules.MACARONI.value for item in choices)
    assert all(configured([], item["settings"]) == MINIMAL for item in choices)
    assert configured([], {}) == FULL
    with scope(MINIMAL):
        assert current() is MINIMAL
    assert current() == FULL
    historical = procedures.selections([{"id": "ordinary", "settings": {"bend_model": "legacy"}}])
    assert historical[0]["settings"]["path_rules"] == "historical"


@pytest.mark.parametrize(
    "procedure,settings",
    (
        ("ordinary", {"bend_model": "legacy"}),
        ("compatible", {"objective": "legacy sphere feedback"}),
        ("discovery", {"variant": "plane guided"}),
        ("discovery", {"variant": "distance guided"}),
    ),
)
def test_auxiliary_rules_cannot_be_hidden_in_a_minimal_request(
    procedure: str, settings: dict[str, Any]
) -> None:
    """
    Reject incompatible named options before a worker can execute extra constraints.
    """
    with pytest.raises(ValueError):
        procedures.selections(
            [{"id": procedure, "settings": dict(settings, path_rules=PathRules.MACARONI.value)}]
        )
    explicit = procedures.selections(
        [{"id": procedure, "settings": dict(settings, path_rules="historical")}]
    )
    assert explicit[0]["settings"]["path_rules"] == "historical"


def test_material_reserve_and_sphere_are_absent_from_minimal_objectives() -> None:
    """
    Positive progress below the old J reserve receives no extra penalty or pose query.
    """

    def sample(_u: float) -> tuple[float, float, float]:
        """
        Supply zero bend and positive J=0.05 below the historical0.1target.
        """
        return 0.0, 0.2, 0.95 / 2.4

    path: Any = SimpleNamespace(
        field=SimpleNamespace(half_width_mm=2.4, constraints=MINIMAL, sample=sample),
        pose=Mock(side_effect=AssertionError("Sphere geometry must not be queried")),
    )
    assert routing_penalties(_case(), path) == (0.0,) * 99
    assert free_penalties(_case(), path) == (0.0,) * 99
    path.field.constraints = replace(MINIMAL, path_rules=PathRules.HISTORICAL)
    assert any(value > 0 for value in routing_penalties(_case(), path))
    path.pose.assert_not_called()


def test_only_intrinsic_positive_progress_and_macaroni_limit_shape_the_reduced_chart() -> None:
    """
    Remove the historical reserve without altering cable dimensions or its bend limit.
    """
    raw = RoutingField("stress", 4, (50, 0, 0, 0), (0.5, -0.5, 0.4, 0.3), 3, 1.5)
    with scope(replace(MINIMAL, path_rules=PathRules.HISTORICAL)):
        historical = CompatibleField(raw, BendMapping.NEAR_LIMIT)
    with scope(MINIMAL):
        reduced = CompatibleField(raw, BendMapping.NEAR_LIMIT)
    assert reduced.ruling_scale > historical.ruling_scale
    assert (reduced.lines, reduced.diameter_mm, reduced.half_width_mm) == (
        historical.lines,
        historical.diameter_mm,
        historical.half_width_mm,
    )
    for index in range(129):
        observed = reduced.carrier(index / 128)
        minimum_progress = observed.progress_mm - reduced.half_width_mm * abs(observed.eta_u)
        assert minimum_progress > 0
        limit = reduced.turn_limit(observed)
        assert limit is not None and abs(observed.turn) <= limit


def test_minimal_transport_retains_no_lateral_bending() -> None:
    """
    Check actual director derivatives against the width axis along a spatial transport.
    """
    with scope(MINIMAL):
        path = broad_chart.integrate(
            _case(), (1.1, -0.3, 0.2, 0.1, 0.1, 0.4, -0.2, 0.1, 0.1, 1.2), 64, lambda: None
        )
    for state, rate in zip(path.states, path.rates):
        assert abs(dot(Vector3(*rate[3:6]), Vector3(*state[6:9]))) < 1e-9


def test_broad_and_neutral_modes_never_sample_or_repair_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Two-rule handoffs depend only on connection goals, with no fabricated contact audit.
    """
    forbidden = Mock(side_effect=AssertionError("Contact decisions are excluded"))
    monkeypatch.setitem(vars(broad_search), "sample", forbidden)
    monkeypatch.setitem(vars(generalized), "sample", forbidden)
    monkeypatch.setattr(broad_search.projected_clearance, "refine", forbidden)
    with scope(MINIMAL):
        case = _case()
        values = (0.0,) * 9 + (1.0,)
        path = broad_chart.integrate(case, values, 64, lambda: None)
        seed = Seed(0, values, 0.0, (0.0, 0.0, 0.0))
        monkeypatch.setattr(broad_search.broad_chart, "screen", lambda *_args: (seed,))
        monkeypatch.setattr(
            broad_search.box_fit,
            "refine",
            lambda *_args: (
                path,
                {"score": 0.0, "strict_endpoint_gate": True, "coordinates": values},
            ),
        )
        ledger = broad_search.solve(case, lambda: None, broad_search.SearchLedger())
        candidate = ledger.candidate
        assert candidate is not None
        assert candidate.contact["contact_enforced"] is False
        assert "contact_detected" not in candidate.contact
        neutral = generalized.solve(case, lambda: None, broad_search.SearchLedger())
        assert neutral is not None and neutral.contact["contact_enforced"] is False
    forbidden.assert_not_called()


def test_director_policies_use_reduced_objective_at_both_grids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Historical director transport choices cannot silently restore old penalty functions.
    """
    forbidden = Mock(side_effect=AssertionError("Historical penalties are excluded"))
    monkeypatch.setitem(vars(director_shooting), "free_penalties", forbidden)
    monkeypatch.setitem(vars(director_shooting), "regular_penalties", forbidden)
    observer = Mock(wraps=director_shooting.routing_penalties)
    monkeypatch.setitem(vars(director_shooting), "routing_penalties", observer)
    with scope(MINIMAL):
        _, metrics = director_shooting.solve(_case(), lambda: None)
    assert observer.call_count == 2 and metrics["evaluations"] == 2
    forbidden.assert_not_called()


def test_old_archives_keep_historical_scope_without_rewriting_them(tmp_path: Path) -> None:
    """
    An old pinch model is not relabelled as the newly reduced rule set.
    """
    manifest = examples.create(tmp_path / "reference", "single", lambda: None)
    original = manifest.read_bytes()
    session = Session(manifest)
    assert session.state()["path_rules"] == "historical"
    assert manifest.read_bytes() == original
