"""
Check common flat cap labels, original cut ownership and combined uncertainty without native UV assumptions.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.flat_correspondence import controls
from experiments.experiment_ribbon_complete.native_cap_chain import (
    ConformingCapChain,
    conform,
    orient_endpoints,
)
from experiments.experiment_ribbon_complete.native_cap_material import (
    MaterialCapSource,
    NativeCapCurve,
    bind,
)
from experiments.experiment_ribbon_complete.native_flat_cap import FlatCapIncidence, adopt
from experiments.experiment_ribbon_complete.native_flat_cylinder import enclose
from experiments.experiment_ribbon_complete.native_flat_embedding import (
    FlatSupportEmbedding,
    certify,
)
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from tests.test_ribbon_complete_native_flat_cylinder import cylinder
from tests.test_ribbon_complete_native_flat_embedding import chart, support
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def inputs(
    side: int,
    reverse: bool = False,
    shift: Fraction = Fraction(0),
    declared_error: Fraction = Fraction(0),
) -> tuple[FlatSupportEmbedding, ConformingCapChain, FlatCapIncidence]:
    """
    Author one unchanged captured-like edge with explicit original source order and optional measured cap offset.
    """
    embedding = certify(support(), checkpoint)
    owned = embedding.support
    cut = owned.chart.high if side == 0 else owned.chart.low
    row = tuple((p[0] + shift, p[1], p[2]) for p in controls(owned.chart, cut, owned.arc))
    first = MaterialCapSource((0, "straight"), owned.arc, row, declared_error, "source")
    other = replace(first, region=(1, "before"))
    pair = (first, other) if side == 0 else (other, first)
    weights = tuple(map(Fraction, owned.arc.weights))
    curve = NativeCapCurve(
        owned.native.revision,
        7,
        tuple(reversed(row)) if reverse else row,
        tuple(reversed(weights)) if reverse else weights,
    )
    bound = bind(curve, pair, (Fraction(0), Fraction(1)), curve.revision, checkpoint)
    endpoint = orient_endpoints(
        curve, (10, 11), (curve.controls[0], curve.controls[-1]), checkpoint
    )
    chain = conform((bound,), (endpoint,), (Fraction(0), Fraction(0)), checkpoint)
    return embedding, chain, FlatCapIncidence(owned.native, curve)


@pytest.mark.parametrize("side", (0, 1))
@pytest.mark.parametrize("reverse", (False, True))
def test_shared_labels_use_the_original_ordered_cut_and_explicit_curve_map(
    side: int, reverse: bool
) -> None:
    """
    Both native directions and both source sides decode identical original q/b without a UV convention.
    """
    embedding, chain, incidence = inputs(side, reverse)
    binding = chain.bindings[0]
    result = adopt(embedding, chain, binding, incidence, checkpoint)
    assert result.status == "qualified_flat_cap_material_labels" and result.side == side
    assert result.source_control_upper_mm.numerator == 0
    assert binding.mapping is not None
    for i in range(9):
        z = Fraction(i, 8)
        q, b = binding.mapping.profile_coordinates(z)
        assert result.material_coordinates(z) == (Fraction(2 if side == 0 else 0), q, b)
    with pytest.raises(ValueError, match="SAME actual face/curve"):
        replace(result, incidence=replace(incidence, native=replace(incidence.native)))
    with pytest.raises(ValueError, match="SAME canonical cut"):
        replace(result, world_upper_mm=Fraction(1))


def test_source_tags_and_a_small_gap_cannot_replace_the_original_canonical_error_receipt() -> None:
    """
    A cap offset below0.01mm still requires the source error already charged to the shared chain.
    """
    embedding, chain, incidence = inputs(0, shift=Fraction(1, 2000))
    result = adopt(embedding, chain, chain.bindings[0], incidence, checkpoint)
    assert result.source_control_upper_mm == Fraction(1, 2000)
    assert result.status == "unresolved_flat_cap_material_labels"
    with pytest.raises(ValueError, match="qualified SAME-source"):
        result.material_coordinates(Fraction(1, 2))
    embedding, chain, incidence = inputs(
        0, shift=Fraction(1, 2000), declared_error=Fraction(1, 2000)
    )
    result = adopt(embedding, chain, chain.bindings[0], incidence, checkpoint)
    assert result.status == "qualified_flat_cap_material_labels"
    assert result.world_upper_mm is not None and result.world_upper_mm >= Fraction(1, 2000)


def test_chain_and_projection_errors_share_one_dimensional_allowance() -> None:
    """
    A larger native circle and its source uncertainty cannot each consume a separate0.01mm allowance.
    """
    arc = MaterialArc(((1, 0), (1, 1), (0, 1)), (1, 2**-0.5, 1), "circle")
    radius = Fraction(251, 250)
    native = replace(cylinder(), radius_mm=radius)
    measured = enclose(chart(), arc, native, 0, native.revision, checkpoint)
    embedding = certify(measured, checkpoint)
    row = tuple(
        (p[0], p[1] * radius, p[2] * radius)
        for p in controls(measured.chart, measured.chart.high, arc)
    )
    source = MaterialCapSource((0, "straight"), arc, row, 2 * (radius - 1), "measured outgoing")
    pair = source, replace(source, region=(1, "before"))
    curve = NativeCapCurve(native.revision, 7, row, tuple(map(Fraction, arc.weights)))
    bound = bind(curve, pair, (Fraction(0), Fraction(1)), native.revision, checkpoint)
    endpoints = orient_endpoints(curve, (10, 11), (row[0], row[-1]), checkpoint)
    chain = conform((bound,), (endpoints,), (Fraction(0), Fraction(0)), checkpoint)
    assert embedding.status == "certified_flat_support_global_coordinates"
    assert chain.status == "qualified_conforming_cap_material_chain"
    result = adopt(embedding, chain, chain.bindings[0], FlatCapIncidence(native, curve), checkpoint)
    assert result.world_upper_mm is not None and result.world_upper_mm > Fraction(1, 100)
    assert result.status == "unresolved_flat_cap_material_labels"


def test_foreign_edge_revision_and_caller_stop_cannot_create_a_boundary_receipt() -> None:
    """
    Native incidence and fixed shared allocation remain mandatory even when geometry is coincident.
    """
    embedding, chain, incidence = inputs(0)
    with pytest.raises(ValueError, match="SAME native revision"):
        replace(incidence, curve=replace(incidence.curve, revision="foreign"))
    with pytest.raises(ValueError, match="SAME actual face/curve"):
        adopt(
            embedding,
            chain,
            chain.bindings[0],
            replace(incidence, curve=replace(incidence.curve)),
            checkpoint,
        )
    calls = 0

    def stop() -> None:
        """
        Stop after original cut comparison before the receipt can be constructed.
        """
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("cap adoption stopped")

    with pytest.raises(RuntimeError, match="adoption stopped"):
        adopt(embedding, chain, chain.bindings[0], incidence, stop)
