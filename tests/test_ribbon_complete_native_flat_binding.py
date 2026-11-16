"""
Prevent independently valid coordinate and domain evidence from silently acquiring foreign source or face ownership.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.flat_chart import MaterialCut
from experiments.experiment_ribbon_complete.flat_cut_domain import certify_frame_domain, from_chart
from experiments.experiment_ribbon_complete.native_flat_binding import NativeFlatBinding
from experiments.experiment_ribbon_complete.native_flat_domain import NativeFlatDomainAccuracy
from experiments.experiment_ribbon_complete.native_flat_material import FlatNativeMaterialField
from experiments.experiment_ribbon_complete.native_profile_accuracy import NativeProfileAccuracy
from experiments.experiment_ribbon_complete.profile_conic import EllipseArc
from tests.test_ribbon_complete_native_flat_material import field
from tests.test_ribbon_complete_native_profile_accuracy import fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def domain(
    material: FlatNativeMaterialField, wrong_branch: bool = False
) -> NativeFlatDomainAccuracy:
    """
    Use original source objects and a branch-sensitive actual-style box on the same captured support.
    """
    _, _, box = fixture(branch=-1 if wrong_branch else 1)
    box = replace(box, native=material.embedding.support.native)
    frame = from_chart(material.frame)
    profile = NativeProfileAccuracy(
        EllipseArc(material.embedding.support.arc), frame, (box,), checkpoint
    )
    return NativeFlatDomainAccuracy(
        profile, certify_frame_domain(frame, box, box, checkpoint), checkpoint
    )


def test_owned_binding_preserves_coordinates_and_all_existing_error_bounds() -> None:
    """
    Linking a valid domain neither changes the coordinate map nor relabels projection bounds as full native metrics.
    """
    material = field()
    proof = domain(material)
    bound = NativeFlatBinding(material, proof, checkpoint)
    assert bound.status == "qualified_native_flat_coordinate_domain_binding"
    point = Fraction(1), Fraction(3, 5), Fraction(4, 5)
    assert bound.coordinates(point) == material.coordinates(point) == point
    assert bound.material is material and bound.domain is proof
    assert material.embedding.support.chart.point(*bound.coordinates(point)) == point


def test_equivalent_foreign_native_and_profile_objects_cannot_be_substituted() -> None:
    """
    Equal numerical geometry does not establish that evidence shares original source and native ownership.
    """
    material = field()
    with pytest.raises(ValueError, match="SAME native face"):
        NativeFlatBinding(material, domain(field()), checkpoint)
    proof = domain(material)
    foreign_arc = replace(proof.profile.conic.arc)
    profile = NativeProfileAccuracy(
        EllipseArc(foreign_arc), proof.profile.frame, proof.profile.boxes, checkpoint
    )
    with pytest.raises(ValueError, match="SAME native face"):
        NativeFlatBinding(
            material, NativeFlatDomainAccuracy(profile, proof.cuts, checkpoint), checkpoint
        )


@pytest.mark.parametrize("change", ("cut", "token"))
def test_valid_components_with_different_cuts_or_face_tokens_cannot_bind(change: str) -> None:
    """
    A domain can qualify alone yet belong to different original cuts or an unrelated native trim.
    """
    material = field()
    proof = domain(material)
    frame = proof.profile.frame
    boxes = proof.profile.boxes
    if change == "cut":
        frame = replace(frame, high=MaterialCut(Fraction(3)))
    else:
        boxes = tuple(replace(box, face_token="another-face") for box in boxes)
    profile = NativeProfileAccuracy(proof.profile.conic, frame, boxes, checkpoint)
    changed = NativeFlatDomainAccuracy(
        profile, certify_frame_domain(frame, boxes[0], boxes[0], checkpoint), checkpoint
    )
    assert changed.status == "within_native_original_flat_domain_accuracy"
    with pytest.raises(ValueError, match="SAME native face"):
        NativeFlatBinding(material, changed, checkpoint)


def test_wrong_branch_stays_unresolved_and_resource_stop_prevents_new_binding() -> None:
    """
    Coordinate validity cannot waive a missing domain proof, and binding honors the caller's shared stop.
    """
    material = field()
    bound = NativeFlatBinding(material, domain(material, wrong_branch=True), checkpoint)
    assert bound.status == "unresolved_native_flat_coordinate_domain_binding"
    with pytest.raises(ValueError, match="qualified native"):
        bound.coordinates((Fraction(1), Fraction(0), Fraction(1)))

    def stop() -> None:
        """
        Refuse additional qualification once the caller's allocation stops.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        NativeFlatBinding(material, domain(material), stop)
