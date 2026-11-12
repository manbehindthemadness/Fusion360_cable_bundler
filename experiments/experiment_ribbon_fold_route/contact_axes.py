"""
Re-prove untrusted optional directions on immutable material cells without caching clearance.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from enum import Enum
from typing import Callable

from cable_bundler.routing.geometry import Vector3

from .contact_bounds import Cell, Span
from .geometry import FoldRoute

Project = Callable[[Cell, Vector3], Span]


class AxisContinuation(Enum):
    """
    Preserve root-only proposal tests or re-prove directions on their descendant material cells.
    """

    ROOT_ONLY = "root_only"
    MATERIAL_CELLS = "material_cells"


class AxisLearning(Enum):
    """
    Keep external hints alone or also retain directions from completed local-axis separation tests.
    """

    PROPOSALS_ONLY = "proposals_only"
    LOCAL_SEPARATIONS = "local_separations"


class ProposedAxes:
    """
    Own at most 64 untrusted directions and measured proof counters for one immutable walk.

    No span or clearance is retained. FIFO eviction removes only acceleration;
    ordinary complete-cell proof and subdivision remain mandatory. A context
    cannot transfer directions, counters or unfinished work into another walk.
    """

    def __init__(
        self,
        continuation: AxisContinuation = AxisContinuation.ROOT_ONLY,
        *,
        learning: AxisLearning = AxisLearning.PROPOSALS_ONLY,
    ) -> None:
        """
        Require an explicit typed strategy and start with no source or inherited measurements.
        """
        if not isinstance(continuation, AxisContinuation):
            raise ValueError("Supply an explicit optional-axis continuation policy")
        if not isinstance(learning, AxisLearning) or (
            learning is AxisLearning.LOCAL_SEPARATIONS
            and continuation is not AxisContinuation.MATERIAL_CELLS
        ):
            raise ValueError("Local separation learning requires material-cell continuation")
        self.continuation = continuation
        self.learning = learning
        self._source: FoldRoute | None = None
        self._directions: OrderedDict[tuple[int, int], Vector3] = OrderedDict()
        self._resolutions: dict[tuple[int, int], float] = {}
        self.tests = self.separations = 0
        self.descendant_tests = self.descendant_separations = 0
        self.local_hints = 0
        self.resolution_deferrals = 0

    def bind(self, route: FoldRoute) -> None:
        """
        Seal one immutable proof source, rejecting reuse even for an equivalent or identical route.
        """
        if self._source is not None:
            raise ValueError("Use a fresh optional-axis context for each contact walk")
        self._source = route

    def retain(self, pair: tuple[int, int], proposal: object) -> Vector3:
        """
        Validate the original finite nonzero proposal and optionally retain its original pair identity.
        """
        if self._source is None:
            raise ValueError("Bind a contact source before retaining optional directions")
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or any(type(index) is not int for index in pair)
            or not 0 <= pair[0] < pair[1] < len(self._source.pieces)
        ):
            raise ValueError("Optional directions require ordered existing material identities")
        if not isinstance(proposal, Vector3):
            raise ValueError("Optional axis proposal must be a finite nonzero vector")
        coordinates = proposal.x, proposal.y, proposal.z
        if (
            any(
                type(value) not in (int, float) or not math.isfinite(value) for value in coordinates
            )
            or not 0 < math.hypot(*coordinates) < math.inf
        ):
            raise ValueError("Optional axis proposal must be a finite nonzero vector")
        if self.continuation is AxisContinuation.MATERIAL_CELLS:
            self._directions[pair] = proposal
            self._resolutions.pop(pair, None)
            if len(self._directions) > 64:
                evicted, _ = self._directions.popitem(last=False)
                self._resolutions.pop(evicted, None)
        return proposal

    def separates(
        self,
        first: Cell,
        second: Cell,
        direction: Vector3,
        project: Project,
        checkpoint: Callable[[], None] | None,
    ) -> bool:
        """
        Re-enclose both complete thick cells and accept only the original strict interval inequality.

        Counters count started tests, including a test interrupted in projection.
        Separations count only fully measured strict outward-bound decisions.
        """
        if checkpoint is not None:
            checkpoint()
        descendant = max(first.depth, second.depth) > 0
        self.tests += 1
        self.descendant_tests += int(descendant)
        a, b = project(first, direction), project(second, direction)
        separated = a.high < b.low or b.high < a.low
        self.separations += int(separated)
        self.descendant_separations += int(descendant and separated)
        return separated

    def _resolution(self, first: Cell, second: Cell) -> float:
        """
        Measure the pair's largest material-coordinate extent at this immutable source.
        """
        source = self._source
        if source is None:
            raise ValueError("Bind a contact source before retaining optional directions")
        sizes: list[float] = []
        for cell in (first, second):
            if type(cell.piece) is not int or not 0 <= cell.piece < len(source.pieces):
                raise ValueError("Learning requires existing material identities")
            extents = (
                (cell.u.high - cell.u.low) * source.pieces[cell.piece].geometry.material_length_mm,
                cell.q.high - cell.q.low,
                cell.height.high - cell.height.low,
            )
            if any(not math.isfinite(value) or value < 0 for value in extents):
                raise ValueError("Learning requires finite nonnegative material extents")
            sizes.extend(extents)
        return max(sizes)

    def learn_local(self, first: Cell, second: Cell, direction: Vector3) -> None:
        """
        Retain a completed local separation's direction only under the explicit learning policy.

        The caller must first measure strict separation of both complete cells.
        Retain its direction and one material-resolution scalar within the
        existing64entry FIFO context; results, spans and cells are not retained.
        Coarser pairs defer this optional test. Same/finer pairs must re-prove
        their own full outward bounds. Default contexts remain unchanged.
        """
        if self.learning is AxisLearning.LOCAL_SEPARATIONS:
            resolution = self._resolution(first, second)
            pair = first.piece, second.piece
            self.retain(pair, direction)
            self._resolutions[pair] = resolution
            self.local_hints += 1

    def separates_descendants(
        self,
        first: Cell,
        second: Cell,
        project: Project,
        checkpoint: Callable[[], None] | None,
    ) -> bool:
        """
        Offer one retained direction only to descendants of its same original material pair.
        """
        if self.continuation is AxisContinuation.ROOT_ONLY or max(first.depth, second.depth) == 0:
            return False
        direction = self._directions.get((first.piece, second.piece))
        resolution = self._resolutions.get((first.piece, second.piece))
        if direction is not None and resolution is not None:
            if checkpoint is not None:
                checkpoint()
            if self._resolution(first, second) > resolution:
                self.resolution_deferrals += 1
                return False
        return direction is not None and self.separates(
            first, second, direction, project, checkpoint
        )

    def statistics(self) -> dict[str, int]:
        """
        Expose attempted tests, completed strict separations and bounded retained-direction count.
        """
        result = {
            "tests": self.tests,
            "separations": self.separations,
            "descendant_tests": self.descendant_tests,
            "descendant_separations": self.descendant_separations,
            "retained_directions": len(self._directions),
        }
        if self.learning is AxisLearning.LOCAL_SEPARATIONS:
            result["local_separation_hints"] = self.local_hints
            result["resolution_deferrals"] = self.resolution_deferrals
            result["retained_resolutions"] = len(self._resolutions)
        return result
