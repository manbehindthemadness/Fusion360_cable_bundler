"""
Bound common material cap labels on actual native bend-face boundary traces.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, derivative, elevate, multiply

from .native_cap_chain import ConformingCapChain, profile_rates
from .native_cap_material import CapMaterialBinding
from .native_face_condition import NativeFaceCondition
from .native_material_chart import NativeSurfaceSnapshot
from .native_trim_boundary import NativeTrimCurve
from .spatial_frame import split_at


@dataclass(frozen=True)
class NativeFaceCoedge:
    """
    Retain the original co-edge geometry under its actual face snapshot and body revision.

    Capture adapters establish face/edge incidence and complete single-span
    Bezier provenance. This is not a guessed edge-to-co-edge parameter mapping.
    """

    native: NativeSurfaceSnapshot
    curve: NativeTrimCurve


def trace_bounds(
    curve: NativeTrimCurve, phase: Fraction, interval: tuple[Fraction, Fraction]
) -> tuple[Fraction, Fraction, Fraction, Fraction]:
    """
    Enclose UV discrepancy and profile-progress derivatives over a complete positive rational trace.
    """
    weights = curve.weights
    count = len(weights)
    numerator = tuple(p[1] * w for p, w in zip(curve.controls, weights))
    difference = add(elevate(numerator, count), multiply(interval, weights), Fraction(-1))
    elevated_weights = elevate(weights, count)
    dv = max(abs(x) / w for x, w in zip(difference, elevated_weights))
    du = max(abs(p[0] - phase) for p in curve.controls)
    quotient = elevate(
        add(
            multiply(derivative(numerator), weights),
            multiply(numerator, derivative(weights)),
            Fraction(-1),
        ),
        2 * (count - 1),
    )
    denominator = multiply(weights, weights)
    rates = tuple(x / w for x, w in zip(quotient, denominator))
    return du, dv, min(rates), max(rates)


@dataclass(frozen=True)
class NativeCapFaceEvidence:
    """
    Own the exact source objects and derived bounds used by one boundary qualification.
    """

    condition: NativeFaceCondition
    chain: ConformingCapChain
    binding: CapMaterialBinding
    coedge: NativeFaceCoedge
    reversed_coedge: bool | None
    phase: Fraction
    world_upper_mm: Fraction | None
    label_upper_mm: Fraction | None


@dataclass(frozen=True)
class NativeCapFaceBoundary:
    """
    Retain whole-curve world/physical-label compatibility, not a full trim/interior/material-metric pass.
    """

    condition: NativeFaceCondition
    chain: ConformingCapChain
    binding: CapMaterialBinding
    coedge: NativeFaceCoedge
    reversed_coedge: bool | None
    phase: Fraction
    world_upper_mm: Fraction | None
    label_upper_mm: Fraction | None
    status: str
    evidence: NativeCapFaceEvidence

    def __post_init__(self) -> None:
        """
        Prevent chart or source replacement from retaining a previously qualified boundary receipt.
        """
        if self.coedge.native is not self.condition.native or not any(
            b is self.binding for b in self.chain.bindings
        ):
            raise ValueError("The SAME native face and owned cap-chain binding required")
        evidence = self.evidence
        if (
            evidence.condition is not self.condition
            or evidence.chain is not self.chain
            or evidence.binding is not self.binding
            or evidence.coedge is not self.coedge
            or evidence.reversed_coedge != self.reversed_coedge
            or evidence.phase != self.phase
            or evidence.world_upper_mm != self.world_upper_mm
            or evidence.label_upper_mm != self.label_upper_mm
        ):
            raise ValueError("Boundary qualification must retain the SAME owned evidence")
        if self.status == "qualified_native_cap_face_labels" and (
            type(self.reversed_coedge) is not bool
            or self.world_upper_mm is None
            or self.label_upper_mm is None
            or type(self.world_upper_mm) is not Fraction
            or type(self.label_upper_mm) is not Fraction
            or min(self.world_upper_mm, self.label_upper_mm) < 0
            or self.world_upper_mm + self.label_upper_mm > Fraction(1, 100)
        ):
            raise ValueError("A complete combined0.01mm boundary proof required")

    def material_parameter(self, coordinate: Fraction) -> Fraction:
        """
        Decode original V from the normalized original co-edge Bezier parameter.
        """
        if (
            self.status != "qualified_native_cap_face_labels"
            or type(coordinate) is not Fraction
            or not 0 <= coordinate <= 1
        ):
            raise ValueError("A qualified boundary and exact unit co-edge parameter required")
        t = 1 - coordinate if self.reversed_coedge else coordinate
        a, b = self.binding.interval
        return a + (b - a) * t

    def cap_coordinate(self, coordinate: Fraction) -> Fraction:
        """
        Return the corresponding converted-cap parameter through the explicit inverse label map.
        """
        mapping = self.binding.mapping
        if mapping is None:
            raise ValueError("An owned qualified cap material map required")
        return mapping.native_coordinate(self.material_parameter(coordinate))

    def native_parameters(self, coordinate: Fraction) -> tuple[Fraction, Fraction]:
        """
        Evaluate original native UV geometry without snapping or changing its parameterization.
        """
        self.material_parameter(coordinate)
        curve = self.coedge.curve
        denominator = split_at(curve.weights, coordinate)[0][-1]
        values = tuple(
            split_at(tuple(p[k] * w for p, w in zip(curve.controls, curve.weights)), coordinate)[0][
                -1
            ]
            / denominator
            for k in range(2)
        )
        return values[0], values[1]


def adopt(
    condition: NativeFaceCondition,
    chain: ConformingCapChain,
    binding: CapMaterialBinding,
    coedge: NativeFaceCoedge,
    checkpoint: Callable[[], None],
) -> NativeCapFaceBoundary:
    """
    Verify one explicit whole-curve correspondence instead of assuming native edge/face parameters agree.

    The native cap row must be the actual row used by the cap proof. Uniform
    native partial bounds transfer UV error to world distance. Original profile
    derivatives and s=(R*phase-sine*q)/cosine+before transfer label discrepancy
    to physical s/q/b millimeters. The cap-chain error is charged once alongside
    world and label errors. Strict positive V progress is independently required.
    """
    checkpoint()
    native = condition.native
    if (
        coedge.native is not native
        or binding.native.revision != native.revision
        or coedge.curve.edge_id != binding.native.edge_id
    ):
        raise ValueError("The SAME native face, revision and shared cap edge required")
    if not any(b is binding for b in chain.bindings) or binding.mapping is None:
        raise ValueError("An owned cap-chain binding required")
    indices = [
        i
        for i, source in enumerate(binding.sources)
        if source.region == (native.piece_index, "bend")
    ]
    if len(indices) != 1:
        raise ValueError("The original ordered bend cap source required")
    index = indices[0]
    chart = condition.embedding.chart
    cap_row = native.rows[-1 if index == 0 else 0]
    source = binding.sources[index]
    if source.controls != cap_row or source.profile != chart.arc:
        raise ValueError("The SAME actual native bend cap controls/profile required")
    basis = chart.volume.source.surface.basis
    phase = basis.breaks[-1 if index == 0 else 0]
    low, high = basis.breaks[0], basis.breaks[-1]
    if any(not low <= u <= high or not 0 <= v <= 1 for u, v in coedge.curve.controls):
        raise ValueError("Original native UV controls must remain inside the qualified domain")
    accepted = []
    if (
        condition.status == "certified_native_face_parameter_conditioning"
        and chain.status == "qualified_conforming_cap_material_chain"
        and condition.partial_upper is not None
        and chain.accuracy_upper_mm is not None
    ):
        q_rate, b_rate = profile_rates(chart.arc)
        volume = chart.volume
        for reverse in (False, True):
            checkpoint()
            raw = coedge.curve
            oriented = (
                NativeTrimCurve(
                    raw.edge_id, tuple(reversed(raw.controls)), tuple(reversed(raw.weights))
                )
                if reverse
                else raw
            )
            du, dv, lower, upper = trace_bounds(oriented, phase, binding.interval)
            if lower <= 0 or upper / lower > 1024:
                continue
            world = condition.partial_upper[0] * du + condition.partial_upper[1] * dv
            labels = (
                volume.radius_mm / volume.cosine * du
                + ((1 + abs(volume.sine / volume.cosine)) * q_rate + b_rate) * dv
            )
            if chain.accuracy_upper_mm + world + labels <= Fraction(1, 100):
                accepted.append((reverse, chain.accuracy_upper_mm + world, labels))
    reverse, world, labels = accepted[0] if len(accepted) == 1 else (None, None, None)
    status = (
        "qualified_native_cap_face_labels"
        if reverse is not None
        else "unresolved_native_cap_face_labels"
    )
    checkpoint()
    evidence = NativeCapFaceEvidence(
        condition, chain, binding, coedge, reverse, phase, world, labels
    )
    return NativeCapFaceBoundary(
        condition, chain, binding, coedge, reverse, phase, world, labels, status, evidence
    )
