"""
Bind partial cap evidence to exact canonical pair owners without accepting remaining contact.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3255.run import profile_reach

from .cap_topology import CapLoopEvidence
from .contact_cell import ContactCell
from .contact_flat_junction import FlatCapCollar
from .contact_junction import BendCapCollar
from .contact_profile_cover import ProfileSupportCover
from .flat_chart import FlatChart

RegionKey = tuple[int, str]


def region_key(cell: ContactCell) -> RegionKey:
    """
    Preserve the original piece ordinal and explicit material region kind.
    """
    if type(cell.box.piece) is not int or cell.box.piece < 0:
        raise ValueError("An explicit original material piece ordinal required")
    return cell.box.piece, cell.region.region.value if isinstance(
        cell.region, FlatChart
    ) else "bend"


@dataclass(frozen=True)
class NativeCapOwnership:
    """
    Retain observed native boundary provenance separately from material-coordinate validity.

    The capture adapter verifies live body ownership and face-map source hashes;
    this value alone cannot establish them or turn topology into volume clearance.
    """

    first: RegionKey
    second: RegionKey
    revision: str
    loop: CapLoopEvidence

    def __post_init__(self) -> None:
        """
        Validate external native identity fields before any set or adjacency operation.
        """
        kinds = {"straight", "before", "bend", "after"}
        if (
            any(
                type(key) is not tuple
                or len(key) != 2
                or type(key[0]) is not int
                or key[0] < 0
                or not isinstance(key[1], str)
                or key[1] not in kinds
                for key in (self.first, self.second)
            )
            or self.first == self.second
            or not isinstance(self.revision, str)
            or not self.revision.strip()
            or not isinstance(self.loop, CapLoopEvidence)
        ):
            raise ValueError(
                "Explicit distinct native region keys, revision and topology receipt required"
            )


@dataclass(frozen=True)
class CapJunctionEvidence:
    """
    Keep a qualified exterior collar bound and optional native loop on the SAME exact pair.

    This always retains unresolved collar contact, native inverse/gluing and flow.
    It is never a substitute for a successful whole-pair separation certificate.
    """

    first: ContactCell
    second: ContactCell
    profile: ProfileSupportCover
    collar: BendCapCollar | FlatCapCollar
    native: NativeCapOwnership | None = None
    expected_native_revision: str | None = None

    def __post_init__(self) -> None:
        """
        Reject source, adjacency, profile and native-body substitutions before consuming evidence.
        """
        a, b = region_key(self.first), region_key(self.second)
        same_piece = a[0] == b[0] and {a[1], b[1]} in ({"before", "bend"}, {"bend", "after"})
        ordered = sorted((a, b))
        left, right = ordered
        consecutive = (
            right[0] == left[0] + 1
            and left[1] in ("straight", "after")
            and right[1] in ("straight", "before")
        )
        if not (same_piece or consecutive):
            raise ValueError("Only original shared material caps may bind junction evidence")
        if (
            self.profile.status != "certified_positive_support_cover"
            or self.collar.status != "certified_material_cap_collar"
        ):
            raise ValueError("Qualified original profile and material collar bounds required")
        if isinstance(self.collar, BendCapCollar):
            owners = (
                (self.first.region, self.second.region),
                (self.second.region, self.first.region),
            )
            matches = any(
                chart is self.collar.chart and volume is self.collar.volume
                for chart, volume in owners
            )
        else:
            matches = (
                self.first.region is self.collar.first and self.second.region is self.collar.second
            )
        if not matches:
            raise ValueError("Collar must bind the SAME original pair geometry")
        half = max(abs(Fraction(q)) for arc in self.profile.arcs for q, _ in arc.controls)
        reach = max(
            profile_reach({"controls": arc.controls, "weights": arc.weights})
            for arc in self.profile.arcs
        )
        if isinstance(self.collar, BendCapCollar):
            bounds = self.collar.volume.source.half_mm, self.collar.volume.half_thickness_mm
        else:
            bounds = self.collar.half_mm, self.collar.half_thickness_mm
        if bounds[0] < half or bounds[1] < reach:
            raise ValueError("Collar must cover the complete original filled profile")
        if self.native is not None:
            if (
                not self.expected_native_revision
                or self.native.revision != self.expected_native_revision
            ):
                raise ValueError("Native boundary must match the current body revision")
            if {self.native.first, self.native.second} != {a, b}:
                raise ValueError("Native boundary must bind the SAME material region pair")
            if (
                self.native.loop.status != "certified_ordered_cap_cycle"
                or self.native.loop.profile_order != tuple(arc.label for arc in self.profile.arcs)
            ):
                raise ValueError("Native boundary must retain the original complete profile order")
        elif self.expected_native_revision is not None:
            raise ValueError("A native revision cannot replace missing native boundary evidence")
