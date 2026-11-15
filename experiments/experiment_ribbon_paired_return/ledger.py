"""
Debit paired-branch actions and proofs inside one nonrenewable experimental allocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, process_time
from typing import Callable

from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


class Exhausted(RuntimeError):
    """
    Stop optional prototype work without masking caller cancellation or host errors.
    """


@dataclass
class Ledger:
    """
    Keep root reservations, started actions and completed comparisons on original clocks.

    Two roots are debited before each balanced factorization, even if it later
    degenerates or raises. Actual returned roots are reported separately; no
    unsuccessful reservation is refunded. External checkpoint failures propagate.
    """

    work: Work
    maximum_roots: int
    external: Callable[[], None]
    updates: int = 0
    roots: int = 0
    derived_roots: int = 0
    pairs: int = 0
    newton_steps: int = 0
    action_newton: int = 0

    def __post_init__(self) -> None:
        """
        Validate the original root pool and begin clocks before any action preparation.
        """
        if type(self.maximum_roots) is not int or not 0 <= self.maximum_roots <= 8:
            raise ValueError("Use zero to eight genuinely remaining roots")
        if any(
            value != 0
            for value in (
                self.updates,
                self.roots,
                self.derived_roots,
                self.pairs,
                self.newton_steps,
                self.action_newton,
            )
        ):
            raise ValueError("Start a new ledger with no invented completed work")
        self.cpu_started = process_time()
        self.wall_started = perf_counter()

    def checkpoint(self) -> None:
        """
        Enforce the same original clocks around every preparation, projection and proof.
        """
        self.external()
        if self.cpu_seconds >= self.work.cpu_seconds or self.wall_seconds >= self.work.wall_seconds:
            raise Exhausted("phase_budget")

    @property
    def cpu_seconds(self) -> float:
        """
        Include all intervening work since the original sequence entry.
        """
        return process_time() - self.cpu_started

    @property
    def wall_seconds(self) -> float:
        """
        Include elapsed preparation and measurement time without clock renewal.
        """
        return perf_counter() - self.wall_started

    def start_action(self) -> None:
        """
        Charge unsuccessful and unsupported preparations before entering them.
        """
        self.checkpoint()
        if self.updates >= self.work.updates or self.pairs >= self.work.pairs:
            raise Exhausted("work_exhausted")
        self.updates += 1
        self.action_newton = 0

    def start_newton(self) -> None:
        """
        Charge failed numerical corrections too, at most six in each already charged action.
        """
        self.checkpoint()
        if (
            not self.updates
            or self.action_newton >= 6
            or self.newton_steps >= self.work.newton_steps
        ):
            raise Exhausted("newton_budget")
        self.newton_steps += 1
        self.action_newton += 1

    def reserve_factors(self) -> None:
        """
        Debit both possible balanced roots before computing or inspecting either.
        """
        self.checkpoint()
        if self.roots + 2 > self.maximum_roots:
            raise Exhausted("root_budget")
        self.roots += 2

    def charge_pairs(self, count: int) -> None:
        """
        Retain every completed comparison, including the final unsuccessful certificate.
        """
        if type(count) is not int or not 0 <= count <= self.work.pairs - self.pairs:
            raise ArithmeticError("Contact proof exceeded its supplied comparison pool")
        self.pairs += count
