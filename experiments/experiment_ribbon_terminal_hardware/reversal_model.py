"""
Reflect one measured incident fold while coupling the remaining joints to fixed targets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property

from cable_bundler.routing.geometry import cross, difference, dot
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Pose

from .check import Witness


def incident_fold(route: FoldRoute, witness: Witness) -> int | None:
    """
    Select the witnessed fold or the fold joining its straight toward the hit terminal.

    This derives one ordered event from material incidence. It never searches
    alternative fold indices or assumes the terminal-most fold caused a return.
    A terminal straight with no fold toward that terminal has no supported action.
    """
    if witness.terminal not in ("start", "end") or not 0 <= witness.piece < len(route.pieces):
        raise ValueError("A terminal witness must identify an existing material piece")
    folds = tuple(
        i for i, piece in enumerate(route.pieces) if isinstance(piece.geometry, CylindricalFold)
    )
    if witness.piece in folds:
        selected = witness.piece
    elif witness.terminal == "end":
        selected = next((i for i in folds if i > witness.piece), None)
    else:
        selected = next((i for i in reversed(folds) if i < witness.piece), None)
    return folds.index(selected) if selected is not None else None


def frame_rotation(actual: Pose, target: Pose) -> tuple[float, float, float]:
    """
    Return the shortest SO(3) logarithm in the target frame, including a nonzero half-turn.

    Quaternion extraction uses the largest diagonal near a half-turn. Unlike the
    historical local skew residual, this cannot certify a reversed ordered frame
    as zero. Final acceptance still measures the actual cap vectors separately.
    """
    axes = (target.tangent, target.width, cross(target.tangent, target.width))
    ends = (actual.tangent, actual.width, cross(actual.tangent, actual.width))
    matrix = tuple(tuple(dot(a, b) for b in ends) for a in axes)
    trace = sum(matrix[i][i] for i in range(3))
    if trace > 0:
        scale = 2 * math.sqrt(1 + trace)
        quaternion = [
            scale / 4,
            (matrix[2][1] - matrix[1][2]) / scale,
            (matrix[0][2] - matrix[2][0]) / scale,
            (matrix[1][0] - matrix[0][1]) / scale,
        ]
    else:
        i = max(range(3), key=lambda index: matrix[index][index])
        j, k = (i + 1) % 3, (i + 2) % 3
        scale = 2 * math.sqrt(max(0.0, 1 + matrix[i][i] - matrix[j][j] - matrix[k][k]))
        quaternion = [0.0] * 4
        quaternion[0] = (matrix[k][j] - matrix[j][k]) / scale
        quaternion[i + 1] = scale / 4
        quaternion[j + 1] = (matrix[j][i] + matrix[i][j]) / scale
        quaternion[k + 1] = (matrix[k][i] + matrix[i][k]) / scale
    if quaternion[0] < 0:
        quaternion = [-value for value in quaternion]
    length = math.sqrt(math.fsum(value**2 for value in quaternion[1:]))
    factor = 2 * math.atan2(length, quaternion[0]) / length if length > 1e-12 else 2.0
    return quaternion[1] * factor, quaternion[2] * factor, quaternion[3] * factor


@dataclass(frozen=True)
class ReversalModel(MovableBends):
    """
    Fix one reflected angle/bank and all radii; move other signed angles, banks and runways.

    Other folds retain their original signs. Initially absent straight slots may
    grow, and existing ones may contract, while their lengths remain nonnegative.
    Recomposition preserves material order and the fixed start frame. Closure
    solves the other endpoint's position and complete ordered orientation together.
    """

    selected: int

    def __post_init__(self) -> None:
        """
        Require an existing ordered fold before constructing any reflected coordinates.
        """
        if type(self.selected) is not int or not 0 <= self.selected < len(self.folds):
            raise ValueError("Select an existing fold ordinal")

    @cached_property
    def indices(self) -> tuple[int, ...]:
        """
        Exclude immutable radii and the selected reflected fold's fixed angle and bank.
        """
        fixed = (4 * self.selected + 1, 4 * self.selected + 2)
        return tuple(i for i in range(len(self.full.initial)) if i % 4 != 3 and i not in fixed)

    def expanded(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Reflect exactly one source angle and reinsert the unchanged bank/radius anchors.
        """
        if len(values) != len(self.indices):
            raise ValueError("Supply one value per free reflected-chain coordinate")
        result = list(self.full.initial)
        result[4 * self.selected + 1] *= -1
        for index, value in zip(self.indices, values):
            result[index] = value
        return tuple(result)

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Preserve all nonselected fold signs alongside existing bank and runway bounds.
        """
        full_index = self.indices[index]
        low, high = self.full.bounds(full_index)
        if full_index % 4 == 1:
            if self.full.initial[full_index] > 0:
                low = 0.0
            else:
                high = 0.0
        return low, high

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Couple layout-normalized endpoint position with the full ordered-frame rotation.
        """
        return ordered_residual(self, values)


def ordered_residual(model: MovableBends, values: tuple[float, ...]) -> tuple[float, ...]:
    """
    Share exact ordered-cap residuals across reflected and sign-preserving joint models.
    """
    end = model.pieces(values)[-1].end_pose()
    target = model.original.targets
    displacement = difference(end.origin, target.end)
    expected = Pose(target.end, target.end_tangent, target.end_width)
    position = tuple(getattr(displacement, axis) / model.scale for axis in "xyz")
    return position + frame_rotation(end, expected)
