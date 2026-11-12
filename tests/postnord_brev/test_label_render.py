"""PostNord Brev label template rendering tests."""

import unittest
import xml.etree.ElementTree as ET

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
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

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

    def test_shipper_contact_flows_below_sender_block(self):
        contact = "avsandare@example.se · +46701234567"
        # Three sender lines (no address_line2): the contact sits one sender
        # slot below the last line, at 12.1 + 3 * 2.75 = 20.35.
        svg = render_label(
            models.ShipmentRequest(**ShipmentPayload),
            "20000000",
            1000,
            self.href,
            shipper_contact=contact,
        )
        self.assertIn(
            '<text x="5" y="20.35" font-size="2.24">' + contact + "</text>", svg
        )
        # A fourth sender line (address_line2) moves the contact down one
        # more slot to 12.1 + 4 * 2.75 = 23.1 instead of overlapping the block.
        payload = {
            **ShipmentPayload,
            "shipper": {
                **ShipmentPayload["shipper"],
                "address_line2": "Attn: Brevlåda 4",
                "email": "avsandare@example.se",
                "phone_number": "+46 70 123 45 67",
            },
        }
        svg = render_label(
            models.ShipmentRequest(**payload),
            "20000000",
            1000,
            self.href,
            shipper_contact=contact,
        )
        self.assertIn(
            '<text x="5" y="23.1" font-size="2.24">' + contact + "</text>", svg
        )

    def test_engine_line_renders_when_given(self):
        svg = render_label(
            self.shipment,
            "20000000",
            1000,
            self.href,
            engine_line="A corp. – 202611121435",
        )
        self.assertIn(
            '<text x="94" y="27.3" font-size="2.06" font-weight="bold" '
            'text-anchor="end">A corp. – 202611121435</text>',
            svg,
        )

    def test_engine_line_and_tagline_omitted_when_unset(self):
        svg = self.render()
        self.assertNotIn('<text x="94" y="27.3"', svg)
        self.assertNotIn("rotate(90)", svg)

    def test_tagline_renders_centred_on_right_margin(self):
        svg = render_label(
            self.shipment,
            "20000000",
            1000,
            self.href,
            tagline="Skicka rätt",
        )
        self.assertIn(
            '<text transform="translate(95.6 45.8) rotate(90)" '
            'font-size="2.06" font-weight="bold" text-anchor="middle">'
            "Skicka rätt</text>",
            svg,
        )

    def test_tagline_and_engine_line_escape_markup(self):
        svg = render_label(
            self.shipment,
            "20000000",
            1000,
            self.href,
            engine_line="A & B",
            tagline="C <i>D</i>",
        )
        self.assertIn("A &amp; B", svg)
        self.assertIn("C &lt;i&gt;D&lt;/i&gt;", svg)
