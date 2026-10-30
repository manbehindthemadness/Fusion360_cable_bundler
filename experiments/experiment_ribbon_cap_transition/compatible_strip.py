"""
Generate locally regular developable strips from a compatible pair of edges.

This is a constrained coordinate chart,not elastic equilibrium or a global
contact/containment certificate. It does not classify physical turn-event sides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from typing import Callable

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.inspection.capture import transported
from devtools.ribbon_analysis.pinch import BendModel, PinchLimit

from .constraint_policy import ConstraintPolicy, Rule, current
from .director_motion_transport import DirectorMotion, integrate_motion
from .director_routing_field import RoutingField
from .director_transport import INITIAL, State, interpolate_pose, material_lane


class BendMapping(Enum):
    """
    Distinguish historical global softening from a near-limit-only shoulder.
    """

    GLOBAL_SOFT = "global-softening"
    NEAR_LIMIT = "identity-below-90-percent"


def map_turn(raw_turn: float, limit: float, mapping: BendMapping) -> float:
    """
    Preserve historical mapping or retain requests below90%of the internal limit.

    The near-limit rational shoulder matches value and first two derivatives at
    the knee. Its asymptote is the unchanged limit; two inward floating-point
    steps keep rounded saturated values strictly inside it. No geometry repair
    or increase in the permitted bend occurs.
    """
    if not math.isfinite(raw_turn) or not math.isfinite(limit) or limit <= 0:
        raise ValueError("A finite turn and positive finite limit are required.")
    if mapping is BendMapping.GLOBAL_SOFT:
        return raw_turn / math.hypot(1.0, raw_turn / limit)
    if mapping is not BendMapping.NEAR_LIMIT:
        raise ValueError("Choose a registered bend mapping.")
    knee, shoulder = 0.9 * limit, 0.1 * limit
    if abs(raw_turn) <= knee:
        return raw_turn
    excess = (abs(raw_turn) - knee) / shoulder
    magnitude = knee + shoulder * excess / math.hypot(1.0, excess)
    inside = math.nextafter(math.nextafter(limit, 0.0), 0.0)
    return math.copysign(min(magnitude, inside), raw_turn)


@dataclass(frozen=True)
class CarrierSample:
    """
    Retain center progress,tangent turning and ruling motion in the carrier parameter.
    """

    progress_mm: float
    turn: float
    eta: float
    eta_u: float


@dataclass(frozen=True)
class CompatibleField:
    """
    Map finite raw Fourier coordinates into a locally valid material-strip field.

    L=raw.length_mm is a carrier budget, not material center length. With h the
    halfwidth and g=eta_u, the center advances c=L-h*abs(g); a lane advances c+q*g.
    Analytic Fourier derivative bounds scale g to keep minimum material J>.1 for
    every u. Turning is bounded so center k*reach<.78 and every lane radius>3.1D.
    No sampled rejection, endpoint snapping or later geometric repair enforces
    these local bounds. The actual transported/interpolated geometry still needs
    independent numerical/native checks. An explicit diagnostic policy may remove
    either named bend cap; material regularity and independent measurements remain.
    """

    raw: RoutingField
    bend_mapping: BendMapping = BendMapping.GLOBAL_SOFT
    constraints: ConstraintPolicy = dataclass_field(default_factory=current)
    ruling_scale: float = dataclass_field(init=False)

    def __post_init__(self) -> None:
        """
        Freeze the global ruling normalization before transport or fitting.
        """
        if not isinstance(self.constraints, ConstraintPolicy):
            raise ValueError("Compatible fields require an explicit constraint policy.")
        if self.constraints.bend_model is BendModel.PINCH and self.lines == 1:
            object.__setattr__(self, "ruling_scale", 1.0)
            return
        _, b, c, d = self.raw.ruling
        derivative_bound = (
            2 * math.pi * (abs(b) + abs(c) + 2 * abs(d) + 2 * abs(self.raw.extra_ruling))
        )
        allowed = 0.9 * self.carrier_length_mm / (1.9 * self.half_width_mm)
        object.__setattr__(self, "ruling_scale", allowed / math.hypot(allowed, derivative_bound))

    @property
    def carrier_length_mm(self) -> float:
        """
        Return the progress budget of the locally faster boundary envelope.
        """
        return self.raw.length_mm

    @property
    def lines(self) -> int:
        """
        Preserve the fixed ordered conductor count.
        """
        return self.raw.lines

    @property
    def diameter_mm(self) -> float:
        """
        Preserve the fixed conductor diameter.
        """
        return self.raw.diameter_mm

    @property
    def half_width_mm(self) -> float:
        """
        Preserve the material boundary offsets including the original padding.
        """
        return self.raw.half_width_mm

    def carrier(self, u: float) -> CarrierSample:
        """
        Return analytically bounded progress and turning without a hard clipping step.
        """
        k_raw, eta_raw, gradient_raw = self.raw.sample(u)
        length, half = self.carrier_length_mm, self.half_width_mm
        eta, eta_u = eta_raw * self.ruling_scale, gradient_raw * length * self.ruling_scale
        redistribution = (
            0.0
            if self.constraints.bend_model is BendModel.PINCH and self.lines == 1
            else half * abs(eta_u)
        )
        progress = length - redistribution
        value = CarrierSample(progress, k_raw * length, eta, eta_u)
        limit = self.turn_limit(value)
        turn = map_turn(value.turn, limit, self.bend_mapping) if limit is not None else value.turn
        return CarrierSample(progress, turn, eta, eta_u)

    def turn_limit(self, value: CarrierSample) -> float | None:
        """
        Share the same versioned geometric bound with transport and redistribution.
        """
        if self.constraints.bend_model is BendModel.PINCH:
            if not self.constraints.enabled(Rule.LANE_BEND):
                return None
            minimum_progress = (
                value.progress_mm
                if self.lines == 1
                else self.carrier_length_mm - 2 * self.half_width_mm * abs(value.eta_u)
            )
            return PinchLimit(self.constraints.pinch_percent).turn_bound(
                minimum_progress, value.eta, self.diameter_mm, self.lines
            )
        minimum_lane_progress = self.carrier_length_mm - 2 * self.half_width_mm * abs(value.eta_u)
        reach = math.hypot(self.half_width_mm, self.diameter_mm / 2)
        limits = []
        if self.constraints.enabled(Rule.CENTRE_BEND):
            limits.append(0.78 * value.progress_mm / reach)
        if self.constraints.enabled(Rule.LANE_BEND):
            limits.append(minimum_lane_progress / (3.1 * self.diameter_mm))
        return min(limits) if limits else None

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Return intrinsic curvature, eta, and eta_s in actual center material length.
        """
        value = self.carrier(u)
        return value.turn / value.progress_mm, value.eta, value.eta_u / value.progress_mm

    def motion(self, u: float) -> DirectorMotion:
        """
        Supply explicit variable progress to the shared unit-rotation integrator.
        """
        value = self.carrier(u)
        return DirectorMotion(value.progress_mm, value.turn, value.eta)


@dataclass(frozen=True)
class CompatiblePath:
    """
    Keep variable-progress strip geometry distinct from constant-arclength paths.
    """

    field: CompatibleField
    states: tuple[State, ...]
    rates: tuple[State, ...]

    def pose(self, u: float) -> tuple[State, State]:
        """
        Evaluate the shared dense interpolation without changing the integrated frame.
        """
        return interpolate_pose(self.states, self.rates, u)

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Differentiate the actual material lane in the carrier parameter.
        """
        if not math.isfinite(offset_mm) or abs(offset_mm) > self.field.half_width_mm:
            raise ValueError("Compatible lane offset lies outside the material width.")
        state, derivative = self.pose(u)
        value = self.field.carrier(u)
        return material_lane(state, derivative, offset_mm, value.eta, value.eta_u)


def integrate_compatible(
    field: CompatibleField,
    steps: int,
    checkpoint: Callable[[], None],
    *,
    initial: State = INITIAL,
) -> CompatiblePath:
    """
    Transport one fixed compatible field with no search,repair or native construction.
    """
    states, rates = integrate_motion(field.motion, steps, checkpoint, initial=initial)
    path = CompatiblePath(field, states, rates)
    transported(path, steps)
    return path
