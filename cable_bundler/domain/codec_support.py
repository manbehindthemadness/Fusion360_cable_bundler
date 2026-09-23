"""
Shared validation primitives for the versioned harness codec.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Optional, Type, TypeVar
from uuid import UUID

from .materials import PullbackMode, StripePattern
from .model import (
    AttachmentTargetKind,
    AutoTransitionPreset,
    ControlKind,
    InterpolationSettings,
    PathwayEndpoint,
    RoutingMode,
)

EnumType = TypeVar(
    "EnumType",
    RoutingMode,
    ControlKind,
    PathwayEndpoint,
    StripePattern,
    AutoTransitionPreset,
    AttachmentTargetKind,
    PullbackMode,
)


class DefinitionParseError(ValueError):
    """
    Report invalid serialized harness data at a precise field path.
    """

    def __init__(self, path: str, message: str) -> None:
        """
        Initialize a structured parse error.
        """
        self.path = path
        self.reason = message
        super().__init__(f"{path}: {message}")


def require_mapping(raw_value: object, path: str) -> Mapping[str, Any]:
    """
    Require a mapping with string keys.
    """
    if not isinstance(raw_value, Mapping):
        raise DefinitionParseError(path, "expected an object")
    if not all(isinstance(key, str) for key in raw_value):
        raise DefinitionParseError(path, "expected string object keys")
    return raw_value


def require_value(value: Mapping[str, Any], key: str, path: str) -> object:
    """
    Require a named mapping value.
    """
    if key not in value:
        raise DefinitionParseError(path, "missing required field")
    return value[key]


def require_str(value: Mapping[str, Any], key: str, path: str) -> str:
    """
    Require a string field.
    """
    raw_value = require_value(value, key, path)
    if not isinstance(raw_value, str):
        raise DefinitionParseError(path, "expected a string")
    return raw_value


def require_int(value: Mapping[str, Any], key: str, path: str) -> int:
    """
    Require an integer field without accepting booleans.
    """
    raw_value = require_value(value, key, path)
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise DefinitionParseError(path, "expected an integer")
    return raw_value


def require_float(value: Mapping[str, Any], key: str, path: str) -> float:
    """
    Require a numeric field without accepting booleans.
    """
    raw_value = require_value(value, key, path)
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        raise DefinitionParseError(path, "expected a number")
    return float(raw_value)


def require_finite_nonnegative_float(raw_value: object, path: str) -> float:
    """
    Parse one persisted distance that may be zero but must remain finite.
    """
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        raise DefinitionParseError(path, "expected a number")
    parsed = float(raw_value)
    if not math.isfinite(parsed) or parsed < 0.0:
        raise DefinitionParseError(path, "expected a finite nonnegative number")
    return parsed


def optional_float(raw_value: object, path: str) -> Optional[float]:
    """
    Parse a nullable finite number.
    """
    if raw_value is None:
        return None
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        raise DefinitionParseError(path, "expected a number or null")
    parsed = float(raw_value)
    if not math.isfinite(parsed):
        raise DefinitionParseError(path, "expected a finite number or null")
    return parsed


def optional_str(raw_value: object, path: str) -> Optional[str]:
    """
    Parse nullable override text without treating an empty string as inheritance.
    """
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise DefinitionParseError(path, "expected a string or null")
    return raw_value


def require_list(value: Mapping[str, Any], key: str, path: str) -> Sequence[object]:
    """
    Require an array field.
    """
    raw_value = require_value(value, key, path)
    if not isinstance(raw_value, list):
        raise DefinitionParseError(path, "expected an array")
    return raw_value


def require_uuid(value: Mapping[str, Any], key: str, path: str) -> UUID:
    """
    Require and parse a UUID string field.
    """
    raw_value = require_value(value, key, path)
    return parse_uuid(raw_value, path)


def parse_uuid(raw_value: object, path: str) -> UUID:
    """
    Parse a UUID string.
    """
    if not isinstance(raw_value, str):
        raise DefinitionParseError(path, "expected a UUID string")
    try:
        return UUID(raw_value)
    except ValueError as error:
        raise DefinitionParseError(path, "invalid UUID") from error


def require_enum(
    enum_type: Type[EnumType],
    value: Mapping[str, Any],
    key: str,
    path: str,
) -> EnumType:
    """
    Require a string matching a supported enum value.
    """
    raw_value = require_str(value, key, path)
    try:
        return enum_type(raw_value)
    except ValueError as error:
        allowed_values = ", ".join(member.value for member in enum_type)
        raise DefinitionParseError(path, f"expected one of: {allowed_values}") from error


def parse_interpolation(raw_value: object, path: str) -> InterpolationSettings:
    """
    Parse optional automatic or explicit distances for persistence and UI requests.
    """
    value = require_mapping(raw_value, path)
    distances = []
    for field in ("approach_mm", "departure_mm"):
        raw = value.get(field)
        if raw is None:
            distances.append(None)
            continue
        number = require_float(value, field, f"{path}.{field}")
        try:
            InterpolationSettings(number)
        except ValueError as error:
            raise DefinitionParseError(f"{path}.{field}", str(error)) from error
        distances.append(number)
    return InterpolationSettings(*distances)
