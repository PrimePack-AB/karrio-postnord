"""PostNord Brev carrier registration and static rating tests."""

import unittest
from unittest.mock import patch

import karrio.sdk as karrio
import karrio.core.models as models

from .fixture import gateway


RatePayload = {
    "shipper": {
        "company_name": "A corp.",
        "address_line1": "125 Church St",
        "postal_code": "11455",
        "city": "Stockholm",
        "country_code": "SE",
    },
    "recipient": {
        "company_name": "B corp.",
        "person_name": "Jane Doe",
        "address_line1": "5840 Oak St",
        "postal_code": "41121",
        "city": "Göteborg",
        "country_code": "SE",
    },
    "parcels": [{"weight": 1.0, "weight_unit": "KG"}],
    "services": ["postnord_brev_first_class"],
}


class TestPostNordBrevRegistration(unittest.TestCase):
    def test_carrier_registers(self):
        self.assertIn("postnord_brev", karrio.gateway.providers)
        metadata = karrio.gateway.providers["postnord_brev"]
        self.assertEqual(metadata.label, "PostNord Brev (Port Payé)")

    def test_se_lane_offers_the_single_service_without_http(self):
        with patch("karrio.mappers.postnord_brev.proxy.lib.request") as mock:
            rates, messages = (
                karrio.Rating.fetch(models.RateRequest(**RatePayload))
                .from_(gateway)
                .parse()
            )
            mock.assert_not_called()
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates[0].service, "postnord_brev_first_class")

    def test_non_se_lane_offers_nothing(self):
        payload = {**RatePayload, "recipient": {**RatePayload["recipient"], "country_code": "NO"}}
        rates, _ = karrio.Rating.fetch(models.RateRequest(**payload)).from_(gateway).parse()
        self.assertEqual(rates, [])
