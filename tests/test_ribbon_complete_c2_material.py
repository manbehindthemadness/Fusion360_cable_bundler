"""
Check actual C2 path extraction and local increment bounds independently of an isometry claim.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from artifacts.verification.resume3216.basis import Basis
from artifacts.verification.resume3216.field import Midsurface
from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.c2_material import (
    discrepancy,
    labels,
    measure,
    prepare,
)
from experiments.experiment_ribbon_complete.curve_lengths import Controls
from experiments.experiment_ribbon_complete.root_profiles import partition


def checkpoint() -> None:
    """
    Leave these finite unit examples free of wall-clock assumptions.
    """


def surface() -> Midsurface:
    """
    Store exactly representable affine world coordinates on a nonuniform C2 basis.
    """
    basis = Basis((Fraction(0), Fraction(1, 8), Fraction(5, 2)))
    return Midsurface(
        basis,
        tuple(
            tuple(Vector3(float(i), float(q), float(2 * i)) for q in (-2, 0, 2))
            for i in range(basis.count)
        ),
    )


@pytest.mark.parametrize("lines", (1, 2, 5, 10))
def test_labels_retain_lobe_center_and_ordered_shared_partition_seams(lines: int) -> None:
    """
    Outer-lobe asymmetry cannot redefine the nominal conductor center.
    """
    roots = partition(lines, 0.75)
    values = tuple(labels(root) for root in roots)
    assert all(a < b < c for a, b, c in values)
    assert all(a[2] == b[0] for a, b in zip(values, values[1:]))
    for root, (_, center, _) in zip(roots, values):
        top = root.edges[0].geometry
        assert center == Fraction(top.controls[1][0])
    if lines > 1:
        assert values[0][1] != (values[0][0] + values[0][2]) / 2


def test_original_nonuniform_surface_and_all_three_world_paths_are_preserved() -> None:
    """
    Independent tensor evaluation agrees at endpoints and internal source coordinates.
    """
    original = surface()
    root = partition(2, 0.75)[0]
    source = prepare(original, Fraction(2), "unit stored controls", checkpoint)
    audit = measure(source, root, checkpoint)
    assert audit.source is source and source.surface is original and audit.root is root
    assert audit.pairwise_upper_mm == Fraction(0) and len(audit.spans) == 2
    for span in audit.spans:
        for q, curve in zip(audit.q_mm, span.curves):
            for t in (Fraction(0), Fraction(2, 7), Fraction(1)):
                level = curve
                while len(level) > 1:
                    level = tuple(
                        tuple((1 - t) * x + t * y for x, y in zip(a, b))
                        for a, b in zip(level, level[1:])
                    )
                u = span.low + t * (span.high - span.low)
                assert level[0] == original.jet(u, (q / 2 + 1) / 2).point


def test_local_extension_cannot_cancel_against_later_contraction() -> None:
    """
    Collinear monotone paths share endpoints and total length but differ on local intervals.
    """
    # Center speed is five. Left first extends, then contracts, staying monotone.
    center: Controls = tuple((Fraction(i), Fraction(0), Fraction(0)) for i in range(6))
    shifted: Controls = tuple(
        (Fraction(i) + offset, Fraction(0), Fraction(0))
        for i, offset in enumerate(map(Fraction, (0, 1, 1, 1, 1, 0)))
    )
    assert shifted[0] == center[0] and shifted[-1] == center[-1]
    assert discrepancy(shifted, center, checkpoint) == 2
    assert discrepancy(center, shifted, checkpoint) == 2
    assert discrepancy(center, center, checkpoint) == 0


def test_changed_world_controls_are_measured_instead_of_inheriting_a_zero_bound() -> None:
    """
    A replacement source recomputes its exact spans and retains nonzero local distortion.
    """
    original = surface()
    source = prepare(original, Fraction(2), "first field", checkpoint)
    rows = list(original.rows)
    rows[2] = (Vector3(2, -1.5, 4), rows[2][1], rows[2][2])
    changed = Midsurface(original.basis, tuple(rows))
    successor = replace(source, surface=changed, checkpoint=checkpoint)
    assert successor.surface is changed and successor.spans != source.spans
    audit = measure(successor, partition(2, 0.75)[0], checkpoint)
    assert audit.pairwise_upper_mm > 0


def test_unsupported_or_outside_labels_and_work_stops_are_not_silently_skipped() -> None:
    """
    Invalid source mappings reject and the caller's resource exception propagates.
    """
    source = prepare(surface(), Fraction(1, 10), "too narrow for root", checkpoint)
    with pytest.raises(ValueError, match="in-domain"):
        measure(source, partition(2, 0.75)[0], checkpoint)
    with pytest.raises(ValueError, match="provenance"):
        prepare(surface(), Fraction(2), "", checkpoint)

    def stop() -> None:
        """
        Represent the caller's exhausted shared allocation without renewal.
        """
        raise RuntimeError("shared work exhausted")

    with pytest.raises(RuntimeError, match="shared work exhausted"):
        prepare(surface(), Fraction(2), "bounded field", stop)
