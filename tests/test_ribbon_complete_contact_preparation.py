"""
Verify source-owned preparation reuse without reusing contact acceptance.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.contact_cell import enclose
from experiments.experiment_ribbon_complete.contact_pairs import children
from experiments.experiment_ribbon_complete.flat_chart import MaterialCut, straight
from experiments.experiment_ribbon_complete.volume_boundary import VolumeSpan
from experiments.experiment_ribbon_complete.volume_field import BendVolume
from tests.test_ribbon_complete_contact_cell import box
from tests.test_ribbon_complete_flat_chart import piece
from tests.test_ribbon_complete_volume_injectivity import candidate, checkpoint


def test_children_reuse_only_original_bend_span_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Descendants of one owner avoid re-extraction; a separate preparation recomputes normally.
    """
    volume = candidate()
    original = volume.span
    calls: dict[int, int] = {}

    def counted(owner: BendVolume, index: int) -> VolumeSpan:
        """
        Count actual extraction without changing controls or metadata.
        """
        assert owner is volume
        calls[index] = calls.get(index, 0) + 1
        return original(index)

    monkeypatch.setattr(BendVolume, "span", counted)
    parent = enclose(volume, box(), checkpoint)
    baseline = dict(calls)
    assert baseline and all(n == 1 for n in baseline.values())
    left, right = children(parent, checkpoint)
    assert left.preparation is right.preparation is parent.preparation
    assert calls == baseline
    fresh = enclose(volume, box(), checkpoint)
    assert fresh.preparation is not parent.preparation
    assert calls == {index: 2 for index in baseline}
    assert fresh.model == parent.model and fresh.residual_mm == parent.residual_mm


def test_preparation_cannot_transfer_to_an_equal_but_distinct_owner() -> None:
    """
    Source identity remains required, and a flat cannot inherit a bend preparation.
    """
    volume = candidate()
    parent = enclose(volume, box(), checkpoint)
    with pytest.raises(ValueError, match="SAME original"):
        enclose(replace(volume), box(), checkpoint, preparation=parent.preparation)
    with pytest.raises(ValueError, match="flat chart"):
        enclose(straight(piece()), box(), checkpoint, preparation=parent.preparation)


def test_cached_normal_still_obeys_caller_resource_stop() -> None:
    """
    A cached exact span does not bypass cancellation or grant another work allocation.
    """
    parent = enclose(candidate(), box(), checkpoint)
    assert parent.preparation is not None

    def stop() -> None:
        """
        Stop before returning even an already-prepared span.
        """
        raise RuntimeError("caller stopped")

    with pytest.raises(RuntimeError, match="caller stopped"):
        parent.preparation.normal(0, stop)


def test_flat_cut_preparation_belongs_to_each_frozen_cell() -> None:
    """
    Equal clones and changed cuts cannot inherit a prior cell's prepared models.
    """
    parent = enclose(straight(piece()), box(0, 2), checkpoint)
    prepared = parent.cut_models
    assert prepared is not None and len(prepared) == 2
    assert parent.cut_models is prepared
    clone = replace(parent)
    assert clone.cut_models == prepared and clone.cut_models is not prepared
    changed = replace(parent, region=replace(parent.region, high=MaterialCut(Fraction(-3))))
    assert changed.cut_models is None
    assert parent.cut_models is prepared
