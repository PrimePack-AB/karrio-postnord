"""Karrio PostNord Brev client settings."""

import typing

import attr
import jstruct
import karrio.core.models as models
import karrio.providers.postnord_brev.units as provider_units
import karrio.providers.postnord_brev.utils as provider_utils
import karrio.universal.mappers.rating_proxy as rating_proxy


@attr.s(auto_attribs=True)
class Settings(provider_utils.Settings, rating_proxy.RatingMixinSettings):
    """PostNord Brev (port payé) connection settings."""

    # Karrio's connection-field extractor ships the raw annotation, and the
    # dashboard renders no input for "typing.Optional[str]", so mapper
    # settings use the karrio-wide bare `str = None` shape.
    customer_number: str = None  # type: ignore
    franking_asset: str = None  # type: ignore

    # generic properties
    # id must stay declared: DP.to_object drops undeclared settings keys.
    id: str = None  # type: ignore
    test_mode: bool = False
    carrier_id: str = "postnord_brev"
    account_country_code: str = "SE"
    metadata: dict = {}
    config: dict = {}

    services: typing.List[models.ServiceLevel] = jstruct.JList[
        models.ServiceLevel, False, dict(default=provider_units.DEFAULT_SERVICES)
    ]  # type: ignore

    @property
    def shipping_services(self) -> typing.List[models.ServiceLevel]:
        services = (
            self.services
            if any(self.services or [])
            else provider_units.DEFAULT_SERVICES
        )
        return services
