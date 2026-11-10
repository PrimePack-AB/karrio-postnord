"""PostNord Brev local shipment flow and guard tests."""

import base64
import unittest
from collections import namedtuple
from unittest.mock import patch

import karrio.sdk as karrio
import karrio.core.models as models

from .fixture import (
    SyntheticFrankingAsset,
    _settings,
    gateway,
    gateway_with_phone_policy,
    gateway_without,
)
from .test_label_render import ShipmentPayload

# This SDK build's parse() returns a bare (details, messages) tuple; the shim
# keeps the response.shipment / response.messages accessors.
ShipmentResponse = namedtuple("ShipmentResponse", ["shipment", "messages"])


def _create(payload, gw=gateway):
    details, messages = (
        karrio.Shipment.create(models.ShipmentRequest(**payload)).from_(gw).parse()
    )
    return ShipmentResponse(details, messages)


def _errors(response):
    return {
        key
        for message in response.messages
        for key in (message.details or {}).keys()
    }


class TestBrevCreateShipment(unittest.TestCase):
    def test_generates_svg_label_without_http(self):
        with patch("karrio.mappers.postnord_brev.proxy.lib.request") as mock:
            response = _create(dict(ShipmentPayload))
            mock.assert_not_called()
        details = response.shipment
        self.assertEqual(details.label_type, "SVG")
        self.assertEqual(details.carrier_id, "postnord_brev")
        self.assertEqual(details.meta["service_name"], "PostNord Brev First Class (Port Payé)")
        svg = base64.b64decode(details.docs.label).decode()
        self.assertIn('viewBox="0 0 100 180"', svg)
        self.assertIn("20000000", svg)
        self.assertIn("data:image/svg+xml;base64,", svg)
        self.assertIn("1000 g", svg)

    def test_mints_identifier_from_reference_number(self):
        response = _create(dict(ShipmentPayload))
        self.assertEqual(response.shipment.tracking_number, "BREV-001")
        self.assertEqual(response.shipment.shipment_identifier, "BREV-001")

    def test_mints_numeric_identifier_without_reference(self):
        payload = {
            **ShipmentPayload,
            "parcels": [dict(weight=1.0, weight_unit="KG")],
        }
        response = _create(payload)
        self.assertRegex(response.shipment.tracking_number, r"^\d{1,10}$")

    def test_customer_number_metadata_overrides_connection(self):
        payload = {**ShipmentPayload, "metadata": {"postnord_port_paye_customer_number": "12345678"}}
        response = _create(payload)
        svg = base64.b64decode(response.shipment.docs.label).decode()
        self.assertIn("12345678", svg)


class TestBrevGuards(unittest.TestCase):
    def test_missing_customer_number_fails(self):
        response = _create(dict(ShipmentPayload), gateway_without(customer_number=None))
        self.assertIsNone(response.shipment)
        self.assertIn("customer_number", _errors(response))

    def test_non_se_recipient_fails(self):
        payload = {
            **ShipmentPayload,
            "recipient": {**ShipmentPayload["recipient"], "country_code": "NO"},
        }
        response = _create(payload)
        self.assertIn("recipient.country_code", _errors(response))

    def test_non_se_shipper_fails(self):
        payload = {
            **ShipmentPayload,
            "shipper": {**ShipmentPayload["shipper"], "country_code": "DK"},
        }
        # The SDK's origin gate aborts a non-SE shipper before the provider
        # guard runs when account_country_code is set, so reach the guard by
        # clearing it for this gateway.
        gw = karrio.gateway["postnord_brev"].create(
            dict(_settings, account_country_code=None)
        )
        response = _create(payload, gw)
        self.assertIn("shipper.country_code", _errors(response))

    def test_multiple_parcels_fail(self):
        payload = {
            **ShipmentPayload,
            "parcels": [dict(weight=0.5, weight_unit="KG"), dict(weight=0.5, weight_unit="KG")],
        }
        response = _create(payload)
        self.assertIn("parcels", _errors(response))

    def test_missing_weight_fails(self):
        payload = {**ShipmentPayload, "parcels": [dict(weight_unit="KG")]}
        response = _create(payload)
        self.assertIn("parcels.weight", _errors(response))

    def test_overweight_fails(self):
        payload = {**ShipmentPayload, "parcels": [dict(weight=2.5, weight_unit="KG")]}
        response = _create(payload)
        self.assertIn("parcels.weight", _errors(response))

    def test_oversize_dimensions_fail(self):
        # Dimensions are top-level parcel fields: jstruct drops an unknown
        # `dimension` key when constructing models.Parcel.
        payload = {
            **ShipmentPayload,
            "parcels": [
                dict(
                    weight=0.5,
                    weight_unit="KG",
                    length=50,
                    width=40,
                    height=30,
                    dimension_unit="CM",
                )
            ],
        }
        response = _create(payload)
        self.assertIn("parcels.dimension", _errors(response))

    def test_customs_declaration_fails(self):
        # Customs.commodities is required by the SDK model, so the minimal
        # declaration carries one commodity line.
        payload = {
            **ShipmentPayload,
            "customs": dict(
                content_description="letter goods",
                commodities=[dict(description="letter goods", quantity=1)],
            ),
        }
        response = _create(payload)
        self.assertIn("customs", _errors(response))

    def test_missing_franking_asset_fails(self):
        response = _create(dict(ShipmentPayload), gateway_without(franking_asset=None))
        self.assertIn("franking_asset", _errors(response))

    def test_unsniffable_franking_asset_fails(self):
        bad = base64.b64encode(b"not an image").decode()
        gw = karrio.gateway["postnord_brev"].create(dict(_settings, franking_asset=bad))
        response = _create(dict(ShipmentPayload), gw)
        self.assertIn("franking_asset", _errors(response))

    def test_png_franking_asset_renders_png_uri(self):
        png = base64.b64encode(b"\x89PNG\r\n\x1a\nfakepng").decode()
        gw = karrio.gateway["postnord_brev"].create(dict(_settings, franking_asset=png))
        response = _create(dict(ShipmentPayload), gw)
        svg = base64.b64decode(response.shipment.docs.label).decode()
        self.assertIn("data:image/png;base64,", svg)

    def test_data_uri_franking_asset_passes_through(self):
        gw = karrio.gateway["postnord_brev"].create(
            dict(_settings, franking_asset="data:image/svg+xml;base64," + SyntheticFrankingAsset)
        )
        response = _create(dict(ShipmentPayload), gw)
        svg = base64.b64decode(response.shipment.docs.label).decode()
        self.assertIn("data:image/svg+xml;base64," + SyntheticFrankingAsset, svg)


class TestBrevShipperContact(unittest.TestCase):
    def _svg(self, payload, gw=gateway):
        response = _create(payload, gw)
        return base64.b64decode(response.shipment.docs.label).decode()

    def _contact_payload(self, **options):
        return {
            **ShipmentPayload,
            "shipper": {
                **ShipmentPayload["shipper"],
                "email": "avsandare@example.se",
                "phone_number": "+46 70 123 45 67",
            },
            "options": options,
        }

    def test_email_suffices_omits_phone(self):
        svg = self._svg(
            self._contact_payload(postnord_phone_number_policy="omit_when_email_suffices")
        )
        self.assertIn("avsandare@example.se", svg)
        self.assertNotIn("46701234567", svg)

    def test_always_policy_prints_phone_beside_email(self):
        svg = self._svg(self._contact_payload(postnord_phone_number_policy="always"))
        self.assertIn("avsandare@example.se · +46701234567", svg)

    def test_request_option_overrides_connection_config(self):
        payload = self._contact_payload(postnord_phone_number_policy="always")
        svg = self._svg(
            payload, gateway_with_phone_policy("omit_when_email_suffices")
        )
        self.assertIn("46701234567", svg)
