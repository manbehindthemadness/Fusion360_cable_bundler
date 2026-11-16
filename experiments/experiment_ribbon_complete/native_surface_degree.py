"""
Prove native surface-domain coverage by boundary winding and original-profile continuity without a projection inverse claim.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from .boundary_traversal import BoundaryTraversalPolicy
from .clipped_flat_domain import ClippedNativeFlatDomainAccuracy
from .native_flat_domain import NativeFlatDomainAccuracy
from .native_material_domain import NativeBoundaryCollar, NativeOuterLoop
from .profile_continuity import ProfileContinuity


@dataclass(frozen=True)
class NativeSurfaceDegreeCoverage:
    """
    Bound both filled directions for an actual compact oriented native face with its complete single outer loop.

    The SDK actual-face manifold, orientation and complete boundary are trusted
    model premises. The ordered source-side collar preserves nonzero winding
    about every point in the source convex core. A missing native preimage
    would extend that boundary map into the punctured plane, whose boundary
    winding is zero by Stokes' theorem. Thus the actual affine (s,q) image
    covers the core even if its projection folds or has stationary derivatives.
    Compactness supplies boundary limits when the measured collar is zero.

    The existing SAME-face forward witness D and original-profile continuity
    lift planar reverse distance into one material/world allowance. This is
    existence and distance coverage only: projection injectivity, a qualified
    inverse material chart, isometry, paths, volume and physical acceptance
    remain separate gates. No native points or returned labels are changed.
    An explicit finite-bridge policy charges every corner of an omitted source
    side to its actual native junction. Convexity covers the intervening source
    segment without inventing a native coedge or rounding its length to zero.
    """

    loop: NativeOuterLoop
    continuity: ProfileContinuity
    domain: NativeFlatDomainAccuracy | ClippedNativeFlatDomainAccuracy
    checkpoint: InitVar[Callable[[], None]]
    boundary_policy: BoundaryTraversalPolicy = BoundaryTraversalPolicy.COMPLETE
    boundary: NativeBoundaryCollar = field(init=False)
    forward_upper_mm: Fraction = field(init=False)
    reverse_upper_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Bind exact native/source owners and charge forward witness plus source lift without assuming a native inverse.
        """
        checkpoint()
        first = self.loop.sides[0]
        frame, graph, native = first.frame, first.graph, first.box.native
        if isinstance(self.domain, ClippedNativeFlatDomainAccuracy):
            interval_owned = (
                graph is self.domain.clipped and self.continuity is self.domain.clipped.continuity
            )
        else:
            interval_owned = self.continuity.interval == graph.interval
        if (
            self.continuity.conic is not graph.conic
            or not interval_owned
            or self.domain.profile.frame is not frame
            or self.domain.profile.conic is not graph.conic
            or self.domain.status != "within_native_original_flat_domain_accuracy"
            or self.domain.distance_upper_mm is None
            or any(
                box.native is not native or box.face_token != first.box.face_token
                for box in (
                    *self.domain.profile.boxes,
                    self.domain.cuts.low_box,
                    self.domain.cuts.high_box,
                )
            )
        ):
            raise ValueError(
                "The SAME actual native face, source continuity and qualified forward domain required"
            )
        boundary = NativeBoundaryCollar(self.loop, checkpoint, self.boundary_policy)
        forward = self.domain.distance_upper_mm
        planar = boundary.planar_reverse_upper_mm + forward
        thickness = self.continuity.variation(planar)
        scales = tuple(sum(map(abs, column)) for column in frame.columns)
        lift = max(planar + thickness, max(scales[:2]) * planar + scales[2] * thickness)
        object.__setattr__(self, "boundary", boundary)
        object.__setattr__(self, "forward_upper_mm", forward)
        object.__setattr__(self, "reverse_upper_mm", forward + lift)
        checkpoint()

    @property
    def status(self) -> str:
        """
        Require a nonempty source core and one inclusive dimensional allowance, without assigning a material-map pass.
        """
        return (
            "qualified_native_surface_domain_by_degree"
            if 2 * self.boundary.collar_upper_mm < self.boundary.polygon.inradius_mm
            and max(self.forward_upper_mm, self.reverse_upper_mm) <= Fraction(1, 100)
            else "unresolved_native_surface_domain_by_degree"
        )
