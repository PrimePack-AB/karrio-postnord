"""Exit non-zero unless the installed karrio SDK provides the document-stamping surface this connector needs."""

import sys

import attr
import karrio.lib as lib
from karrio.core.metadata import PluginMetadata

fields = attr.fields_dict(PluginMetadata)
missing = [
    f"PluginMetadata.{name}"
    for name in ("stamp_seeds", "document_sections")
    if name not in fields
] + [
    f"karrio.lib.{name}"
    for name in (
        "StampSeed",
        "StampPlacement",
        "AnyOf",
        "CustomsComposition",
        "classify_customs_composition",
    )
    if not hasattr(lib, name)
]
if missing:
    sys.exit(
        "The installed Joaqim/karrio SDK lacks the document-stamping surface "
        "this connector needs: " + ", ".join(missing)
    )
