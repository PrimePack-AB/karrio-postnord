from typing import List, Tuple

from karrio.api.mapper import Mapper as BaseMapper
from karrio.core.models import RateDetails, RateRequest, Message
from karrio.core.utils.serializable import Deserializable, Serializable
from karrio.universal.providers.rating import parse_rate_response, rate_request


class Mapper(BaseMapper):
    def create_rate_request(self, payload: RateRequest) -> Serializable:
        return rate_request(payload, self.settings)

    def parse_rate_response(
        self, response: Deserializable
    ) -> Tuple[List[RateDetails], List[Message]]:
        return parse_rate_response(response, self.settings)
