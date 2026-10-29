"""
Verify signed-turn allocation and unchanged geometry/search bounds independently of closure.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_redistribution.allocation import propose
from experiments.experiment_ribbon_bend_redistribution.refinement import redistribute
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
    CompatiblePath,
)
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import broad_chart


def _field(
    bending: tuple[float, float, float, float, float],
) -> tuple[CompatibleField, tuple[float, ...]]:
    """
    Author a short field with visible saturation independent of any historical case.
    """
    raw = RoutingField(
        "allocation control",
        60,
        (bending[0], bending[1], bending[2], bending[3]),
        (0, 0, 0, 0),
        19,
        1,
        bending[4],
        0,
    )
    return CompatibleField(raw, BendMapping.NEAR_LIMIT), bending + (0, 0, 0, 0, 1)


@pytest.mark.parametrize("sign", (1, -1))
def test_allocation_relaxes_peak_and_tightens_loose_region_with_signed_turn_conserved(
    sign: int,
) -> None:
    """
    Balance actual turning within one sign region while preserving sampled demand.
    """
    field, values = _field((sign * 3, sign * 3, 0, 0, 0))
    allocation = propose(field, values)
    assert allocation is not None
    assert allocation.reason == "near-limit bend"
    assert abs(allocation.target_turns[allocation.peak]) < abs(allocation.turns[allocation.peak])
    assert abs(allocation.target_turns[allocation.recipient]) > abs(
        allocation.turns[allocation.recipient]
    )
    weights = (0.5,) + (1.0,) * 31 + (0.5,)
    assert sum(w * t for w, t in zip(weights, allocation.target_turns)) == pytest.approx(
        sum(w * t for w, t in zip(weights, allocation.turns)), abs=1e-12
    )
    lower, upper = allocation.region
    for i, (before, after, limit) in enumerate(
        zip(allocation.turns, allocation.target_turns, allocation.limits)
    ):
        assert abs(after) < limit
        if lower <= i <= upper:
            assert before * after >= 0
        else:
            assert before == after
    assert allocation.proposed[5:] == values[5:]
    assert all(abs(v) <= 4 * math.pi for v in allocation.proposed[:5])
    assert math.sqrt(sum((a - b) ** 2 for a, b in zip(allocation.proposed, values))) <= 1.5 + 1e-12
    changed = replace(
        field.raw,
        bending=(
            allocation.proposed[0],
            allocation.proposed[1],
            allocation.proposed[2],
            allocation.proposed[3],
        ),
        extra_bending=allocation.proposed[4],
    )
    mapped = CompatibleField(changed, BendMapping.NEAR_LIMIT)
    assert abs(mapped.carrier(allocation.fractions[allocation.peak]).turn) < abs(
        allocation.turns[allocation.peak]
    )


@pytest.mark.parametrize("bending", ((0, 0, 0, 0, 0), (0.2, 0, 0, 0, 0), (8, 0, 0, 0, 0)))
def test_neutral_gentle_and_uniformly_saturated_fields_have_no_transfer(
    bending: tuple[float, float, float, float, float],
) -> None:
    """
    Do not invent donors/recipients when no meaningful bend imbalance exists.
    """
    field, values = _field(bending)
    assert propose(field, values) is None


def test_search_box_boundary_and_stale_inputs_are_handled_without_geometry_relaxation() -> None:
    """
    Stay inside a saturated coefficient box and reject a field/coordinate mismatch.
    """
    field, values = _field((4 * math.pi, 4 * math.pi, 0, 0, 0))
    allocation = propose(field, values)
    assert allocation is not None
    assert max(abs(v) for v in allocation.proposed[:5]) <= 4 * math.pi
    with pytest.raises(ValueError, match="disagree"):
        propose(field, (0,) + values[1:])
    with pytest.raises(ValueError, match="near-limit"):
        propose(replace(field, bend_mapping=BendMapping.GLOBAL_SOFT), values)
    with pytest.raises(ValueError, match="finite"):
        propose(field, values[:-1] + (math.nan,))


def _neutral() -> tuple[EndpointCase, tuple[float, ...], CompatiblePath]:
    """
    Supply one complete straight control for continuation and resource-stop checks.
    """
    case = EndpointCase(
        "neutral",
        Vector3(0, 0, 0),
        Vector3(80, 0, 0),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
        19,
        1,
    )
    values = (0.0,) * 9 + (1.0,)
    original = broad_chart.integrate(case, values, 512, lambda: None)
    return case, values, original


def test_neutral_continuation_uses_registered_grid_and_preserves_fixed_pose() -> None:
    """
    Keep no-proposal continuation bounded and compatible with ordinary geometry.
    """
    case, values, original = _neutral()
    result, metrics = redistribute(case, original, values, lambda: None)
    assert metrics["allocation"] is None and metrics["evaluations"] <= 158
    assert result.states == original.states and result.rates == original.rates
    assert metrics["strict_endpoint_gate"]


def test_checkpoint_errors_propagate_without_retry_or_altered_targets() -> None:
    """
    Fail closed on resource stops before any allocation or fit work.
    """
    case, values, original = _neutral()

    def stopped() -> None:
        """
        Represent a caller-owned resource stop.
        """
        raise RuntimeError("resource stop")

    with pytest.raises(RuntimeError, match="resource stop"):
        redistribute(case, original, values, stopped)
