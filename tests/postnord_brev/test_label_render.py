"""PostNord Brev label template rendering tests."""

import unittest

import karrio.core.models as models

from karrio.providers.postnord_brev.label import render_label
from .fixture import SyntheticFrankingAsset


ShipmentPayload = {
    "service": "postnord_brev_first_class",
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
        "address_line2": "Lgh 1002",
        "postal_code": "41121",
        "city": "Göteborg",
        "country_code": "SE",
    },
    "parcels": [{"weight": 1.0, "weight_unit": "KG", "reference_number": "BREV-001"}],
}


class TestBrevLabelRender(unittest.TestCase):
    def setUp(self):
        self.shipment = models.ShipmentRequest(**ShipmentPayload)
        self.href = "data:image/svg+xml;base64," + SyntheticFrankingAsset

    def render(self):
        return render_label(
            self.shipment, "20000000", 1000, self.href, ship_date="2026-11-10"
        )

    def test_renders_swedish_fixed_svg_canvas(self):
        svg = self.render()
        self.assertIn('viewBox="0 0 100 180"', svg)
        self.assertIn("@page { size: 100mm 180mm; margin: 0; }", svg)
        for label_text in ("Avsändare", "Kundnummer", "Vikt", "Datum"):
            self.assertIn(label_text, svg)

    def test_renders_customer_number_parties_weight_and_asset(self):
        svg = self.render()
        self.assertIn("20000000", svg)
        self.assertIn("A corp.", svg)
        self.assertIn("125 Church St", svg)
        self.assertIn("11455 STOCKHOLM", svg)
        self.assertIn("B corp.", svg)
        self.assertIn("Jane Doe", svg)
        self.assertIn("5840 Oak St, Lgh 1002", svg)
        self.assertIn("41121 GÖTEBORG", svg)
        self.assertIn("1000 g", svg)
        self.assertIn("2026-11-10", svg)
        self.assertIn(self.href, svg)

    def test_same_country_recipient_omits_country_line(self):
        svg = self.render()
        # SE == SE, so the recipient block is exactly four lines: company,
        # person, street (with line2), and postcode+city — no country line.
        self.assertEqual(svg.count('<text x="11"'), 4)

    def test_escapes_markup_in_party_input(self):
        payload = {
            **ShipmentPayload,
            "recipient": {
                **ShipmentPayload["recipient"],
                "person_name": "Jane <b>Doe</b>",
            },
        }
        svg = render_label(
            models.ShipmentRequest(**payload), "20000000", 1000, self.href
        )
        self.assertIn("Jane &lt;b&gt;Doe&lt;/b&gt;", svg)

    def test_shipper_contact_line_renders_when_given(self):
        payload = {
            **ShipmentPayload,
            "shipper": {
                **ShipmentPayload["shipper"],
                "email": "avsandare@example.se",
                "phone_number": "+46 70 123 45 67",
            },
        }
        svg = render_label(
            models.ShipmentRequest(**payload),
            "20000000",
            1000,
            self.href,
            shipper_contact="avsandare@example.se · +46701234567",
        )
        self.assertIn("avsandare@example.se · +46701234567", svg)
