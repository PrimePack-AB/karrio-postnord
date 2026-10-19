"""Sandbox segment ``p2_invoice_gateway``: customs-invoice parcel through the connector.

Same Stockholm-to-Tirana lane and parcel as ``p1_cn23_gateway``, booked as
postnord_parcel (18) with a commercial customs invoice (the SE-to-NO
invoice test payload retargeted to Albania): seller VAT, invoice number and
date, and two invoice lines select the ``customsInvoice`` branch. For
customs-invoice bookings the connector always follows the booking with the
by-id customs document fetch, so this segment's capture holds both calls:
the booking's own answer and the composed customs printout the fetch
returns.
"""

import base64
import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from . import harness, payloads

SEGMENT = "p2_invoice_gateway"


class TestSandboxP2InvoiceGateway(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment(SEGMENT)

    def test_book_18_to_albania_with_commercial_invoice(self):
        self.maxDiff = None
        harness.require_booking(self, self.session)
        harness.require_fire(self, self.session, SEGMENT)
        gateway = self.session.gateway()

        shipment, messages = (
            karrio.Shipment.create(
                models.ShipmentRequest(
                    **payloads.invoice_payload(
                        typing.cast(str, self.session.config.eori),
                        reference="P2-INVOICE-GATEWAY",
                    )
                )
            )
            .from_(gateway)
            .parse()
        )

        bodies = self.session.capture_gateway_calls(gateway, SEGMENT)
        self.session.write_result(
            SEGMENT,
            dict(
                karrio=dict(
                    tracking_number=shipment.tracking_number if shipment else None,
                    booking_id=(shipment.meta or {}).get("booking_id")
                    if shipment
                    else None,
                    printout_composition=(shipment.meta or {}).get(
                        "printout_composition"
                    )
                    if shipment
                    else None,
                    label_type=shipment.label_type if shipment else None,
                    label_bytes=(
                        len(base64.b64decode(shipment.docs.label))
                        if shipment and shipment.docs.label
                        else 0
                    ),
                    extra_documents=[
                        dict(category=document.category, format=document.format)
                        for document in (
                            shipment.docs.extra_documents if shipment else []
                        )
                        or []
                    ],
                    messages=lib.to_dict(messages),
                ),
                calls_captured=len(bodies),
            ),
        )
        self.session.log_booking(
            SEGMENT,
            self.id(),
            tracking_number=shipment.tracking_number if shipment else None,
            booking_id=(shipment.meta or {}).get("booking_id") if shipment else None,
            print_id=harness.find_print_id(bodies[0]) if bodies else None,
        )
        self.assertTrue(bodies, "no carrier call was captured")
