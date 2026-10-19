"""Sandbox segment ``p1_cn23_gateway``: International Parcel CN23 through the connector.

Drives our own connector end to end: a 91 (postnord_postpaket_utrikes)
booking from Stockholm to a generic Tirana address with the CN23 customs
block (EORI from the environment), one 1.0 kg 20x10x30 cm parcel. The
mapper builds ``customsDeclarationCN23`` with zero ``postalCharges``; the
capture records PostNord's whole answer — bookingResponse statuses,
``printoutComposition``, and the composed document bytes — which is the
first real evidence for both the CN23 acceptance and what test mode
composes for it. The standalone customs documents opt-in stays off: the
by-id fetch this connector would make for it is probed separately, raw, by
segment ``p4_byid_fetch_raw``.
"""

import base64
import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from . import harness, payloads

SEGMENT = "p1_cn23_gateway"


class TestSandboxP1CN23Gateway(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment(SEGMENT)

    def test_book_91_to_albania_with_cn23(self):
        self.maxDiff = None
        harness.require_booking(self, self.session)
        harness.require_fire(self, self.session, SEGMENT)
        gateway = self.session.gateway()

        shipment, messages = (
            karrio.Shipment.create(
                models.ShipmentRequest(
                    **payloads.cn23_payload(
                        typing.cast(str, self.session.config.eori),
                        reference="P1-CN23-GATEWAY",
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
