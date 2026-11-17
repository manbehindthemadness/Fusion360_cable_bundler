"""
Check that both diagnostic recovery branches retain their defaults after normal and failed exits.
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from artifacts.verification.resume3364.limits import RUNGS
from artifacts.verification.resume3367.limits import installed
from experiments.experiment_ribbon_locked_solver import branch_recovery, initial_closure
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


@pytest.mark.parametrize("interrupted", (False, True))
def test_initial_and_deferred_limits_restore(tmp_path: Path, interrupted: bool) -> None:
    """
    Added initial-closure ceilings cannot escape the isolated attempt or renew child work.
    """
    before = initial_closure.recover.__code__
    alias = branch_recovery.recover_initial_closure
    limit = RUNGS[3]
    with pytest.raises(RuntimeError, match="interrupted") if interrupted else nullcontext():
        with installed(limit, tmp_path):
            assert initial_closure.MAXIMUM_CPU_SECONDS == 1.6
            assert initial_closure.CONTACT_PAIR_BUDGET == 8192
            assert branch_recovery.recover_initial_closure is not alias
            work = Work(8, 8192, 1.6, 2)
            left = work.remaining(
                updates=3, pairs=1024, cpu_seconds=0.6, wall_seconds=0.5, newton_steps=8
            )
            assert left is not None
            assert (left.updates, left.pairs, left.newton_steps, left.cpu_seconds) == (
                5,
                7168,
                16,
                1.0,
            )
            if interrupted:
                raise RuntimeError("interrupted")
    assert initial_closure.recover.__code__ is before
    assert branch_recovery.recover_initial_closure is alias
    assert initial_closure.MAXIMUM_CPU_SECONDS == 0.4
    assert initial_closure.CONTACT_PAIR_BUDGET == 2048
    with pytest.raises(ValueError):
        Work(8, 8192, 1.6, 2)
