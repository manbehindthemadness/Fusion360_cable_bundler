"""
Pure application domain for harness definitions and validation.
"""

from .codec import DefinitionParseError, dumps, loads
from .model import (
    DEFAULT_WIRE_DIAMETER_MM,
    SCHEMA_VERSION,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    PathwayDefinition,
    PathwayEndpoint,
    RefineGeometry,
    RoutingMode,
    StandaloneEndDefinition,
    StripePattern,
    WireAppearanceReference,
    WireColor,
    WireGroupDefinition,
    WireMaterialOverrides,
    WireMaterialSettings,
    WireStripe,
)
from .naming import next_available_name
from .validation import ValidationIssue, validate_harness

__all__ = [
    "DEFAULT_WIRE_DIAMETER_MM",
    "SCHEMA_VERSION",
    "Connection",
    "ControlKind",
    "ControlStructure",
    "DefinitionParseError",
    "HarnessDefinition",
    "JunctionDefinition",
    "JunctionPathwayRelationship",
    "PathwayDefinition",
    "PathwayEndpoint",
    "RefineGeometry",
    "RoutingMode",
    "StandaloneEndDefinition",
    "StripePattern",
    "ValidationIssue",
    "WireAppearanceReference",
    "WireGroupDefinition",
    "WireColor",
    "WireMaterialOverrides",
    "WireMaterialSettings",
    "WireStripe",
    "dumps",
    "loads",
    "next_available_name",
    "validate_harness",
]
