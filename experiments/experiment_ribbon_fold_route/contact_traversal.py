"""
Resume one immutable material-cell traversal without repeating or renewing comparisons.
"""

from __future__ import annotations

from functools import partial
from typing import Callable, Generator

from .contact import ContactResult, ProbeOrder, ProjectionReuse, WitnessProbe, _walk
from .contact_cap_support import CapPolicy
from .geometry import FoldRoute


class ContactTraversal:
    """
    Own one route and fixed proof policy under an immutable cumulative pair ceiling.

    Only pair exhaustion can suspend. A completed, depth-limited or irregular
    result is final. Changed geometry needs a new traversal and a new complete
    certificate. An optional negative-only probe runs once per original pair
    within the same stack. A probe that exhausts its comparison allowance ends
    the walk permanently; only a genuinely suspended material stack may resume.
    The typed original-pair-first policy retains that same pending screen and
    material stack across chunks; no original pair is screened twice.
    Exceptions permanently close this traversal; callers cannot retry cancelled
    work or recover uncharged partial comparisons. The owner must conservatively
    charge its active allowance when a check is interrupted.
    """

    def __init__(
        self,
        route: FoldRoute,
        *,
        maximum_pairs: int,
        maximum_depth: int = 36,
        checkpoint: Callable[[], None] | None = None,
        cap_policy: CapPolicy = CapPolicy.MONOTONE,
        projection_reuse: ProjectionReuse = ProjectionReuse.PREPARATIONS,
        witness_probe: WitnessProbe | None = None,
        probe_order: ProbeOrder = ProbeOrder.MATERIAL_CELLS,
    ) -> None:
        """
        Seal the source, policy and total allowance before any material comparison.
        """
        if type(maximum_pairs) is not int or maximum_pairs < 1:
            raise ValueError("Positive finite cumulative contact allowance required")
        self._maximum_pairs = maximum_pairs
        self._checkpoint = checkpoint
        self._start = partial(
            _walk,
            route,
            maximum_depth=maximum_depth,
            checkpoint=checkpoint,
            cap_policy=cap_policy,
            witness_probe=witness_probe,
            probe_order=probe_order,
            projection_reuse=projection_reuse,
        )
        self._pending: Generator[ContactResult, int, ContactResult] | None = None
        self._result: ContactResult | None = None
        self._limit = 0
        self._failed = False

    def advance(self, pair_limit: int) -> ContactResult:
        """
        Continue to a cumulative limit, retaining the first unprocessed cell pair.

        Returned pairs_checked counts the complete traversal, including earlier
        calls. Equal limits return the existing immutable receipt without work.
        Completed receipts can also be read without rerunning geometry.
        """
        if (
            type(pair_limit) is not int
            or not self._limit <= pair_limit <= self._maximum_pairs
            or pair_limit < 1
        ):
            raise ValueError("Use a nondecreasing limit within the original contact allowance")
        if self._failed:
            raise RuntimeError("Interrupted contact traversal cannot resume")
        if self._result is not None and (
            self._pending is None or self._result.limit != "pairs" or pair_limit == self._limit
        ):
            self._limit = pair_limit
            return self._result
        self._limit = pair_limit
        try:
            if self._checkpoint is not None:
                self._checkpoint()
            if self._pending is None:
                pending = self._start(maximum_pairs=pair_limit)
                self._pending = pending
                self._result = next(pending)
            else:
                self._result = self._pending.send(pair_limit)
        except StopIteration as finished:
            self._result = finished.value
            self._pending = None
        except BaseException:
            self._failed = True
            if self._pending is not None:
                self._pending.close()
            raise
        assert self._result is not None
        return self._result
