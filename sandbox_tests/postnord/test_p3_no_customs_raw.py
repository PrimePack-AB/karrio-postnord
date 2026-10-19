"""Sandbox segment ``p3_no_customs_raw``: booking without customs, past the connector.

Posts a minimal ``ediInstruction`` — parties and goods item only, no
customs object — straight to ``/rest/shipment/v3/edi/labels/pdf``, one
sub-case per basicServiceCode 18 and 91. Going raw bypasses our mapper on
purpose, so the connector's customs fail-fast guards cannot interfere with
the question: does PostNord itself accept a customs-less booking for these
services, and if so what ``printoutComposition`` comes back. Each sub-case
books at most once and draws on the booking budget; a rejection is recorded
and ends that sub-case.
"""

import typing
import unittest

from . import harness, payloads

SEGMENT = "p3_no_customs_raw"
BOOKING_PATH = "/rest/shipment/v3/edi/labels/pdf"


class TestSandboxP3NoCustomsRaw(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment(SEGMENT)

    def test_no_customs_basic_service_18(self):
        self._probe("18")

    def test_no_customs_basic_service_91(self):
        self._probe("91")

    def _probe(self, basic_service_code: str):
        self.maxDiff = None
        marker = f"{SEGMENT}-{basic_service_code}"
        harness.require_booking(self, self.session)
        harness.require_fire(self, self.session, marker)

        body = payloads.raw_booking_body(
            basic_service_code, typing.cast(str, self.session.config.customer_number)
        )
        status, text = self.session.raw_post(BOOKING_PATH, body)

        stem = self.session.next_stem(marker)
        self.session.write_request(
            stem,
            harness.SANDBOX_ORIGIN + BOOKING_PATH,
            body,
            note="minimal ediInstruction, no customs object, testIndicator true asserted before send",
        )
        parsed = self.session.write_response(
            stem, text, transport="response", http_status=status
        )
        compositions = (
            [
                entry.get("printoutComposition")
                for entry in (parsed.get("labelPrintout") or [])
            ]
            if isinstance(parsed, dict)
            else None
        )
        self.session.write_result(
            marker,
            dict(
                basic_service_code=basic_service_code,
                http_status=status,
                fault_codes=[
                    fault.get("faultCode")
                    for fault in ((parsed.get("compositeFault") or {}).get("faults"))
                    or []
                ]
                if isinstance(parsed, dict)
                else None,
                printout_compositions=compositions,
            ),
        )
        self.session.log_booking(marker, self.id())
