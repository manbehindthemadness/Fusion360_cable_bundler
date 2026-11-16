"""
Compare bounded cyclic association against exhaustive small-loop assignments without selecting a preferred error.
"""

from itertools import product

import pytest

from experiments.experiment_ribbon_complete.boundary_cycle_candidates import BoundaryCycleCandidates
from experiments.experiment_ribbon_complete.material_polygon import MaterialPolygon
from experiments.experiment_ribbon_complete.native_boundary_distance import BoundarySide
from tests.test_ribbon_complete_native_boundary_distance import fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


@pytest.mark.parametrize(
    "candidates",
    [
        (
            (BoundarySide.LOW, BoundarySide.HIGH, BoundarySide.END0),
            (BoundarySide.HIGH,),
            (BoundarySide.END1,),
            (BoundarySide.LOW,),
        ),
        (
            (BoundarySide.END0,),
            (BoundarySide.LOW, BoundarySide.HIGH),
            (BoundarySide.END1,),
            (BoundarySide.LOW, BoundarySide.HIGH),
        ),
        (
            (BoundarySide.HIGH,),
            (BoundarySide.HIGH,),
            (BoundarySide.END1,),
            (BoundarySide.LOW,),
            (BoundarySide.END0,),
            (BoundarySide.HIGH,),
        ),
        (tuple(BoundarySide),) * 4,
        ((), (BoundarySide.HIGH,), (BoundarySide.END1,), (BoundarySide.LOW,)),
    ],
)
def test_dynamic_assignment_matches_independent_exhaustive_small_loop_oracle(
    candidates: tuple[tuple[BoundarySide, ...], ...],
) -> None:
    """
    Local ambiguity may become globally unique, but multiple valid whole cycles remain unresolved.
    """
    _, frame, graph = fixture()
    polygon = MaterialPolygon(frame, graph)
    valid = set()
    for assignment in product(*candidates):
        try:
            polygon.validate_sides(assignment)
        except ValueError:
            continue
        valid.add(assignment)
    proof = BoundaryCycleCandidates(polygon, candidates, checkpoint)
    assert proof.assignment_count == min(2, len(valid))
    assert proof.unique_assignment == (next(iter(valid)) if len(valid) == 1 else None)


def test_complete_cycle_association_observes_shared_resource_stop() -> None:
    """
    No additional proof-search allocation bypasses the caller's stop gate.
    """
    _, frame, graph = fixture()

    def stop() -> None:
        """
        Reject work after allocation expiry.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        BoundaryCycleCandidates(MaterialPolygon(frame, graph), (tuple(BoundarySide),) * 4, stop)
