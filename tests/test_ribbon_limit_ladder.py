"""
Verify isolated limit changes keep one shared pool and cannot escape the frozen ladder.
"""

from __future__ import annotations

from contextlib import nullcontext

import pytest

from artifacts.verification.resume3364.limits import RUNGS, Limit, installed
from experiments.experiment_ribbon_locked_solver import deferred_construction
from experiments.experiment_ribbon_terminal_hardware import recovery_limits


@pytest.mark.parametrize("interrupted", (False, True))
@pytest.mark.parametrize("limit", RUNGS)
def test_limit_context_preserves_debits_and_restores(limit: Limit, interrupted: bool) -> None:
    """
    Changed ceilings never grant child renewals or leak into the next ordinary solve.
    """
    work_type = recovery_limits.Work
    before = (work_type.__post_init__.__code__, deferred_construction.recover.__code__)
    with pytest.raises(ValueError):
        work_type(limit.actions, limit.pairs, limit.cpu, 2)
    with pytest.raises(RuntimeError, match="interrupted") if interrupted else nullcontext():
        with installed(limit):
            allocation = work_type(limit.actions, limit.pairs, limit.cpu, 2)
            left = allocation.remaining(
                updates=1, pairs=17, cpu_seconds=0.1, wall_seconds=0.2, newton_steps=3
            )
            assert left is not None
            assert (left.updates, left.pairs, left.newton_steps) == (
                limit.actions - 1,
                limit.pairs - 17,
                21,
            )
            assert left.cpu_seconds == limit.cpu - 0.1 and left.wall_seconds == 1.8
            assert deferred_construction.CONTACT_PAIR_BUDGET == limit.pairs
            assert deferred_construction.MAXIMUM_CPU_SECONDS == limit.cpu
            for values in (
                (limit.actions + 1, limit.pairs, limit.cpu, 2, 24),
                (limit.actions, limit.pairs + 1, limit.cpu, 2, 24),
                (limit.actions, limit.pairs, limit.cpu + 0.01, 2, 24),
                (limit.actions, limit.pairs, limit.cpu, 2.01, 24),
                (limit.actions, limit.pairs, limit.cpu, 2, 25),
            ):
                with pytest.raises(ValueError):
                    work_type(*values)
            assert (
                allocation.remaining(updates=limit.actions, pairs=0, cpu_seconds=0, wall_seconds=0)
                is None
            )
            with pytest.raises(RuntimeError):
                with installed(limit):
                    pytest.fail("Nested override must refuse unknown runtime")
            if interrupted:
                raise RuntimeError("interrupted")
    assert (work_type.__post_init__.__code__, deferred_construction.recover.__code__) == before
    assert recovery_limits.MAXIMUM_CPU_SECONDS == deferred_construction.MAXIMUM_CPU_SECONDS == 0.4
    assert deferred_construction.CONTACT_PAIR_BUDGET == 2048
    work_type(4, 2048, 0.4, 2)
    with pytest.raises(ValueError):
        work_type(limit.actions, limit.pairs, limit.cpu, 2)


def test_unknown_rung_is_rejected() -> None:
    """
    Caller-provided values cannot silently enlarge the declared diagnostic ladder.
    """
    with pytest.raises(RuntimeError):
        with installed(Limit(10.0, 100, 100000)):
            pytest.fail("Unknown budget must not enter")
