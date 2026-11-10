from karrio.core.metadata import PluginMetadata

from karrio.mappers.postnord_brev.mapper import Mapper
from karrio.mappers.postnord_brev.proxy import Proxy
from karrio.mappers.postnord_brev.settings import Settings
import karrio.providers.postnord_brev.units as units


# Discovered and registered through the karrio.plugins entry point in
# pyproject.toml, beside the postnord plugin.
METADATA = PluginMetadata(
    id="postnord_brev",
    label="PostNord Brev (Port Payé)",
    description=(
        "PostNord domestic First Class letters under a port payé agreement: "
        "local SVG label generation, no PostNord API"
    ),
    # Integrations
    Mapper=Mapper,
    Proxy=Proxy,
    Settings=Settings,
    # Data Units
    is_hub=False,
    services=units.ShippingService,
    options=units.ShippingOption,
    service_levels=units.DEFAULT_SERVICES,
    website="https://www.postnord.se",
)
