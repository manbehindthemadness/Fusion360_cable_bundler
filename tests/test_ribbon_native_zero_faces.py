"""
Preserve absent slots when the original linear restoration gate proves them sufficient.
"""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import MaterialGuidance
from experiments.experiment_ribbon_terminal_hardware.native_slots import bind_proposal, zero_step
from experiments.experiment_ribbon_terminal_hardware.redistributed_projection import (
    GuidancePolicy,
    redistributed_step,
)
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate
from tests.test_ribbon_material_return import _witness
from tests.test_ribbon_native_slots import _Bounds


def test_zero_face_restores_caps_where_gratuitous_positive_floor_conflicts_with_hardware() -> None:
    """
    Solve an authored affine cap with an incidental tiny runway direction and a strict hardware row.
    """
    source = _Bounds(((0, 1), (-10, 10)))
    values = (0.0, 0.0)
    rows = [[1e-8, 1.0]] + [[0.0, 0.0] for _ in range(5)] + [[1.0, 0.0]]
    residual = (-1.0,) + (0.0,) * 5 + (-1e-6,)
    policy = GuidancePolicy.RESTORATION_MERIT
    first = redistributed_step(source, values, rows, residual, lambda: None, guidance_policy=policy)
    assert first is not None and 0 < first[0] < 1e-6
    positive = bind_proposal(source, values, frozenset({0}), first, 1e-5, 1.0)
    assert positive is not None
    assert (
        redistributed_step(positive, values, rows, residual, lambda: None, guidance_policy=policy)
        is None
    )
    selected = zero_step(values, frozenset({0}), first, rows, residual, policy)
    assert selected is not None and selected[0] == 0 and selected[1] == first[1]
    absent = bind_proposal(source, values, frozenset({0}), selected, 1e-5, 1.0)
    assert absent is not None and absent.frozen == frozenset({0})
    replacement = redistributed_step(
        absent, values, rows, residual, lambda: None, guidance_policy=policy
    )
    assert replacement is not None and replacement[0] == 0
    assert abs(residual[0] + replacement[1]) < 1
    assert replacement[0] - 1e-6 < 0


@pytest.mark.parametrize("policy", tuple(GuidancePolicy))
def test_positive_material_and_required_gap_are_not_silently_removed(
    policy: GuidancePolicy,
) -> None:
    """
    Existing material stays positive, and an essential new direction retains its native floor.
    """
    rows = [[-1.0, -1.0]] + [[0.0, 0.0] for _ in range(5)] + [[0.0, 0.0]]
    residual = (1.0,) + (0.0,) * 5 + (-1.0,)
    assert zero_step((0.0, 0.0), frozenset({0}), (1e-6, 0.0), rows, residual, policy) is None
    selected = zero_step((0.0, 1e-6), frozenset({0, 1}), (1e-6, -5e-7), rows, residual, policy)
    assert selected is None
    selected = zero_step((0.0, 1e-6), frozenset({0, 1}), (1e-6, 5e-7), rows, residual, policy)
    assert selected == (0.0, 5e-7)


@pytest.mark.parametrize("physical", (-1e-6, 0.0))
def test_zero_face_cannot_cross_a_satisfied_or_touching_linear_constraint(physical: float) -> None:
    """
    A descending cap correction cannot trade away an already valid physical halfspace.
    """
    rows = [[0.0, -1.0]] + [[0.0, 0.0] for _ in range(5)] + [[-1.0, 1e-3]]
    residual = (1.0,) + (0.0,) * 5 + (physical,)
    assert (
        zero_step(
            (0.0, 0.0),
            frozenset({0}),
            (1e-6, 0.5),
            rows,
            residual,
            GuidancePolicy.RESTORATION_MERIT,
        )
        is None
    )


def test_zero_selection_preserves_explicit_positive_guidance_policy() -> None:
    """
    Default guidance cannot worsen; explicit restoration may trade only below strict maximum descent.
    """
    rows = [[0.0, -1.0]] + [[0.0, 0.0] for _ in range(5)] + [[0.0, 1.0]]
    terms = (1.0,) + (0.0,) * 5 + (0.1,)
    args = ((0.0, 0.0), frozenset({0}), (1e-9, 0.5), rows, terms)
    assert zero_step(*args, GuidancePolicy.NONWORSENING) is None
    assert zero_step(*args, GuidancePolicy.RESTORATION_MERIT) == (0.0, 0.5)


def test_incomplete_or_nonfinite_retained_linear_data_is_rejected() -> None:
    """
    Never select a geometry face from mismatched derivatives or nonfinite coordinates.
    """
    for change, rows in ((float("nan"), [[1.0]] * 6), (1e-9, [[1.0, 0.0]] * 6)):
        with pytest.raises(ValueError, match="complete finite"):
            zero_step(
                (0.0,),
                frozenset({0}),
                (change,),
                rows,
                (1.0,) * 6,
                GuidancePolicy.RESTORATION_MERIT,
            )


def test_real_joint_preparation_selects_zero_in_the_same_replacement_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Retain two projection calls and zero geometry updates while observing the actual selected face.
    """
    source = _route((fold(2, 1.2, 1, 0, 1), Straight(2), fold(2, 1.2, -1, 0, 1)))
    calls: list[list[list[float]]] = []

    def derivative(
        _model: Any, values: tuple[float, ...], *_args: Any, **_kwargs: Any
    ) -> list[list[float]]:
        """
        Supply an independent affine cap direction with an incidental positive zero-slot increment.
        """
        row = [0.0] * len(values)
        row[0] = 1e-8
        row[1] = -1.0
        return [row] + [[0.0] * len(values) for _ in range(6)]

    def project(
        _model: Any,
        values: tuple[float, ...],
        rows: list[list[float]],
        _terms: tuple[float, ...],
        _check: Callable[[], None],
        **_kwargs: Any,
    ) -> tuple[float, ...] | None:
        """
        Choose one declining retained linear step, then stop before any nonlinear geometry update.
        """
        calls.append(rows)
        if len(calls) == 1:
            return tuple(1e-9 if i == 0 else 0.1 if i == 1 else 0.0 for i in range(len(values)))
        assert len(calls) == 2
        assert all(row[0] == 0 for row in rows)
        return None

    monkeypatch.setitem(vars(joint_contact), "joint_jacobian", derivative)
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", project)
    monkeypatch.setitem(vars(joint_contact), "ordered_caps_complete", Mock(return_value=False))

    def equations(
        _self: joint_contact.JointEvaluation, _values: tuple[float, ...]
    ) -> tuple[float, ...]:
        """
        Retain independently authored cap restoration and one satisfied inequality.
        """
        return (1.0,) + (0.0,) * 5 + (-1.0,)

    monkeypatch.setattr(joint_contact.JointEvaluation, "equations", equations)
    result = joint_contact.recover(
        source,
        _witness(0, 2, 0.5, 0.5),
        _gate(source),
        lambda: None,
        lambda _: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        mode=MaterialGuidance(0),
    )
    assert result is not None and len(calls) == 2
    assert result.detail["native_zero_face_selections"] == 1
    assert result.detail["newton_steps"] == result.detail["contact_pairs"] == 0
