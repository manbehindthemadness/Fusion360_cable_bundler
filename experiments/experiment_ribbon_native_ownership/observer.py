"""
Retain bounded coverage evidence at the original check's return or exception unwind.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import CodeType, FrameType
from typing import Any, Callable


@dataclass(frozen=True)
class Coverage:
    """
    Detach the original ownership map while retaining only its unchanged native body handle.
    """

    body: Any
    native_face_count: int
    owners: tuple[tuple[int, int], ...]
    regions: tuple[tuple[int, ...], ...]
    queries: int
    distance_queries: int

    def payload(self) -> dict[str, Any]:
        """
        Serialize evidence outside the audit callback, without evaluating any geometry or certificate.
        """
        claimed = {index for index, _ in self.owners}
        return {
            "body_revision": self.body.revisionId,
            "native_face_count": self.native_face_count,
            "owners": [list(entry) for entry in self.owners],
            "regions": [list(region) for region in self.regions],
            "unowned": sorted(set(range(self.native_face_count)) - claimed),
            "queries": self.queries,
            "distance_queries": self.distance_queries,
            "sealed": False,
        }


class Observer:
    """
    Scope a Python profile callback to one synchronous host poll and preserve original failures.

    Only the exact supplied seal function's return event is observed, including
    exception unwind. No native query, source patch, solver callback or physical
    acceptance is changed. A failed seal's plain ownership data is copied before
    its frame disappears. At most two failed records are retained; overflow is
    reported for a hard harness stop outside this callback. The caller owns that
    disposition and writes receipts after the original audit returns.
    An existing profiler is refused, and any unexpected replacement is preserved
    and reported. This diagnostic adds host timing overhead; it is not a speed test.
    """

    def __init__(self, seal: Callable[..., None]) -> None:
        """
        Bind one existing function by code identity without changing its module or implementation.
        """
        code = getattr(seal, "__code__", None)
        if not isinstance(code, CodeType):
            raise ValueError("Observe an existing Python seal function")
        self._code = code
        self._callback = self._observe
        self._active = False
        self._used = False
        self.calls = 0
        self.overflow = False
        self.failures: list[Coverage] = []

    def __enter__(self) -> Observer:
        """
        Refuse an existing profiler or reentry instead of displacing another observer.
        """
        if self._used or sys.getprofile() is not None:
            raise RuntimeError(
                "Ownership observer requires an unused lease and no existing profiler"
            )
        self._used = self._active = True
        sys.setprofile(self._callback)
        return self

    def __exit__(self, *_exception: Any) -> None:
        """
        Remove only this callback and let the original audit or caller exception propagate.
        """
        if not self._active or sys.getprofile() is not self._callback:
            raise RuntimeError("Ownership observer profile lease changed")
        sys.setprofile(None)
        self._active = False

    def _observe(self, frame: FrameType, event: str, _argument: Any) -> None:
        """
        Copy only original Python bookkeeping at a failed seal, issuing no native operations.
        """
        if event != "return" or frame.f_code is not self._code:
            return
        mapping = frame.f_locals["self"]
        self.calls += 1
        if mapping.sealed:
            return
        if len(self.failures) == 2:
            self.overflow = True
            return
        self.failures.append(
            Coverage(
                mapping.body,
                len(mapping.native),
                tuple(sorted(mapping.owners.items())),
                tuple(tuple(sorted(region)) for region in mapping.members),
                mapping.queries,
                mapping.distance_queries,
            )
        )

    def payload(self) -> dict[str, Any]:
        """
        Report the detached evidence after the profile lease has been removed.
        """
        if self._active:
            raise RuntimeError("Collect ownership evidence only after the observed poll")
        return {
            "observed_seals": self.calls,
            "overflow": self.overflow,
            "failures": [failure.payload() for failure in self.failures],
            "scope": "Original coverage bookkeeping only; no remapping, solve, build or proof replay",
        }
