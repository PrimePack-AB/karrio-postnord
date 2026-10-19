"""Sandbox segment ``p5_no_customs_with_application_raw``: customs-less 91 with an application id.

The p3-91 probe — the same minimal ``ediInstruction`` with no customs
object — was rejected with SACUS-BR-24100901 "ApplicationId is invalid,
should be 4 digit integer", while the p1 mapper booking (which carried an
``application`` object with only a name) passed. This segment resends the
p3-91 body unchanged plus a top-level ``application`` object carrying the
configured 4-digit id, raw, one shot: acceptance with a composed printout
would be a major finding, as would a customs-data fault naming what the
customs-less booking is missing. The id is non-secret per the repo
carve-out and is captured in the request artifact.
"""

import os
import typing
import unittest

from . import harness, payloads

SEGMENT = "p5_no_customs_with_application_raw"
BOOKING_PATH = "/rest/shipment/v3/edi/labels/pdf"


def require_application(test: unittest.TestCase, environ: typing.Mapping[str, str]) -> dict:
    """Skip unless an application id is configured; refuse a malformed one."""
    application = payloads.application_object(environ)
    if application is None:
        test.skipTest(
            "neither POSTNORD_LIVE_APPLICATION_ID nor POSTNORD_APPLICATION_ID is set"
        )
    return application


class TestSandboxP5NoCustomsWithApplicationRaw(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment(SEGMENT)

    def test_no_customs_91_with_application_id(self):
        self.maxDiff = None
        application = require_application(self, os.environ)
        harness.require_booking(self, self.session)
        harness.require_fire(self, self.session, SEGMENT)

        body = payloads.raw_booking_body(
            "91",
            typing.cast(str, self.session.config.customer_number),
            application=application,
        )
        status, text = self.session.raw_post(BOOKING_PATH, body)

        stem = self.session.next_stem(SEGMENT)
        self.session.write_request(
            stem,
            harness.SANDBOX_ORIGIN + BOOKING_PATH,
            body,
            note=(
                "p3-91 body unchanged plus a top-level application object; "
                "no customs object, testIndicator true asserted before send"
            ),
        )
        parsed = self.session.write_response(
            stem, text, transport="response", http_status=status
        )
        faults = (
            (parsed.get("compositeFault") or {}).get("faults")
            if isinstance(parsed, dict)
            else None
        )
        self.session.write_result(
            SEGMENT,
            dict(
                basic_service_code="91",
                application=application,
                http_status=status,
                fault_codes=[fault.get("faultCode") for fault in faults or []],
                faults=faults,
                printout_compositions=[
                    entry.get("printoutComposition")
                    for entry in (parsed.get("labelPrintout") or [])
                ]
                if isinstance(parsed, dict)
                else None,
            ),
        )
        self.session.log_booking(SEGMENT, self.id())
