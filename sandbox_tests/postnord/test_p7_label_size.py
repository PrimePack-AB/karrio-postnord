"""Sandbox segments ``p7_label_size_*``: the p1 CN23 booking at non-default label sizes.

Each segment books the p1 shape — a 91 (postnord_postpaket_utrikes)
booking from Stockholm to a generic Tirana address with the mapper-built
CN23, one 1.0 kg parcel — through the connector, on a connection whose
``label_size`` is set, in one file format. The connector sends the size
as the ``labelType`` query parameter on the format's booking endpoint
(``/rest/shipment/v3/edi/labels/pdf`` or ``/zpl``). Booking APIs
3.5.29.1 lists standard, small, and ste for PDF and standard and small
for ZPL, and says small is not available for every label, with standard
defaulted. The stamping seeds were measured on standard-size output, so
the captures answer what PostNord composes at each size and whether the
seeds still fit.

The four bookings fire in ``CASES`` order, each its own one-shot segment,
so a rejection in one leaves the others free to fire; none retries.
``ste`` on ZPL is outside the documented values and fires once as
specified, a rejection being a valid finding. The standalone customs
documents opt-in stays off, so each booking is the only call made.
"""

import base64
import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from . import harness, payloads

SEGMENT_PREFIX = "p7_label_size"

# (label_size, file format) in firing order; the method names sort the same.
CASES: typing.Tuple[typing.Tuple[str, str], ...] = (
    ("small", "ZPL"),
    ("small", "PDF"),
    ("ste", "PDF"),
    ("ste", "ZPL"),
)


def segment_name(label_size: str, label_format: str) -> str:
    return f"{SEGMENT_PREFIX}_{label_size}_{label_format.lower()}"


def reference(label_size: str, label_format: str) -> str:
    return f"P7-{label_size.upper()}-{label_format.upper()}"


class TestSandboxP7LabelSize(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment(SEGMENT_PREFIX)

    def _book(self, label_size: str, label_format: str) -> None:
        self.maxDiff = None
        segment = segment_name(label_size, label_format)
        harness.require_booking(self, self.session)
        harness.require_fire(self, self.session, segment)
        gateway = self.session.gateway(dict(label_size=label_size))

        shipment, messages = (
            karrio.Shipment.create(
                models.ShipmentRequest(
                    **payloads.cn23_payload(
                        typing.cast(str, self.session.config.eori),
                        reference=reference(label_size, label_format),
                        label_type=label_format,
                    )
                )
            )
            .from_(gateway)
            .parse()
        )

        bodies = self.session.capture_gateway_calls(gateway, segment)
        print_id = harness.find_print_id(bodies[0]) if bodies else None
        meta = (shipment.meta or {}) if shipment else {}
        self.session.write_result(
            segment,
            dict(
                label_size=label_size,
                label_format=label_format,
                karrio=dict(
                    tracking_number=shipment.tracking_number if shipment else None,
                    booking_id=meta.get("booking_id"),
                    printout_composition=meta.get("printout_composition"),
                    stamp_doc_type=meta.get("stamp_doc_type"),
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
                print_id=print_id,
            ),
        )
        self.session.log_booking(
            segment,
            self.id(),
            tracking_number=shipment.tracking_number if shipment else None,
            booking_id=meta.get("booking_id"),
            print_id=print_id,
        )
        self.assertEqual(len(bodies), 1, "expected exactly the booking call")

    def test_1_small_zpl(self):
        self._book("small", "ZPL")

    def test_2_small_pdf(self):
        self._book("small", "PDF")

    def test_3_ste_pdf(self):
        self._book("ste", "PDF")

    def test_4_ste_zpl(self):
        self._book("ste", "ZPL")
