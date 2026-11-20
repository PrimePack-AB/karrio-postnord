import typing

import karrio.core.models as models
import karrio.lib as lib


class ShippingService(lib.StrEnum):
    """Brev services. The member value is the karrio service code; there is no
    PostNord basicServiceCode because the carrier never calls a PostNord API."""

    postnord_brev_first_class = "postnord_brev_first_class"


class ShippingOption(lib.Enum):
    pass


class ConnectionConfig(lib.Enum):
    postnord_brev_label_tagline = lib.OptionEnum("postnord_brev_label_tagline")
    postnord_brev_stamp_pattern = lib.OptionEnum("postnord_brev_stamp_pattern")


def _resolved_option(payload, settings, code: str) -> typing.Optional[str]:
    """The shipment option value when it is a string, else the connection
    config value; anything else fails safe to ``None``."""
    option = (payload.options or {}).get(code)
    if isinstance(option, str):
        return option
    config = getattr(settings.connection_config, code)
    state = getattr(config, "state", None)
    return state if isinstance(state, str) else None


def resolve_label_tagline(payload, settings) -> typing.Optional[str]:
    """Vertical right-margin tagline; unset on both layers means no line."""
    return _resolved_option(payload, settings, "postnord_brev_label_tagline")


def resolve_stamp_pattern(payload, settings) -> typing.Optional[str]:
    """Engine-line pattern (jinja2 syntax); unset means the default."""
    return _resolved_option(payload, settings, "postnord_brev_stamp_pattern")


# One letter product in v1: domestic First Class under port payé. The SE-only
# zone is the first layer of the domestic gate: non-SE lanes resolve no rate.
# Prices arrive per-merchant through Karrio's server-side RateSheet, exactly
# as for the postnord carrier; 0.0 is the seed placeholder.
DEFAULT_SERVICES: typing.List[models.ServiceLevel] = [
    models.ServiceLevel(
        service_name="PostNord Brev First Class (Port Payé)",
        service_code="postnord_brev_first_class",
        currency="SEK",
        transit_days=2,
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    )
]
