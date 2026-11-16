"""
Check complete cell partitions, bounded traversal and conservative contact outcomes.
"""

import pytest

from experiments.experiment_ribbon_complete.contact_cell import enclose
from experiments.experiment_ribbon_complete.contact_pairs import ContactWork, children, inspect_pair
from experiments.experiment_ribbon_complete.contact_profile_cover import certify
from experiments.experiment_ribbon_complete.flat_chart import straight
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from tests.test_ribbon_complete_contact_cell import box
from tests.test_ribbon_complete_flat_chart import piece
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def test_partition_keeps_same_owner_and_covers_parent_box_without_gaps() -> None:
    """
    A split preserves two whole closed child boxes meeting at exactly one shared cut.
    """
    owner = straight(piece())
    parent = enclose(owner, box(0, 2), checkpoint)
    left, right = children(parent, checkpoint)
    assert left.region is owner and right.region is owner
    assert left.box.u.low == parent.box.u.low and right.box.u.high == parent.box.u.high
    assert left.box.u.high == right.box.u.low
    assert left.box.q == right.box.q == parent.box.q
    assert left.box.height == right.box.height == parent.box.height
    assert left.box.depth == right.box.depth == 1


def test_remote_flat_is_clear_but_same_and_touching_interiors_are_unresolved() -> None:
    """
    Positive support accepts a full gap; neither overlap nor a shared cap is silently exempt.
    """
    first = enclose(straight(piece()), box(0, 2), checkpoint)
    profile = certify(material_profile(2, 0.75), 2, 0.75, checkpoint)
    remote = enclose(straight(piece(4)), box(0, 2), checkpoint)
    result = inspect_pair(first, remote, profile, ContactWork(8, checkpoint))
    assert result.status == "certified_separated" and result.pending_pairs == 0
    for second in (first, enclose(straight(piece(2)), box(0, 2), checkpoint)):
        result = inspect_pair(first, second, profile, ContactWork(8, checkpoint), 0)
        assert result.status == "unresolved_depth" and result.pending_pairs == 1


def test_exhausted_pair_work_preserves_pending_coverage_and_cannot_renew() -> None:
    """
    The same allocation remains spent across calls, including an unsuccessful original pair.
    """
    first = enclose(straight(piece()), box(0, 2), checkpoint)
    profile = certify(material_profile(2, 0.75), 2, 0.75, checkpoint)
    work = ContactWork(1, checkpoint)
    result = inspect_pair(first, first, profile, work)
    assert result.status == "unresolved_pair_limit" and result.pending_pairs == 2
    assert work.used_pairs == 1
    again = inspect_pair(first, first, profile, work)
    assert again.status == "unresolved_pair_limit" and again.visited == 0
    assert again.pending_pairs == 1 and work.used_pairs == 1


def test_invalid_allocations_and_resource_stops_do_not_return_contact_success() -> None:
    """
    There is no independent recovery pool or returned certificate after caller cancellation.
    """
    for value in (0, 2049, True):
        with pytest.raises(ValueError):
            ContactWork(value, checkpoint)

    def stop() -> None:
        """
        Stop the caller allocation before a support query.
        """
        raise RuntimeError("caller stopped")

    work = ContactWork(1, stop)
    with pytest.raises(RuntimeError, match="caller stopped"):
        work.claim()
    assert work.used_pairs == 0
