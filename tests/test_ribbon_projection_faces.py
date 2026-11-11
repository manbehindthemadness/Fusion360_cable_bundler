"""
Preserve selected bound identity through scaled projection without deleting interior material.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import active_projection as active
from experiments.experiment_ribbon_terminal_hardware import redistributed_projection as projection
from experiments.experiment_ribbon_terminal_hardware.native_slots import bind_proposal
from tests.test_ribbon_native_slots import _Bounds


@pytest.mark.parametrize("gradient", (0.3, 1.1))
def test_selected_zero_face_survives_rescaling_without_a_false_positive_native_floor(
    gradient: float,
) -> None:
    """
    Reproduce positive roundoff on a solved lower face with an independent two-coordinate system.
    """
    domain = _Bounds(((0.0, 10.0), (0.0, 10.0)))
    rows = [[1.0, gradient]] + [[0.0, 0.0] for _ in range(5)] + [[0.0, -1.0]]
    terms = (1.0,) + (0.0,) * 5 + (0.1,)
    values = (0.1, 0.2)
    evidence = projection.ProjectionEvidence()
    result = projection.redistributed_step(
        domain, values, rows, terms, lambda: None, evidence=evidence
    )
    assert result is not None and values[0] + result[0] == 0.0
    assert evidence.active_face_restorations == 1
    assert terms[0] + result[0] + gradient * result[1] < terms[0]
    assert terms[-1] - result[1] <= terms[-1]
    native = bind_proposal(domain, values, frozenset({0}), result, 1e-5, 1.0)
    assert native is not None and native.frozen == frozenset({0}) and not native.positive


@pytest.mark.parametrize("upper", (False, True))
def test_face_receipt_observes_the_completed_working_set_without_changing_the_vector(
    upper: bool,
) -> None:
    """
    Identify either original coordinate boundary while preserving the projector's exact arithmetic.
    """
    domain = _Bounds(((0.0, 1.0), (-10.0, 10.0)))
    rows = [[1.0, 1.0]] + [[0.0, 0.0] for _ in range(6)]
    terms = ((-4.0 if upper else 4.0),) + (0.0,) * 5 + (-1.0,)
    values = (0.5, 0.0)
    expected = active.active_step(domain, values, rows, terms, lambda: None)
    faces = active.ActiveFaces()
    actual = active.active_step(domain, values, rows, terms, lambda: None, faces=faces)
    assert actual == expected and actual is not None
    assert faces.lower == (frozenset() if upper else frozenset({0}))
    assert faces.upper == (frozenset({0}) if upper else frozenset())


def test_stale_face_evidence_is_cleared_on_inconsistency_and_cancellation() -> None:
    """
    A failed or interrupted projection cannot authorize subsequent restoration of a previous bound.
    """
    faces = active.ActiveFaces(frozenset({0}), frozenset({1}))
    rows = [[1.0], [1.0]] + [[0.0] for _ in range(5)]
    terms = (1.0, 2.0) + (0.0,) * 5
    assert active.active_step(_Bounds(), (0.0,), rows, terms, lambda: None, faces=faces) is None
    assert not faces.lower and not faces.upper
    faces.lower = frozenset({0})
    with pytest.raises(TimeoutError, match="original stop"):
        active.active_step(
            _Bounds(),
            (0.0,),
            rows,
            terms,
            Mock(side_effect=TimeoutError("original stop")),
            faces=faces,
        )
    assert not faces.lower and not faces.upper


@pytest.mark.parametrize("unfinished", (False, True))
def test_tiny_positive_target_without_completed_face_identity_is_not_zeroed(
    monkeypatch: pytest.MonkeyPatch, unfinished: bool
) -> None:
    """
    Interior positive material and uncertified vectors retain the existing native-floor decision.
    """
    offered = (2e-15, 0.5) + (0.0,) * 7

    def project(*_args: object, **kwargs: object) -> tuple[float, ...] | None:
        """
        Offer a tiny interior coordinate with no selected boundary identity.
        """
        if unfinished:
            receipt = kwargs["unfinished"]
            assert isinstance(receipt, active.UnfinishedProjection)
            receipt.step, receipt.stop_reason = offered, "working_set_limit"
            return None
        return offered

    projector = Mock(side_effect=project)
    monkeypatch.setitem(vars(projection), "active_step", projector)
    domain = _Bounds(((0.0, 10.0), (0.0, 10.0)))
    rows = [[0.0, -1.0]] + [[0.0, 0.0] for _ in range(6)]
    result = projection.redistributed_step(
        domain, (0.0, 0.0), rows, (1.0,) + (0.0,) * 5 + (-1.0,), lambda: None
    )
    assert result is not None and result[0] == offered[0]
    native = bind_proposal(domain, (0.0, 0.0), frozenset({0}), result, 1e-5, 1.0)
    assert native is not None and native.positive == frozenset({0})
    projector.assert_called_once()


def test_halfspace_contraction_can_legitimately_leave_the_selected_zero_face(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep the original common ray contraction instead of forcing a zero endpoint through clearance.
    """

    def project(*_args: object, **kwargs: object) -> tuple[float, ...]:
        """
        Retain one completed lower face before the independently necessary physical ray contraction.
        """
        faces = kwargs["faces"]
        assert isinstance(faces, active.ActiveFaces)
        faces.lower = frozenset({0})
        return (-0.1, 0.5) + (0.0,) * 7

    projector = Mock(side_effect=project)
    monkeypatch.setitem(vars(projection), "active_step", projector)
    rows = [[1.0, -1.0]] + [[0.0, 0.0] for _ in range(5)] + [[-1.0, 0.0]]
    terms = (1.0,) + (0.0,) * 5 + (-0.05,)
    result = projection.redistributed_step(
        _Bounds(((0.0, 10.0), (0.0, 10.0))), (0.1, 0.2), rows, terms, lambda: None
    )
    assert result is not None and 0.0 < 0.1 + result[0] < 0.1
    assert terms[-1] - result[0] <= 1e-14
    assert result[1] == pytest.approx(-5.0 * result[0])
    projector.assert_called_once()
