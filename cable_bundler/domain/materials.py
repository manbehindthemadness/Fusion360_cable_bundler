"""
Define cable material, appearance, pullback, weld, and stripe value objects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class StripePattern(str, Enum):
    """
    Describe how an insulation-identification stripe repeats along a cable.
    """

    LONGITUDINAL = "longitudinal"
    DASHED = "dashed"
    HELICAL = "helical"


@dataclass(frozen=True)
class CableColor:
    """
    Store a portable named RGB color independently of Fusion appearances.
    """

    name: str
    red: int
    green: int
    blue: int

    def __post_init__(self) -> None:
        """
        Require a name and three byte-sized color channels.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Cable color name must not be empty.")
        for channel in (self.red, self.green, self.blue):
            if isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 255:
                raise ValueError("Cable color channels must be integers from 0 through 255.")

    @property
    def hex_rgb(self) -> str:
        """
        Return the color in HTML-compatible hexadecimal form.
        """
        return f"#{self.red:02X}{self.green:02X}{self.blue:02X}"


DEFAULT_CABLE_COLOR = CableColor("Black", 32, 32, 32)
DEFAULT_PULLBACK_COLOR = CableColor("Copper", 184, 115, 51)
DEFAULT_WELD_COLOR = CableColor("Silver", 192, 192, 192)


@dataclass(frozen=True)
class CableAppearanceReference:
    """
    Identify an appearance in one of Fusion's installed material libraries.

    Names are retained for display and diagnostics while the stable library and
    appearance IDs drive host lookup.
    """

    library_id: str
    library_name: str
    appearance_id: str
    appearance_name: str

    def __post_init__(self) -> None:
        """
        Require complete lookup and display information.
        """
        for value in (
            self.library_id,
            self.library_name,
            self.appearance_id,
            self.appearance_name,
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Fusion appearance references require nonempty IDs and names.")


class PullbackMode(str, Enum):
    """
    Identify how a cable pullback amount is measured.
    """

    PERCENT = "percent"
    DISTANCE = "distance"


@dataclass(frozen=True)
class CablePullbackSettings:
    """
    Store the finalized leaf-connection pullback and its visual material.

    Percent values are relative to the cable diameter. Distance values are in
    millimeters. Preview and ordinary solid geometry do not use these settings.
    """

    mode: PullbackMode = PullbackMode.PERCENT
    value: float = 200.0
    color: CableColor = DEFAULT_PULLBACK_COLOR
    appearance: Optional[CableAppearanceReference] = None

    def __post_init__(self) -> None:
        """
        Require a supported mode, nonnegative amount, and portable appearance.
        """
        if not isinstance(self.mode, PullbackMode):
            raise ValueError("Pullback mode must be percent or distance.")
        if (
            isinstance(self.value, bool)
            or not isinstance(self.value, (int, float))
            or not math.isfinite(self.value)
            or self.value < 0.0
        ):
            raise ValueError("Pullback value must be finite and nonnegative.")
        if not isinstance(self.color, CableColor):
            raise ValueError("Pullback color must be a cable color.")
        if self.appearance is not None and not isinstance(
            self.appearance, CableAppearanceReference
        ):
            raise ValueError("Pullback appearance must reference a Fusion appearance.")


@dataclass(frozen=True)
class CableWeldSettings:
    """
    Store a finalized leaf-face weld percentage and its visual material.

    The percentage scales the resolved conductor diameter. Its resulting radius
    also defines how far the weld reaches from the target into the conductor.
    """

    value: float = 150.0
    color: CableColor = DEFAULT_WELD_COLOR
    appearance: Optional[CableAppearanceReference] = None

    def __post_init__(self) -> None:
        """
        Require a nonnegative percentage and portable appearance.
        """
        if (
            isinstance(self.value, bool)
            or not isinstance(self.value, (int, float))
            or not math.isfinite(self.value)
            or self.value < 0.0
        ):
            raise ValueError("Weld percentage must be finite and nonnegative.")
        if not isinstance(self.color, CableColor):
            raise ValueError("Weld color must be a cable color.")
        if self.appearance is not None and not isinstance(
            self.appearance, CableAppearanceReference
        ):
            raise ValueError("Weld appearance must reference a Fusion appearance.")


@dataclass(frozen=True)
class CableStripe:
    """
    Define one ordered procedural stripe on the insulation surface.

    ``repeat_mm`` is required for dashed and helical patterns and unused by a
    continuous longitudinal stripe. ``angle_deg`` locates the stripe around the
    cable circumference at its starting section.
    """

    color: CableColor
    width_mm: float
    pattern: StripePattern = StripePattern.LONGITUDINAL
    angle_deg: float = 0.0
    repeat_mm: Optional[float] = None

    def __post_init__(self) -> None:
        """
        Reject stripe dimensions that cannot drive procedural geometry.
        """
        if not isinstance(self.color, CableColor):
            raise ValueError("Stripe color must be a cable color.")
        if not isinstance(self.pattern, StripePattern):
            raise ValueError("Stripe pattern is not supported.")
        if (
            isinstance(self.width_mm, bool)
            or not isinstance(self.width_mm, (int, float))
            or not math.isfinite(self.width_mm)
            or self.width_mm <= 0
        ):
            raise ValueError("Stripe width must be a finite positive value in millimeters.")
        if (
            isinstance(self.angle_deg, bool)
            or not isinstance(self.angle_deg, (int, float))
            or not math.isfinite(self.angle_deg)
        ):
            raise ValueError("Stripe angle must be finite degrees.")
        if self.repeat_mm is not None and (
            isinstance(self.repeat_mm, bool)
            or not isinstance(self.repeat_mm, (int, float))
            or not math.isfinite(self.repeat_mm)
            or self.repeat_mm <= 0
        ):
            raise ValueError("Stripe repeat must be a finite positive value in millimeters.")
        if self.pattern is not StripePattern.LONGITUDINAL and self.repeat_mm is None:
            raise ValueError("Dashed and helical stripes require a positive repeat length.")


def _validate_visual_overrides(
    main_color: Optional[CableColor],
    appearance: Optional[CableAppearanceReference],
    stripes: Optional[tuple[CableStripe, ...]],
) -> None:
    """
    Validate the shared appearance and stripe inheritance contract.
    """
    if main_color is not None and not isinstance(main_color, CableColor):
        raise ValueError("Main color override must be a cable color.")
    if appearance is not None and not isinstance(appearance, CableAppearanceReference):
        raise ValueError("Main appearance override must reference a Fusion appearance.")
    if main_color is None and appearance is not None:
        raise ValueError("A main appearance override requires a main color override.")
    if stripes is not None and (
        not isinstance(stripes, tuple)
        or not all(isinstance(stripe, CableStripe) for stripe in stripes)
    ):
        raise ValueError("Stripe override must be an ordered tuple of stripe definitions.")


def _validate_material_feature_overrides(
    main_color: Optional[CableColor],
    appearance: Optional[CableAppearanceReference],
    stripes: Optional[tuple[CableStripe, ...]],
    pullback: Optional[CablePullbackSettings],
    weld: Optional[CableWeldSettings],
) -> None:
    """
    Validate optional visual, pullback, and weld feature overrides.
    """
    _validate_visual_overrides(main_color, appearance, stripes)
    if pullback is not None and not isinstance(pullback, CablePullbackSettings):
        raise ValueError("Pullback override must contain valid pullback settings.")
    if weld is not None and not isinstance(weld, CableWeldSettings):
        raise ValueError("Weld override must contain valid weld settings.")


@dataclass(frozen=True)
class CableMaterialSettings:
    """
    Store resolved harness-level defaults for cable construction and identification.
    """

    insulation_material: str = "PVC"
    main_color: CableColor = DEFAULT_CABLE_COLOR
    appearance: Optional[CableAppearanceReference] = None
    stripes: tuple[CableStripe, ...] = ()
    conductor_material: str = "Copper"
    shielding: str = ""
    dielectric_material: str = ""
    manufacturer: str = ""
    part_number: str = ""
    notes: str = ""
    pullback: CablePullbackSettings = CablePullbackSettings()
    weld: CableWeldSettings = CableWeldSettings()

    def __post_init__(self) -> None:
        """
        Require usable material labels while permitting optional catalog metadata.
        """
        if not isinstance(self.insulation_material, str) or not self.insulation_material.strip():
            raise ValueError("Insulation material must not be empty.")
        if not isinstance(self.conductor_material, str) or not self.conductor_material.strip():
            raise ValueError("Conductor material must not be empty.")
        if not isinstance(self.main_color, CableColor):
            raise ValueError("Main insulation color must be a cable color.")
        if self.appearance is not None and not isinstance(
            self.appearance, CableAppearanceReference
        ):
            raise ValueError("Main insulation appearance must reference a Fusion appearance.")
        if not isinstance(self.stripes, tuple) or not all(
            isinstance(stripe, CableStripe) for stripe in self.stripes
        ):
            raise ValueError("Cable stripes must be an ordered tuple of stripe definitions.")
        for value in (
            self.shielding,
            self.dielectric_material,
            self.manufacturer,
            self.part_number,
            self.notes,
        ):
            if not isinstance(value, str):
                raise ValueError("Cable catalog metadata must be text.")
        if not self.shielding.strip() and self.dielectric_material.strip():
            raise ValueError("Dielectric material requires shielding.")
        if not isinstance(self.pullback, CablePullbackSettings):
            raise ValueError("Pullback must contain valid pullback settings.")
        if not isinstance(self.weld, CableWeldSettings):
            raise ValueError("Weld must contain valid weld settings.")


@dataclass(frozen=True)
class CableMaterialOverrides:
    """
    Override selected harness material defaults for one persistent cable group.

    A null stripes value inherits the harness stripe collection. An explicit
    empty tuple suppresses every inherited stripe.
    """

    insulation_material: Optional[str] = None
    main_color: Optional[CableColor] = None
    appearance: Optional[CableAppearanceReference] = None
    stripes: Optional[tuple[CableStripe, ...]] = None
    conductor_material: Optional[str] = None
    shielding: Optional[str] = None
    dielectric_material: Optional[str] = None
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    notes: Optional[str] = None
    pullback: Optional[CablePullbackSettings] = None
    weld: Optional[CableWeldSettings] = None

    def __post_init__(self) -> None:
        """
        Validate explicit overrides while preserving null inheritance markers.
        """
        for value, label in (
            (self.insulation_material, "Insulation material"),
            (self.conductor_material, "Conductor material"),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{label} override must not be empty.")
        _validate_material_feature_overrides(
            self.main_color, self.appearance, self.stripes, self.pullback, self.weld
        )
        for value in (
            self.shielding,
            self.dielectric_material,
            self.manufacturer,
            self.part_number,
            self.notes,
        ):
            if value is not None and not isinstance(value, str):
                raise ValueError("Cable catalog metadata overrides must be text.")

    def resolve(self, parent: CableMaterialSettings) -> CableMaterialSettings:
        """
        Merge these field-level overrides over harness defaults.
        """
        shielding = parent.shielding if self.shielding is None else self.shielding
        dielectric_material = (
            parent.dielectric_material
            if self.dielectric_material is None
            else self.dielectric_material
        )
        return CableMaterialSettings(
            insulation_material=(
                parent.insulation_material
                if self.insulation_material is None
                else self.insulation_material
            ),
            main_color=parent.main_color if self.main_color is None else self.main_color,
            appearance=(parent.appearance if self.main_color is None else self.appearance),
            stripes=parent.stripes if self.stripes is None else self.stripes,
            conductor_material=(
                parent.conductor_material
                if self.conductor_material is None
                else self.conductor_material
            ),
            shielding=shielding,
            dielectric_material=dielectric_material if shielding.strip() else "",
            manufacturer=parent.manufacturer if self.manufacturer is None else self.manufacturer,
            part_number=parent.part_number if self.part_number is None else self.part_number,
            notes=parent.notes if self.notes is None else self.notes,
            pullback=parent.pullback if self.pullback is None else self.pullback,
            weld=parent.weld if self.weld is None else self.weld,
        )


@dataclass(frozen=True)
class CableVisualOverrides:
    """
    Override one divided connection branch's construction and visual properties.

    A null diameter selects the cable end's equal share of its parent cable.
    Material and visual nulls inherit from the connected cable group, while an
    empty stripe tuple suppresses inherited stripes.
    """

    main_color: Optional[CableColor] = None
    appearance: Optional[CableAppearanceReference] = None
    stripes: Optional[tuple[CableStripe, ...]] = None
    diameter_mm: Optional[float] = None
    conductor_diameter_mm: Optional[float] = None
    insulation_material: Optional[str] = None
    conductor_material: Optional[str] = None
    shielding: Optional[str] = None
    dielectric_material: Optional[str] = None
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    pullback: Optional[CablePullbackSettings] = None
    weld: Optional[CableWeldSettings] = None

    def __post_init__(self) -> None:
        """
        Validate explicit branch overrides while retaining inheritance markers.
        """
        if self.diameter_mm is not None and (
            isinstance(self.diameter_mm, bool)
            or not isinstance(self.diameter_mm, (int, float))
            or not math.isfinite(self.diameter_mm)
            or self.diameter_mm <= 0.0
        ):
            raise ValueError("Connection diameter override must be finite and positive.")
        if self.conductor_diameter_mm is not None and (
            isinstance(self.conductor_diameter_mm, bool)
            or not isinstance(self.conductor_diameter_mm, (int, float))
            or not math.isfinite(self.conductor_diameter_mm)
            or self.conductor_diameter_mm <= 0.0
        ):
            raise ValueError("Conductor diameter must be finite and positive when specified.")
        for value, label in (
            (self.insulation_material, "Insulation material"),
            (self.conductor_material, "Conductor material"),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{label} override must not be empty.")
        for value in (
            self.shielding,
            self.dielectric_material,
            self.manufacturer,
            self.part_number,
        ):
            if value is not None and not isinstance(value, str):
                raise ValueError("Connection catalog metadata overrides must be text.")
        _validate_material_feature_overrides(
            self.main_color, self.appearance, self.stripes, self.pullback, self.weld
        )

    def resolve(self, parent: CableMaterialSettings) -> CableMaterialSettings:
        """
        Merge branch material and visual overrides over resolved group materials.
        """
        shielding = parent.shielding if self.shielding is None else self.shielding
        dielectric_material = (
            parent.dielectric_material
            if self.dielectric_material is None
            else self.dielectric_material
        )
        return CableMaterialSettings(
            insulation_material=(
                parent.insulation_material
                if self.insulation_material is None
                else self.insulation_material
            ),
            main_color=parent.main_color if self.main_color is None else self.main_color,
            appearance=parent.appearance if self.main_color is None else self.appearance,
            stripes=parent.stripes if self.stripes is None else self.stripes,
            conductor_material=(
                parent.conductor_material
                if self.conductor_material is None
                else self.conductor_material
            ),
            shielding=shielding,
            dielectric_material=dielectric_material if shielding.strip() else "",
            manufacturer=parent.manufacturer if self.manufacturer is None else self.manufacturer,
            part_number=parent.part_number if self.part_number is None else self.part_number,
            notes=parent.notes,
            pullback=parent.pullback if self.pullback is None else self.pullback,
            weld=parent.weld if self.weld is None else self.weld,
        )
