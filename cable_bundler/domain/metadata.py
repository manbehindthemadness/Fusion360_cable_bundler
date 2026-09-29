"""
Validate and resolve ordered harness metadata.
"""

from __future__ import annotations

Metadata = tuple[tuple[str, str], ...]


def validate_metadata(entries: Metadata, label: str) -> None:
    """
    Require ordered, uniquely named text metadata fields.
    """
    if not isinstance(entries, tuple):
        raise ValueError(f"{label} must be an ordered tuple.")
    keys: set[str] = set()
    for entry in entries:
        if (
            not isinstance(entry, tuple)
            or len(entry) != 2
            or not all(isinstance(item, str) for item in entry)
        ):
            raise ValueError(f"{label} entries must contain a text key and value.")
        key, _value = entry
        normalized_key = key.strip().casefold()
        if not normalized_key:
            raise ValueError(f"{label} keys must not be empty.")
        if normalized_key in keys:
            raise ValueError(f"{label} keys must be unique ignoring case.")
        keys.add(normalized_key)


def resolve_metadata(inherited: Metadata, overrides: Metadata) -> Metadata:
    """
    Merge explicit values over inherited entries without changing key order.
    """
    override_by_key = {key.casefold(): (key, value) for key, value in overrides}
    resolved: list[tuple[str, str]] = []
    inherited_keys: set[str] = set()
    for key, value in inherited:
        normalized_key = key.casefold()
        inherited_keys.add(normalized_key)
        resolved.append(override_by_key.get(normalized_key, (key, value)))
    resolved.extend(entry for entry in overrides if entry[0].casefold() not in inherited_keys)
    return tuple(resolved)
