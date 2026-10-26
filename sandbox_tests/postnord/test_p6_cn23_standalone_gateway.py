"""Sandbox segment ``p6_cn23_standalone_gateway``: a standalone CN23 through the connector.

The p1 booking shape — a 91 (postnord_postpaket_utrikes) booking from
Stockholm to a generic Tirana address with the mapper-built CN23, one
1.0 kg parcel, PDF labels — with the connector's
``postnord_standalone_customs_documents`` opt-in set. On an accepted
booking the connector follows up with
``POST /rest/shipment/v3/labels/ids/pdf?definePrintout=onlyCustomsDeclarations``
keyed by the booking's printId and attaches what comes back under
``extra_documents``; both calls are captured. The by-id answer is the
evidence sought: a customs-only CN23 printout, or the per-id FAIL the
fork-era test-mode round recorded. Segment ``p6_cn23_standalone_zpl_byid``
reads this capture for the ZPL rendering of the same printId.
"""

import base64
import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from . import harness, payloads

SEGMENT = "p6_cn23_standalone_gateway"


class TestSandboxP6CN23StandaloneGateway(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment(SEGMENT)

    def test_book_91_to_albania_with_standalone_cn23(self):
        self.maxDiff = None
        harness.require_booking(self, self.session)
        harness.require_fire(self, self.session, SEGMENT)
        gateway = self.session.gateway()

        shipment, messages = (
            karrio.Shipment.create(
                models.ShipmentRequest(
                    **payloads.cn23_payload(
                        typing.cast(str, self.session.config.eori),
                        reference="P6-CN23-STANDALONE",
                        standalone_customs_documents=True,
                    )
                )
            )
            .from_(gateway)
            .parse()
        )

        bodies = self.session.capture_gateway_calls(gateway, SEGMENT)
        print_id = harness.find_print_id(bodies[0]) if bodies else None
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
                        dict(
                            category=document.category,
                            format=document.format,
                            bytes=len(base64.b64decode(document.base64 or "")),
                        )
                        for document in (
                            shipment.docs.extra_documents if shipment else []
                        )
                        or []
                    ],
                    messages=lib.to_dict(messages),
                ),
                calls_captured=len(bodies),
                print_id=print_id,
                standalone_failure=(
                    harness.byid_failure(bodies[1])
                    if len(bodies) > 1
                    else "no by-id call was made"
                ),
            ),
        )
        self.session.log_booking(
            SEGMENT,
            self.id(),
            tracking_number=shipment.tracking_number if shipment else None,
            booking_id=(shipment.meta or {}).get("booking_id") if shipment else None,
            print_id=print_id,
        )
        self.assertTrue(bodies, "no carrier call was captured")
