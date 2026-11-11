"""
Restore already-invalid guidance without granting final acceptance or crossing satisfied linear rows.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import redistributed_projection as projection
from tests.test_ribbon_restoration_metric import _Box


def _terms(x: float) -> tuple[float, ...]:
    """
    Describe one authored nonlinear cap/guidance path with a known fully compliant endpoint.
    """
    return (1.0 - x,) + (0.0,) * 5 + (0.1 + x - 2 * x * x,)


def _merit(terms: tuple[float, ...]) -> float:
    """
    Measure the same maximum cap/positive-guidance residual as the actual recovery entry.
    """
    return max(*(abs(value) for value in terms[:6]), *(max(0.0, value) for value in terms[6:]))


def test_invalid_guidance_tradeoff_reaches_known_compliance_within_original_update_limits() -> None:
    """
    Per-row monotonicity stalls at x0; strict maximum descent completes the independent nonlinear path.
    """
    rows = [[-1.0]] + [[0.0] for _ in range(5)] + [[1.0]]
    assert projection.redistributed_step(_Box(1.0), (0.0,), rows, _terms(0.0), lambda: None) is None
    x, updates = 0.0, 0
    evidence = projection.ProjectionEvidence()
    guidance_increased = False
    for _ in range(24):
        before = _terms(x)
        if _merit(before) < 1e-13:
            break
        rows[-1] = [1.0 - 4 * x]
        step = projection.redistributed_step(
            _Box(1.0),
            (x,),
            rows,
            before,
            lambda: None,
            guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
            evidence=evidence,
        )
        assert step is not None
        for halving in range(4):
            candidate = x + step[0] * 0.5**halving
            after = _terms(candidate)
            if _merit(after) < _merit(before):
                guidance_increased |= after[-1] > before[-1] > 0
                assert 0 <= candidate <= 1
                x, updates = candidate, updates + 1
                break
        else:
            raise AssertionError(
                "Authored restoration must satisfy the original four-trial descent gate"
            )
    assert x == 1.0 and _terms(x)[0] == 0 and _terms(x)[-1] < 0
    assert updates <= 6 and guidance_increased and evidence.guidance_tradeoff_proposals > 0


@pytest.mark.parametrize("physical", (0.0, -0.1))
def test_touching_and_satisfied_guidance_keep_their_original_hard_linear_gate(
    physical: float,
) -> None:
    """
    Permission for an invalid row cannot leak into a different satisfied or touching row.
    """
    rows = [[-1.0]] + [[0.0] for _ in range(5)] + [[1.0], [1.0]]
    residual = (1.0,) + (0.0,) * 5 + (0.1, physical)
    step = projection.redistributed_step(
        _Box(1.0),
        (0.0,),
        rows,
        residual,
        lambda: None,
        guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
    )
    if physical == 0:
        assert step is None
    else:
        assert step is not None and 0 < step[0] <= -physical + 1e-14
        assert physical + step[0] <= 1e-14


@pytest.mark.parametrize("sensitivity", (0.001, 0.1, 1.0))
def test_no_invalid_guidance_preserves_the_exact_original_projection(sensitivity: float) -> None:
    """
    Existing successful clear-guidance arithmetic stays bit-identical under the explicit policy.
    """
    rows = [[-sensitivity]] + [[0.0] for _ in range(6)]
    residual = (0.05,) + (0.0,) * 5 + (-1.0,)
    default = projection.redistributed_step(_Box(), (0.0,), rows, residual, lambda: None)
    restored = projection.redistributed_step(
        _Box(),
        (0.0,),
        rows,
        residual,
        lambda: None,
        guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
    )
    assert restored == default


@pytest.mark.parametrize("unfinished", (False, True))
@pytest.mark.parametrize("offered", (0.3, 0.95))
def test_checked_and_unfinished_proposals_still_require_strict_maximum_merit_descent(
    monkeypatch: pytest.MonkeyPatch,
    unfinished: bool,
    offered: float,
) -> None:
    """
    No retained working vector may grow the maximum residual or bypass the original box.
    """

    def project(*_args: object, **kwargs: object) -> tuple[float, ...] | None:
        """
        Supply one controlled vector from the existing single constrained projection.
        """
        values = (offered,) + (0.0,) * 7
        if unfinished:
            receipt = kwargs["unfinished"]
            assert isinstance(receipt, projection.UnfinishedProjection)
            receipt.step, receipt.stop_reason = values, "working_set_limit"
            return None
        return values

    projector = Mock(side_effect=project)
    monkeypatch.setitem(vars(projection), "active_step", projector)
    evidence = projection.ProjectionEvidence()
    result = projection.redistributed_step(
        _Box(1.0),
        (0.0,),
        [[-1.0]] + [[0.0] for _ in range(5)] + [[1.0]],
        _terms(0.0),
        lambda: None,
        guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
        evidence=evidence,
    )
    assert (result is not None) == (offered == 0.3)
    assert evidence.guidance_tradeoff_proposals == int(offered == 0.3)
    projector.assert_called_once()
    assert (
        len(projector.call_args.args[1]) == 8
    )  # Original one geometry + seven numerical coordinates.


def test_policy_requires_an_explicit_type_and_preserves_cancellation() -> None:
    """
    Malformed policy or a hard stop never enables an uncharged alternative projection.
    """
    bad_policy: Any = "restoration_merit"
    with pytest.raises(ValueError, match="explicit guidance"):
        projection.redistributed_step(
            _Box(), (0.0,), [[1.0]] * 7, _terms(0.0), lambda: None, guidance_policy=bad_policy
        )
    with pytest.raises(TimeoutError, match="original stop"):
        projection.redistributed_step(
            _Box(),
            (0.0,),
            [[1.0]] * 7,
            _terms(0.0),
            Mock(side_effect=TimeoutError("original stop")),
            guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
        )
