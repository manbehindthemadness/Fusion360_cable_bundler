"""
Read-only live diagnostics for the active document's Interface outline snapshots.

Run through the local Fusion MCP script executor with readOnly=true. It inspects
the active document and add-in cache state without changing either.
"""

import json


def run(_context: str) -> None:
    """
    Report cache eligibility, snapshot presence, and session revision counters.
    """
    import adsk.core  # type: ignore[import-not-found]

    from cable_bundler.application import load_harnesses
    from cable_bundler.fusion.interface_contact_disk_cache import (
        _read_snapshot,
        _snapshot_path,
        _validated_revisions,
        describe_interface_contact_cache,
        read_complete_cached_contacts,
    )
    from cable_bundler.fusion.ui.runtime import runtime
    from cable_bundler.fusion.ui.support import _create_harness_gateway

    application = adsk.core.Application.get()
    document = application.activeDocument
    data_file = document.dataFile if document is not None else None
    result: dict[str, object] = {
        "document": getattr(document, "name", None),
        "modified": getattr(document, "isModified", None),
        "savedVersion": getattr(data_file, "versionNumber", None),
        "uiRevision": runtime.contact_geometry_revision,
        "diskRevision": runtime.contact_cache_revision(application),
    }
    interfaces = []
    for item in load_harnesses(_create_harness_gateway(application)):
        if item.definition is None:
            continue
        for interface in item.definition.interfaces:
            status = describe_interface_contact_cache(
                application, item.definition.harness_id, interface.interface_id
            )
            path = _snapshot_path(application, item.definition.harness_id, interface.interface_id)
            entries = _read_snapshot(path)
            validation = _validated_revisions.get(path)
            warm = read_complete_cached_contacts(
                application,
                item.definition.harness_id,
                interface.interface_id,
                interface.contacts,
                runtime.contact_cache_revision(application),
            )
            matched = sum(
                isinstance(record, dict) and record.get("token") == contact.entity_token
                for contact in interface.contacts
                if (record := entries.get(str(contact.contact_id))) is not None
            )
            interfaces.append(
                {
                    "name": interface.name,
                    "contacts": len(interface.contacts),
                    "cache": status,
                    "tokenMatches": matched,
                    "storedSignatures": sum(
                        isinstance(record, dict) and isinstance(record.get("sourceSignature"), str)
                        for record in entries.values()
                    ),
                    "validationRevision": validation[0] if validation else None,
                    "validatedContacts": len(validation[1]) if validation else 0,
                    "warmReadContacts": len(warm) if warm is not None else None,
                }
            )
    result["interfaces"] = interfaces
    print(json.dumps(result, sort_keys=True))
