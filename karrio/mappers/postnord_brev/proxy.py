"""Karrio PostNord Brev client proxy."""

import karrio.api.proxy as proxy
import karrio.lib as lib
from karrio.universal.mappers.rating_proxy import RatingMixinProxy

import karrio.providers.postnord_brev.shipment.create as provider_shipment


class Proxy(proxy.Proxy):
    def get_rates(self, request: lib.Serializable) -> lib.Deserializable:
        """Static rating only: the brev carrier has no PostNord API to call."""
        # RatingMixinProxy computes the static rates; its self annotation names
        # RatingMixinSettings, which Proxy satisfies structurally at runtime.
        return RatingMixinProxy.get_rates(self, request)  # type: ignore

    def create_shipment(self, request: lib.Serializable) -> lib.Deserializable:
        """Local label generation: no PostNord API is contacted."""
        return provider_shipment.create_shipment(request, self.settings)
