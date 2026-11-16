"""
Verify exact shared-vertex cap labels, physical relabelling bounds and topology-preserving rejection.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_cap_chain import (
    CapEndpointEvidence,
    conform,
    orient_endpoints,
    parameter_discrepancy,
)
from experiments.experiment_ribbon_complete.native_cap_material import CapMaterialBinding, bind
from tests.test_ribbon_complete_native_cap_material import native, sources
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def chain(
    reverse: bool = False, epsilon: Fraction = Fraction(1, 100000)
) -> tuple[CapMaterialBinding, ...]:
    """
    Keep two native half-curves while existing label intervals contain a small overlap and endpoint tail.
    """
    pair = sources()
    first = native((Fraction(0), Fraction(1, 2)), Fraction(2))
    second = replace(native((Fraction(1, 2), Fraction(1)), Fraction(3)), edge_id=2)
    if reverse:
        second = replace(
            second,
            controls=tuple(reversed(second.controls)),
            weights=tuple(reversed(second.weights)),
        )
    intervals = (
        (Fraction(0), Fraction(1, 2) + epsilon),
        (Fraction(1, 2) - epsilon, Fraction(1) - epsilon),
    )
    return tuple(
        bind(curve, pair, interval, "revision", checkpoint)
        for curve, interval in zip((first, second), intervals)
    )


def observations(
    original: tuple[CapMaterialBinding, ...], vertices: tuple[tuple[int, int], ...]
) -> tuple[CapEndpointEvidence, ...]:
    """
    Bind explicitly supplied mock vertex identities to the original converted-curve endpoints.
    """
    return tuple(
        orient_endpoints(b.native, ids, (b.native.controls[0], b.native.controls[-1]), checkpoint)
        for b, ids in zip(original, vertices)
    )


@pytest.mark.parametrize("reverse", (False, True))
def test_native_vertex_chain_produces_exact_shared_profile_labels_without_geometry_changes(
    reverse: bool,
) -> None:
    """
    Complete original0/1 coverage and identical q/b at the common native vertex survive parameter reversal.
    """
    original = chain(reverse)
    first, second = original
    first_points = first.native.controls[0], first.native.controls[-1]
    second_points = (
        (second.native.controls[-1], second.native.controls[0])
        if reverse
        else (second.native.controls[0], second.native.controls[-1])
    )
    endpoints = (
        orient_endpoints(first.native, (10, 11), first_points, checkpoint),
        orient_endpoints(second.native, (11, 12), second_points, checkpoint),
    )
    result = conform(original, endpoints, (Fraction(1), Fraction(-2)), checkpoint)
    assert result.status == "qualified_conforming_cap_material_chain"
    assert result.vertex_labels == ((10, Fraction(0)), (11, Fraction(1, 2)), (12, Fraction(1)))
    a, b = (binding.mapping for binding in result.bindings)
    assert a is not None and b is not None
    assert a.profile_coordinates(Fraction(1)) == b.profile_coordinates(Fraction(int(reverse)))
    assert all(new.native is prior.native for new, prior in zip(result.bindings, original))
    assert original[1].interval[-1] < Fraction(1)
    assert result.accuracy_upper_mm is not None and result.accuracy_upper_mm <= Fraction(1, 100)
    assert all(error > 0 for error in result.relabel_upper_mm)
    for prior, current in zip(original, result.bindings):
        assert prior.mapping is not None and current.mapping is not None
        bound = parameter_discrepancy(prior.mapping, current.mapping)
        assert all(
            abs(
                prior.mapping.parameter(Fraction(i, 10))
                - current.mapping.parameter(Fraction(i, 10))
            )
            <= bound
            for i in range(11)
        )


def test_matching_positions_cannot_weld_foreign_native_vertices() -> None:
    """
    Coordinate coincidence cannot replace actual native endpoint identity.
    """
    original = chain()
    endpoints = observations(original, ((10, 11), (99, 12)))
    result = conform(original, endpoints, (Fraction(0), Fraction(0)), checkpoint)
    assert result.status == "unresolved_native_cap_chain_order" and result.accuracy_upper_mm is None


def test_small_dimensionless_label_change_can_exceed_physical_material_accuracy() -> None:
    """
    An original large cut slope magnifies an otherwise small V relabelling into a measured s error.
    """
    original = chain()
    endpoints = observations(original, ((10, 11), (11, 12)))
    result = conform(original, endpoints, (Fraction(10000), Fraction(0)), checkpoint)
    assert result.status == "unresolved_conforming_cap_accuracy"
    assert result.accuracy_upper_mm is not None and result.accuracy_upper_mm > Fraction(1, 100)


def test_endpoint_ambiguity_and_stale_curve_identity_remain_unresolved_or_rejected() -> None:
    """
    A collapsed curve cannot select endpoint identity, and an equal clone cannot reuse old endpoint receipts.
    """
    original = chain()
    curve = original[0].native
    collapsed = replace(curve, controls=((Fraction(0),) * 3,) * 3)
    missing = orient_endpoints(collapsed, (10, 11), ((Fraction(0),) * 3,) * 2, checkpoint)
    assert missing.ordered_vertices is None and missing.upper_mm is None
    endpoints = observations(original, ((10, 11), (11, 12)))
    stale = replace(endpoints[0], native=replace(curve))
    with pytest.raises(ValueError, match="owned endpoint"):
        conform(original, (stale, endpoints[1]), (Fraction(0), Fraction(0)), checkpoint)


def test_chain_requalification_obeys_the_callers_resource_stop() -> None:
    """
    Stop during chain traversal without returning a completed label partition.
    """
    original = chain()
    endpoints = observations(original, ((10, 11), (11, 12)))
    calls = 0

    def stop() -> None:
        """
        Reject the allocation while traversing the second original curve.
        """
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("caller stop")

    with pytest.raises(RuntimeError, match="caller stop"):
        conform(original, endpoints, (Fraction(0), Fraction(0)), stop)
