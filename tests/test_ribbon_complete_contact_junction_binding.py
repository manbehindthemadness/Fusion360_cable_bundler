"""
Keep coupled cap bounds and native topology attached without treating them as contact clearance.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.cap_topology import CapEdge, inspect_cap_loop
from experiments.experiment_ribbon_complete.contact_cell import enclose
from experiments.experiment_ribbon_complete.contact_flat_junction import certify_flat_cap
from experiments.experiment_ribbon_complete.contact_junction_binding import (
    CapJunctionEvidence,
    NativeCapOwnership,
)
from experiments.experiment_ribbon_complete.contact_pairs import ContactWork, inspect_pair
from experiments.experiment_ribbon_complete.contact_profile_cover import certify
from experiments.experiment_ribbon_complete.flat_chart import straight
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from tests.test_ribbon_complete_contact_cell import box
from tests.test_ribbon_complete_flat_chart import piece
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def test_native_loop_and_real_small_overlap_remain_one_pending_contact_pair() -> None:
    """
    Even complete ordered boundary ownership and a small collar cannot clear overlapping interiors.
    """
    first_chart = straight(piece())
    second_chart = replace(
        straight(piece(2)), origin=(Fraction(399, 200), Fraction(0), Fraction(0))
    )
    first = enclose(first_chart, box(0, 2), checkpoint)
    second = enclose(second_chart, replace(box(0, 2), piece=1), checkpoint)
    profile = certify(material_profile(2, 0.75), 2, 0.75, checkpoint)
    labels = tuple(arc.label for arc in profile.arcs)
    loop = inspect_cap_loop(
        tuple(CapEdge(i, label, (i, (i + 1) % len(labels))) for i, label in enumerate(labels)),
        labels,
        checkpoint,
    )
    native = NativeCapOwnership((0, "straight"), (1, "straight"), "analytical-revision", loop)
    collar = certify_flat_cap(first_chart, second_chart, Fraction(1), Fraction(1), checkpoint)
    junction = CapJunctionEvidence(first, second, profile, collar, native, "analytical-revision")
    work = ContactWork(8, checkpoint)
    result = inspect_pair(first, second, profile, work, junction=junction)
    assert result.status == "unresolved_material_cap_collar"
    assert result.pending_pairs == 1 and work.used_pairs == 1
    retained = result.junction
    assert retained is junction
    assert junction.native is native
    single = ContactWork(1, checkpoint)
    assert (
        inspect_pair(first, second, profile, single, junction=junction).status
        == "unresolved_material_cap_collar"
    )
    exhausted = inspect_pair(first, second, profile, single, junction=junction)
    assert exhausted.status == "unresolved_pair_limit" and exhausted.visited == 0
    assert single.used_pairs == 1 and exhausted.junction is junction
    with pytest.raises(ValueError, match="distinct native region"):
        replace(native, first=(-1, "straight"))
    with pytest.raises(ValueError, match="distinct native region"):
        replace(native, revision="")
    with pytest.raises(ValueError, match="body revision"):
        replace(junction, expected_native_revision="wrong")
    with pytest.raises(ValueError, match="region pair"):
        replace(junction, native=replace(native, second=(2, "straight")))
    with pytest.raises(ValueError, match="profile order"):
        replace(
            junction,
            native=replace(native, loop=replace(loop, profile_order=tuple(reversed(labels)))),
        )
    with pytest.raises(ValueError, match="SAME original cells"):
        inspect_pair(replace(first), second, profile, work, junction=junction)


def test_wrong_geometry_or_incomplete_section_bounds_cannot_bind_a_collar() -> None:
    """
    Shared numerical coordinates do not transfer a proof to different geometry or a smaller section.
    """
    a, b = straight(piece()), straight(piece(2))
    first = enclose(a, box(0, 2), checkpoint)
    second = enclose(b, replace(box(0, 2), piece=1), checkpoint)
    profile = certify(material_profile(2, 0.75), 2, 0.75, checkpoint)
    narrow = certify_flat_cap(a, b, Fraction(1), Fraction(1, 4), checkpoint)
    with pytest.raises(ValueError, match="complete original"):
        CapJunctionEvidence(first, second, profile, narrow)
    valid = certify_flat_cap(a, b, Fraction(1), Fraction(1), checkpoint)
    with pytest.raises(ValueError, match="SAME original pair"):
        CapJunctionEvidence(first, second, profile, replace(valid, second=replace(b)))
    with pytest.raises(ValueError, match="original shared material"):
        CapJunctionEvidence(
            first, replace(second, box=replace(second.box, piece=3)), profile, valid
        )
