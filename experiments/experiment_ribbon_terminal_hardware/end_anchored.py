"""
Hold the end connector frame exactly while existing material joints move.
"""

from __future__ import annotations

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, relative

from .feature_plane import SignedJoints
from .reversal_model import frame_rotation


class EndAnchoredJoints(SignedJoints):
    """
    Reexpress unchanged ordered material in its fixed end frame before measuring start closure.

    Placement applies one proper rigid transformation to the forward-composed
    material, equivalent to inverse propagation from its end. Geometry, labels,
    signs, radii and conductor order are preserved. The start is a six-component
    closure constraint; fixing the end alone does not make a valid two-ended
    route. This experimental coordinate model is not selected by the solver.
    """

    def _place(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Anchor every trial's end frame without modifying any local material primitive.

        Reanchoring is part of the numerical placement, not output repair or a
        tolerance-based cap snap. Empty material remains empty for the inherited
        route guard. Pure placements retain the existing bounded model cache.
        """
        pieces = super()._place(values)
        if not pieces:
            return ()
        actual = pieces[-1].end_pose()
        target = self.original.targets
        fixed = Pose(target.end, target.end_tangent, target.end_width)
        return tuple(
            PlacedPiece(
                Pose(
                    fixed.point(relative(actual, difference(piece.pose.origin, actual.origin))),
                    fixed.direction(relative(actual, piece.pose.tangent)),
                    fixed.direction(relative(actual, piece.pose.width)),
                ),
                piece.geometry,
                piece.label,
            )
            for piece in pieces
        )

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Constrain the original ordered start frame, including nonzero half-turn errors.

        Position uses the inherited fixed initial-length normalization. The
        original end remains fixed by placement, including during differentiation
        and nonlinear closure. Final physical and cap audits are still required.
        """
        pieces = self.pieces(values)
        if not pieces:
            raise ValueError("End-anchored closure requires nonempty material")
        target = self.original.targets
        expected = Pose(target.start, target.start_tangent, target.start_width)
        actual = pieces[0].pose
        displacement = difference(actual.origin, expected.origin)
        position = tuple(getattr(displacement, axis) / self.scale for axis in "xyz")
        return position + frame_rotation(actual, expected)
