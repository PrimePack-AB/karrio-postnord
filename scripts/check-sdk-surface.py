"""Exit non-zero unless the installed karrio SDK provides the fork surface this connector needs.

Three capabilities are checked: document stamping (by name), the cn23
declaration kind the label_cn23 seeds stamp under (by value), and typed
enum-list connection configs (by behaviour).
"""

import sys
import typing

import attr
import karrio.lib as lib
import karrio.references as references
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

missing += [
    failure
    for failure, failed in [
        (
            "karrio.lib.DECLARATION_KINDS including 'cn23'",
            "cn23" not in getattr(lib, "DECLARATION_KINDS", ()),
        ),
        (
            "karrio.lib.COMBINED_DOC_TYPES mapping 'cn23' to 'label_cn23'",
            getattr(lib, "COMBINED_DOC_TYPES", {}).get("cn23") != "label_cn23",
        ),
    ]
    if failed
]


class _Channel(lib.StrEnum):
    sms = "A3"
    email = "A4"


class _Config(lib.Enum):
    channels = lib.OptionEnum("channels", typing.List[_Channel])


def _typed_list_config_failures() -> typing.List[str]:
    if not hasattr(references, "extract_list_item_enum"):
        return ["karrio.references.extract_list_item_enum"]

    config_type = _Config.channels.value.type
    published = (references.parse_type(config_type), references.extract_enum_names(config_type))
    coerced = lib.to_connection_config({"channels": "sms"}, option_type=_Config)["channels"].state
    return [
        failure
        for failure, failed in [
            (
                f"a typed list config publishes ('list', ['sms', 'email']), got {published}",
                published != ("list", ["sms", "email"]),
            ),
            (
                f"a typed list config coerces 'sms' to ['sms'], got {coerced!r}",
                coerced != ["sms"],
            ),
        ]
        if failed
    ]


missing += _typed_list_config_failures()
if missing:
    sys.exit(
        "The installed Joaqim/karrio SDK lacks the fork surface "
        "this connector needs: " + "; ".join(missing)
    )
