"""
Reuse exact flat-material dependencies while retaining complete coordinate validation.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, unit
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, locate
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_terminal_hardware import flat_separation
from experiments.experiment_ribbon_terminal_hardware.flat_separation import FlatPart, FlatSeparation
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import jacobian
from tests.test_ribbon_feature_geometry_reuse import _plane
from tests.test_ribbon_flat_contact import load_routes


def test_historical_geometry_entry_point_remains_retired() -> None:
    """
    Prevent consumer checks from silently returning saved geometry to active solver or proof scope.
    """
    with pytest.raises(pytest.skip.Exception, match="retired"):
        load_routes()


def _constraint(phase: FlatPhase = FlatPhase.AFTER) -> FlatSeparation:
    """
    Bind independent leading-straight and second-fold flat regions on an authored four-fold route.
    """
    model = _plane().model
    width = model.original.half_width_mm
    return FlatSeparation(
        model,
        (Region(0, True), Region(1, False)),
        (FlatPart(FlatPhase.STRAIGHT, -width, width, 0.5), FlatPart(phase, -width, width, 0.5)),
        unit(Vector3(1, 2, 3)),
    )


def _raw(bound: FlatSeparation, values: tuple[float, ...], side: Side) -> float:
    """
    Evaluate the original complete-region span and gap arithmetic without dependency reuse.
    """
    pieces = bound.model.pieces(values)
    first, second = tuple(
        flat_separation.flat_span(locate(bound.model.original, pieces, tag), part, bound.axis)
        for tag, part in zip(bound.pair, bound.parts)
    )
    gap = second[0] - first[1] if side is Side.BEFORE else first[0] - second[1]
    return gap / bound.model.scale


@pytest.mark.parametrize("side", tuple(Side))
@pytest.mark.parametrize("phase", (FlatPhase.BEFORE, FlatPhase.AFTER))
def test_suffix_probes_reuse_only_the_unchanged_actual_material_members(
    monkeypatch: pytest.MonkeyPatch, side: Side, phase: FlatPhase
) -> None:
    """
    Preserve every raw gap while unrelated downstream motion avoids repeated projection.
    """
    bound = _constraint(phase)
    values = bound.model.initial
    probes = [values] + [
        values[:index] + (values[index] + delta,) + values[index + 1 :]
        for index in range(6, len(values))
        for delta in (-1e-5, 1e-5)
    ]
    expected = [_raw(bound, probe, side) for probe in probes]
    projected = Mock(wraps=flat_separation.flat_span)
    monkeypatch.setitem(vars(flat_separation), "flat_span", projected)
    assert [bound.gap(probe, side) for probe in probes] == expected
    assert projected.call_count == 2


def test_entire_cap_and_material_derivative_matrix_stays_exact_with_less_projection_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep original derivative probes, raw cap rows and both complete material-side inequalities.
    """
    bound = _constraint()
    model = bound.model

    def raw(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Supply the original validated cap and material equations.
        """
        return model.residual(values) + tuple(_raw(bound, values, side) for side in Side)

    def reused(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Change only identical flat-span reuse within the same equations.
        """
        return model.residual(values) + tuple(bound.gap(values, side) for side in Side)

    projected = Mock(wraps=flat_separation.flat_span)
    monkeypatch.setitem(vars(flat_separation), "flat_span", projected)
    expected = jacobian(
        model, model.initial, raw, 8, frozenset(), lambda: None, admissible=model.admissible
    )
    original_calls = projected.call_count
    projected.reset_mock()
    measured = jacobian(
        model, model.initial, reused, 8, frozenset(), lambda: None, admissible=model.admissible
    )
    assert measured == expected
    assert projected.call_count < original_calls


@pytest.mark.parametrize("index", range(6))
def test_changed_placement_or_material_requires_new_exact_region_bounds(
    monkeypatch: pytest.MonkeyPatch, index: int
) -> None:
    """
    Recompute only the members changed by leading travel, bend angles, banks or intervening travel.
    """
    bound = _constraint()
    values = bound.model.initial
    changed = values[:index] + (values[index] + 1e-5,) + values[index + 1 :]
    expected = _raw(bound, changed, Side.BEFORE)
    bound.gap(values, Side.BEFORE)
    projected = Mock(wraps=flat_separation.flat_span)
    monkeypatch.setitem(vars(flat_separation), "flat_span", projected)
    assert bound.gap(changed, Side.BEFORE) == expected
    assert projected.call_count == (2 if index == 0 else 1)


def test_both_sides_share_bounds_but_other_axes_parts_and_models_do_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Share only raw spans within the same fixed constraint, retaining side-specific gap arithmetic.
    """
    bound = _constraint()
    values = bound.model.initial
    expected = _raw(bound, values, Side.AFTER)
    variants = (
        replace(bound, axis=unit(Vector3(-2, 1, 3))),
        replace(bound, parts=(replace(bound.parts[0], low_q=-0.3), bound.parts[1])),
        replace(bound, model=_plane().model),
    )
    variant_values = [_raw(other, values, Side.AFTER) for other in variants]
    bound.gap(values, Side.BEFORE)
    projected = Mock(wraps=flat_separation.flat_span)
    monkeypatch.setitem(vars(flat_separation), "flat_span", projected)
    assert bound.gap(values, Side.AFTER) == expected and projected.call_count == 0
    for other, expected_other in zip(variants, variant_values):
        projected.reset_mock()
        assert other.gap(values, Side.AFTER) == expected_other
        assert projected.call_count == 2


def test_invalid_unrelated_suffix_cannot_bypass_complete_model_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reject a negative far-end slot before cached early-member bounds can be consulted.
    """
    bound = _constraint()
    values = bound.model.initial
    bound.gap(values, Side.BEFORE)
    projected = Mock(wraps=flat_separation.flat_span)
    monkeypatch.setitem(vars(flat_separation), "flat_span", projected)
    with pytest.raises(ValueError, match="declared bounds"):
        bound.gap(values[:-1] + (-1.0,), Side.AFTER)
    projected.assert_not_called()


def test_dependency_retention_is_bounded_and_eviction_recomputes_exact_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Evict original members after more than64distinct region keys without changing their recomputed gap.
    """
    bound = _constraint()
    values = bound.model.initial
    expected = _raw(bound, values, Side.AFTER)
    bound.gap(values, Side.BEFORE)
    for index in range(1, 35):
        changed = (values[0] + index * 1e-4,) + values[1:]
        bound.gap(changed, Side.BEFORE)
    projected = Mock(wraps=flat_separation.flat_span)
    monkeypatch.setitem(vars(flat_separation), "flat_span", projected)
    assert bound.gap(values, Side.AFTER) == expected
    assert projected.call_count == 2
