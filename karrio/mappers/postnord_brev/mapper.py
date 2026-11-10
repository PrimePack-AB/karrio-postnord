from typing import List, Tuple

from karrio.api.mapper import Mapper as BaseMapper
from karrio.core.models import (
    RateDetails,
    RateRequest,
    Message,
    ShipmentDetails,
    ShipmentRequest,
)
from karrio.core.utils.serializable import Deserializable, Serializable
from karrio.universal.providers.rating import parse_rate_response, rate_request

import karrio.providers.postnord_brev.shipment as provider_shipment


class Mapper(BaseMapper):
    def create_rate_request(self, payload: RateRequest) -> Serializable:
        return rate_request(payload, self.settings)

    def parse_rate_response(
        self, response: Deserializable
    ) -> Tuple[List[RateDetails], List[Message]]:
        return parse_rate_response(response, self.settings)

    def create_shipment_request(self, payload: ShipmentRequest) -> Serializable:
        return provider_shipment.shipment_request(payload, self.settings)

    def parse_shipment_response(
        self, response: Deserializable
    ) -> Tuple[ShipmentDetails, List[Message]]:
        return provider_shipment.parse_shipment_response(response, self.settings)
