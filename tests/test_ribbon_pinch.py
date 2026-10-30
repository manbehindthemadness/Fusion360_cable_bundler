"""
Check the demo's geometric pinch percentage, coupled strip limits and versioned policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    snapshot_payload,
    targets_payload,
    write_document,
)
from devtools.ribbon_analysis.inspection.geometry import (
    LocalFrame,
    freeze_curve,
    freeze_path,
    local_frame,
)
from devtools.ribbon_analysis.inspection.pinch_geometry import sample
from devtools.ribbon_analysis.inspection.session import Session
from devtools.ribbon_analysis.pinch import BendModel, PinchLimit
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import seed_coordinates
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
)
from experiments.experiment_ribbon_cap_transition.constraint_policy import (
    FULL,
    ConstraintPolicy,
    configured,
    scope,
)
from experiments.experiment_ribbon_cap_transition.director_fields import DirectorField
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.director_transport import integrate
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_diagnostic_viewer import examples


@dataclass(frozen=True)
class DemoCircle:
    """
    Independently reproduce the user's R25/profile-R24.9 toroidal demonstration.
    """

    radius_mm: float = 25

    def jet(self, u: float) -> tuple[Vector3, Vector3]:
        """
        Supply a semicircle and its exact normalized derivative in millimetres.
        """
        angle = math.pi * u
        return Vector3(
            self.radius_mm * (1 - math.cos(angle)), 0, self.radius_mm * math.sin(angle)
        ), Vector3(
            self.radius_mm * math.pi * math.sin(angle),
            0,
            self.radius_mm * math.pi * math.cos(angle),
        )

    def frame(self, u: float) -> LocalFrame:
        """
        Keep the circular section normal to the real path tangent.
        """
        point, tangent = self.jet(u)
        return local_frame(point, tangent, Vector3(0, 1, 0))


def test_user_demo_is_99_point_6_percent_with_positive_inner_radius() -> None:
    """
    Recover the measured demo ratio independently from its frozen cubic geometry.
    """
    snapshot = freeze_curve("user-demo", DemoCircle(), 49.8, intervals=512)
    point = sample(snapshot, 0.25, 99.6)
    assert point["radii_mm"]["centre"] == pytest.approx(25, rel=4e-6)
    assert point["maximum_percent"] == pytest.approx(99.6, rel=4e-6)
    assert point["inside_remaining_percent"] == pytest.approx(0.4, abs=0.0004)
    assert point["reference_radii_mm"]["centre"] == pytest.approx(25)


@pytest.mark.parametrize("amplitude", (-0.25, 0.0, 0.25))
def test_principal_curvature_and_radius_order_use_the_same_material_station(
    amplitude: float,
) -> None:
    """
    Check an independently authored regular strip against its analytic normal-offset Jacobian.
    """
    field = DirectorField("independent-strip", 10, (4, 0, 0, 0), (0, 0, amplitude, 0), 3, 1.5)
    snapshot = freeze_path("strip", integrate(field, 512, lambda: None), intervals=512)
    point = sample(snapshot, 0.125, 99.6)
    k, eta, eta_s = field.sample(0.125)
    expected = 100 * 0.75 * abs(k) * (1 + eta * eta) / (1 - field.half_width_mm * abs(eta_s))
    assert point["maximum_percent"] == pytest.approx(expected, rel=2e-5)
    assert point["ordered"] is True
    a, c, b = (point["radii_mm"][key] for key in ("edge_a", "centre", "edge_b"))
    assert c == pytest.approx((a + b) / 2, rel=2e-5)
    red_a, red_c, red_b = (
        point["reference_radii_mm"][key] for key in ("edge_a", "centre", "edge_b")
    )
    assert red_c == pytest.approx((red_a + red_b) / 2, rel=2e-5)
    if amplitude > 0:
        assert b < c < a and red_b < red_c < red_a
    elif amplitude < 0:
        assert a < c < b and red_a < red_c < red_b
    else:
        assert a == pytest.approx(c) and b == pytest.approx(c)


@pytest.mark.parametrize("lines", (1, 3, 19))
def test_turn_bound_keeps_the_entire_thickness_locally_positive(lines: int) -> None:
    """
    Exercise large raw turns while checking both thickness faces over the full width.
    """
    policy = ConstraintPolicy(bend_model=BendModel.PINCH, pinch_percent=99.6)
    field = CompatibleField(
        RoutingField("tight", 10, (50, 0, 10, 0), (0.3, -0.3, 0.4, 0), lines, 1.5),
        BendMapping.NEAR_LIMIT,
        policy,
    )
    for index in range(65):
        value = field.carrier(index / 64)
        for q in (-field.half_width_mm, 0, field.half_width_mm):
            progress = value.progress_mm if lines == 1 else value.progress_mm + q * value.eta_u
            factor = 1 if lines == 1 else 1 + value.eta * value.eta
            utilization = abs(value.turn) * 0.75 * factor / progress
            assert utilization <= 0.996 + 1e-14
            assert progress - abs(value.turn) * 0.75 * factor > 0


@pytest.mark.parametrize("percent", (0, 100, -1, float("nan"), True, "99"))
def test_invalid_pinch_percentages_reject(percent: float) -> None:
    """
    Refuse singular/ambiguous percentage inputs before geometry or search.
    """
    with pytest.raises(ValueError):
        PinchLimit(percent)


def test_pinch_seeds_remove_the_historical_width_reach_length_allowance() -> None:
    """
    Preserve the legacy allocator while giving the new rule its own declared initialization.
    """
    _, case = examples.ribbon(lambda: None)
    raw = (0.0, 0.0, math.pi, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 1.0)
    legacy = seed_coordinates(case, raw)
    with scope(ConstraintPolicy(bend_model=BendModel.PINCH)):
        corrected = seed_coordinates(case, raw)
    assert corrected[9] < legacy[9]
    assert seed_coordinates(case, raw) == legacy
    assert FULL.bend_model is BendModel.LEGACY


def test_versioned_replay_preserves_legacy_and_moves_coupled_circles_together(
    tmp_path: Path,
) -> None:
    """
    Keep historical rules intact while replaying new radii at one selected station.
    """
    field = DirectorField("versioned", 10, (4, 0, 0, 0), (0, 0, 0.25, 0), 3, 1.5)
    path = integrate(field, 512, lambda: None)
    frozen = freeze_path("shared", path, intervals=64)
    last = path.states[-1]
    targets = EndpointCase(
        "versioned",
        Vector3(0, 0, 0),
        Vector3(*last[:3]),
        Vector3(1, 0, 0),
        Vector3(*last[3:6]),
        Vector3(0, 1, 0),
        Vector3(*last[6:9]),
        3,
        1.5,
    )
    methods = []
    for identifier, settings in (
        ("old", {"objective": "routing"}),
        ("new", {"bend_model": "pinch percent", "pinch_percent": 99.6}),
    ):
        methods.append(
            {
                "id": identifier,
                "label": identifier,
                "status": "recorded",
                "detail": "Test frozen field.",
                "source": "independent authored field",
                "procedure": "compatible",
                "settings": settings,
                "rules": [],
                "snapshot": snapshot_payload(frozen),
            }
        )
    manifest = tmp_path / "manifest.json"
    write_document(
        manifest, {"schema": SCHEMA, "targets": targets_payload(targets), "solvers": methods}
    )
    original = manifest.read_bytes()
    session = Session(manifest)
    assert session.state()["bend_policy"]["model"] == "legacy"
    session.select("new")
    session.select_section(2)
    state = session.state()
    assert state["bend_policy"]["pinch_percent"] == 99.6
    assert all(dict(w["measurements"])["u"] == 0.125 for w in state["witnesses"][:3])
    assert not any(rule["name"] == "Legacy centre reach cap" for rule in state["rules"])
    session.select_section(4)
    assert all(dict(w["measurements"])["u"] == 0.25 for w in session.state()["witnesses"][:3])
    assert manifest.read_bytes() == original


def test_pinch_ablation_has_one_coupled_bend_limit() -> None:
    """
    Prevent a separate centre toggle from becoming an ineffective new-model control.
    """
    with pytest.raises(ValueError, match="one coupled"):
        configured(["centre_bend"], {"bend_model": "pinch percent"})
    policy = configured(["lane_bend"], {"bend_model": "pinch percent", "pinch_percent": 95.0})
    assert policy.pinch_percent == 95.0
