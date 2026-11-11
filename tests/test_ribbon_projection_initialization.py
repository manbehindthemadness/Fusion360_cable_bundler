"""
Verify grouped bound entry against known feasible systems and independent dual guards.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from itertools import combinations
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_terminal_hardware import active_projection as active
from experiments.experiment_ribbon_terminal_hardware import projection_initialization as initial
from experiments.experiment_ribbon_terminal_hardware import redistributed_projection as restoration


@dataclass(frozen=True)
class _Orthant:
    """
    Supply either nonnegative or nonpositive independent geometric coordinates.
    """

    upper: bool = False
    free_coordinate: int | None = None

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Retain the orthant, optionally leaving one explicitly named coordinate free.
        """
        if index == self.free_coordinate:
            return -math.inf, math.inf
        return (-math.inf, 0.0) if self.upper else (0.0, math.inf)


@pytest.mark.parametrize("count", (2, 15, 16, 17, 20))
@pytest.mark.parametrize("upper", (False, True))
def test_grouped_coordinate_entry_reaches_the_known_minimum_with_one_seed(
    count: int, upper: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Solve beyond16individual faces with fewer Gram solves and no additional update allowance.
    """
    sign = -1.0 if upper else 1.0
    rows = [[-sign] * count + [1.0]] + [[0.0] * (count + 1) for _ in range(6)]
    terms = (-1.0,) + (0.0,) * 5 + (-1.0,)
    model = _Orthant(upper, count)
    values = (0.0,) * (count + 1)
    empty = active.active_step(model, values, rows, terms, lambda: None)
    if count > 16:
        assert empty is None
    solves = Mock(wraps=vars(active)["_solve"])
    monkeypatch.setitem(vars(active), "_solve", solves)
    evidence = initial.InitializationEvidence()
    faces = active.ActiveFaces()
    step = active.active_step(
        model,
        values,
        rows,
        terms,
        lambda: None,
        initialization=initial.Initialization.COORDINATE_FACES,
        initialization_evidence=evidence,
        faces=faces,
    )
    assert step is not None
    assert solves.call_count == 1 and evidence.attempts == 1 and evidence.faces == count
    assert (faces.upper if upper else faces.lower) == frozenset(range(count))
    predicted = tuple(
        r + math.fsum(a * b for a, b in zip(row, step)) for row, r in zip(rows, terms)
    )
    assert max(map(abs, predicted[:6])) <= 1e-14 and predicted[-1] < 0
    assert step == pytest.approx((0.0,) * count + (1.0,), abs=1e-13)


def test_later_physical_constraint_can_release_an_initial_coordinate_face() -> None:
    """
    A seed supplies no permanent pins or permission to ignore another physical inequality.
    """
    rows = [[-1.0, -1.0, 1.0]] + [[0.0] * 3 for _ in range(5)] + [[-1.0, 0.0, 0.0]]
    terms = (-1.0,) + (0.0,) * 5 + (0.2,)
    faces = active.ActiveFaces()
    step = active.active_step(
        _Orthant(),
        (0.0,) * 3,
        rows,
        terms,
        lambda: None,
        initialization=initial.Initialization.COORDINATE_FACES,
        faces=faces,
    )
    assert step is not None
    assert faces.lower == frozenset({1}) and 0.2 - step[0] <= 1e-14
    assert step == pytest.approx((0.2, 0.0, 1.2), abs=1e-14)


def test_grouped_entry_matches_independent_subset_enumeration_on_small_coupled_systems() -> None:
    """
    Preserve minimum-norm corrections when physical inequalities release or retain initial faces.
    """
    rng = random.Random(931824)
    model = _Orthant()
    for _ in range(32):
        x, y = rng.uniform(0.1, 2), rng.uniform(0.1, 2)
        witness = (x, y, 1 + x + y)
        rows = [[-1.0, -1.0, 1.0]] + [[0.0] * 3 for _ in range(5)]
        physical = [[rng.uniform(-1, 1) for _ in range(3)] for _ in range(2)]
        rows += physical
        terms = (
            (-1.0,)
            + (0.0,) * 5
            + tuple(-math.fsum(a * b for a, b in zip(row, witness)) - 0.1 for row in physical)
        )
        expected = _enumerated_minimum(rows, terms)
        evidence = initial.InitializationEvidence()
        measured = active.active_step(
            model,
            (0.0,) * 3,
            rows,
            terms,
            lambda: None,
            initialization=initial.Initialization.COORDINATE_FACES,
            initialization_evidence=evidence,
        )
        assert measured is not None and expected is not None
        assert measured == pytest.approx(expected, abs=2e-10)
        assert evidence.faces == 2


def _enumerated_minimum(rows: list[list[float]], terms: tuple[float, ...]) -> tuple[float, ...]:
    """
    Enumerate all physical and coordinate active subsets in the independent three-coordinate oracle.
    """
    inequalities = rows[6:] + [[-float(i == j) for j in range(3)] for i in range(3)]
    right = [-value for value in terms[6:]] + [0.0] * 3
    candidates: list[tuple[float, ...]] = []
    for count in range(len(inequalities) + 1):
        for indices in combinations(range(len(inequalities)), count):
            result = affine_projection(
                rows[:6] + [inequalities[i] for i in indices],
                [-value for value in terms[:6]] + [right[i] for i in indices],
                [0.0] * 3,
            )
            if result is not None and all(
                math.fsum(a * b for a, b in zip(row, result)) <= bound + 1e-12
                for row, bound in zip(inequalities, right)
            ):
                candidates.append(tuple(result))
    assert candidates
    return min(candidates, key=lambda vector: math.fsum(value * value for value in vector))


@pytest.mark.parametrize("failure", ("singular", "negative_dual", "inaccurate", "nonfinite"))
def test_seed_declines_without_certifying_unchecked_or_dual_infeasible_vectors(
    failure: str,
) -> None:
    """
    Independently reject every invalid initialization instead of relaxing the original solve.
    """
    constraints = [([1.0, 0.0], -1.0, 1e-14), ([0.0, 1.0], -1.0, 1e-14)]
    offered = {
        "singular": None,
        "negative_dual": [-1.0, 1.0],
        "inaccurate": [0.5, 1.0],
        "nonfinite": [math.inf, 1.0],
    }[failure]
    solve = Mock(return_value=offered)
    seed = initial.coordinate_seed(constraints, [0, 1], solve, active._dot, lambda: None)
    assert seed is None and solve.call_count == 1


def test_declined_seed_consumes_the_first_original_update_and_cannot_renew_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A failed seed leaves only15ordinary updates and an uncertified exhaustion receipt.
    """
    count = 16
    rows = [[-1.0] * count + [1.0]] + [[0.0] * (count + 1) for _ in range(6)]
    seed = Mock(return_value=None)
    monkeypatch.setitem(vars(active), "coordinate_seed", seed)
    receipt = active.UnfinishedProjection()
    result = active.active_step(
        _Orthant(),
        (0.0,) * (count + 1),
        rows,
        (-1.0,) + (0.0,) * 5 + (-1.0,),
        lambda: None,
        initialization=initial.Initialization.COORDINATE_FACES,
        unfinished=receipt,
    )
    assert result is None and receipt.stop_reason == "working_set_limit"
    seed.assert_called_once()


def test_seed_checkpoint_cancellation_and_stale_receipt_clearing() -> None:
    """
    Interrupt preparation before a Gram solve and reset receipts before validating policy.
    """
    constraints = [([1.0, 0.0], -1.0, 1e-14), ([0.0, 1.0], -1.0, 1e-14)]
    solve = Mock()
    with pytest.raises(InterruptedError, match="source"):
        initial.coordinate_seed(
            constraints, [0, 1], solve, active._dot, Mock(side_effect=InterruptedError("source"))
        )
    solve.assert_not_called()
    receipt = initial.InitializationEvidence(5, 10)
    with pytest.raises(ValueError, match="explicit"):
        active.active_step(
            _Orthant(),
            (0.0,),
            [[0.0]] * 7,
            (0.0,) * 7,
            lambda: None,
            initialization=True,  # type: ignore[arg-type]
            initialization_evidence=receipt,
        )
    assert receipt == initial.InitializationEvidence()


@pytest.mark.parametrize("policy", tuple(restoration.GuidancePolicy))
def test_only_explicit_restoration_selects_grouped_initialization_and_reports_usage(
    monkeypatch: pytest.MonkeyPatch, policy: restoration.GuidancePolicy
) -> None:
    """
    Retain original standalone initialization and aggregate actual seeded faces on the opted-in path.
    """
    projector = Mock(wraps=active.active_step)
    monkeypatch.setitem(vars(restoration), "active_step", projector)
    rows = [[-1.0, -1.0, 1.0]] + [[0.0] * 3 for _ in range(6)]
    evidence = restoration.ProjectionEvidence()
    step = restoration.redistributed_step(
        _Orthant(),
        (0.0,) * 3,
        rows,
        (-1.0,) + (0.0,) * 5 + (-1.0,),
        lambda: None,
        guidance_policy=policy,
        evidence=evidence,
    )
    assert step is not None
    opted_in = policy is restoration.GuidancePolicy.RESTORATION_MERIT
    assert projector.call_args.kwargs["initialization"] is (
        initial.Initialization.COORDINATE_FACES if opted_in else initial.Initialization.EMPTY
    )
    assert evidence.coordinate_seed_attempts == int(opted_in)
    assert evidence.coordinate_seed_faces == 2 * int(opted_in)
    projector.assert_called_once()
