"""
Pure application domain for harness definitions and validation.
"""

from .codec import DefinitionParseError, dumps, loads
from .model import (
    DEFAULT_CABLE_DIAMETER_MM,
    SCHEMA_VERSION,
    AutoTransitionPreset,
    CableAppearanceReference,
    CableColor,
    CableGroupDefinition,
    CableMaterialOverrides,
    CableMaterialSettings,
    CableStripe,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    Metadata,
    PathwayDefinition,
    PathwayEndpoint,
    RefineGeometry,
    RoutingMode,
    StandaloneEndDefinition,
    StripePattern,
)
from .naming import next_available_name
from .validation import ValidationIssue, validate_harness

__all__ = [
    "DEFAULT_CABLE_DIAMETER_MM",
    "SCHEMA_VERSION",
    "AutoTransitionPreset",
    "Connection",
    "ControlKind",
    "ControlStructure",
    "DefinitionParseError",
    "HarnessDefinition",
    "JunctionDefinition",
    "JunctionPathwayRelationship",
    "Metadata",
    "PathwayDefinition",
    "PathwayEndpoint",
    "RefineGeometry",
    "RoutingMode",
    "StandaloneEndDefinition",
    "StripePattern",
    "ValidationIssue",
    "CableAppearanceReference",
    "CableGroupDefinition",
    "CableColor",
    "CableMaterialOverrides",
    "CableMaterialSettings",
    "CableStripe",
    "dumps",
    "loads",
    "next_available_name",
    "validate_harness",
]
