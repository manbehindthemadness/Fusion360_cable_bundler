"""
Verify the isolated approved action exception preserves all other budgets and restores on failure.
"""

from __future__ import annotations

from contextlib import nullcontext

import pytest

from artifacts.verification.resume3362.six_actions import installed
from experiments.experiment_ribbon_locked_solver import deferred_construction
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


@pytest.mark.parametrize("interrupted", (False, True))
def test_six_action_context_keeps_remaining_accounting_and_restores(interrupted: bool) -> None:
    """
    Neither a normal exit nor a failed diagnostic can enlarge the next ordinary allocation.
    """
    before = (Work.__post_init__.__code__, deferred_construction.recover.__code__)
    with pytest.raises(ValueError):
        Work(6, 2048, 0.4, 2)
    with (
        pytest.raises(RuntimeError, match="synthetic interruption")
        if interrupted
        else nullcontext()
    ):
        with installed():
            allocation = Work(6, 2048, 0.4, 2)
            remaining = allocation.remaining(
                updates=2, pairs=20, cpu_seconds=0.1, wall_seconds=0.1, newton_steps=3
            )
            assert remaining is not None and remaining.updates == 4
            assert remaining.newton_steps == 21 and remaining.pairs == 2028
            assert allocation.remaining(updates=6, pairs=0, cpu_seconds=0, wall_seconds=0) is None
            for values in (
                (7, 2048, 0.4, 2),
                (6, 2049, 0.4, 2),
                (6, 2048, 0.401, 2),
                (6, 2048, 0.4, 2.01),
            ):
                with pytest.raises(ValueError):
                    Work(*values)
            with pytest.raises(ValueError):
                Work(6, 2048, 0.4, 2, 25)
            if interrupted:
                raise RuntimeError("synthetic interruption")
    assert (Work.__post_init__.__code__, deferred_construction.recover.__code__) == before
    with pytest.raises(ValueError):
        Work(6, 2048, 0.4, 2)
