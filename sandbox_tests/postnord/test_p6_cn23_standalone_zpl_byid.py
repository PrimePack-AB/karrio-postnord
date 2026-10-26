"""Sandbox segment ``p6_cn23_standalone_zpl_byid``: the p6 standalone CN23 as ZPL, raw.

Reads the latest ``p6_cn23_standalone_gateway`` run — never re-booking —
and posts
``/rest/shipment/v3/labels/ids/zpl?definePrintout=onlyCustomsDeclarations``
with the booking's printId, raw, one shot. The by-id endpoints take the
format in the path (Booking APIs 3.5.29.1: ``/v3/labels/ids/zpl`` returns
"custom documents in ZPL"), so the ZPL rendering of the same CN23 needs no
second booking. Skips, without burning the marker, while no p6 run exists,
its booking allocated no printId, or its PDF by-id fetch was not a usable
printout: a rejected step stops the round rather than inviting a variation.
"""

import unittest

from . import harness

SEGMENT = "p6_cn23_standalone_zpl_byid"
SOURCE_SEGMENT = "p6_cn23_standalone_gateway"
FETCH_PATH = "/rest/shipment/v3/labels/ids/zpl"


class TestSandboxP6CN23StandaloneZplById(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment(SEGMENT)

    def test_fetch_standalone_cn23_as_zpl_by_print_id(self):
        self.maxDiff = None
        captures = harness.latest_run_captures(
            self.session.config.sandbox_dir, SOURCE_SEGMENT
        )
        if len(captures) < 2:
            self.skipTest(
                f"no {SOURCE_SEGMENT} run with a booking and a by-id capture exists"
            )
        booking, standalone = captures[0], captures[1]
        print_id = harness.find_print_id(booking.parsed)
        if not print_id:
            self.skipTest(f"the {SOURCE_SEGMENT} booking ({booking.path}) allocated no printId")
        failure = harness.byid_failure((standalone.parsed or {}).get("body"))
        if failure:
            self.skipTest(
                f"the {SOURCE_SEGMENT} PDF by-id fetch ({standalone.path}) was not "
                f"usable ({failure}); the round stops there"
            )

        harness.require_fire(self, self.session, SEGMENT)
        body = [{"id": print_id}]
        status, text = self.session.raw_post(
            FETCH_PATH, body, params={"definePrintout": "onlyCustomsDeclarations"}
        )

        stem = self.session.next_stem(SEGMENT)
        self.session.write_request(
            stem,
            harness.SANDBOX_ORIGIN + FETCH_PATH,
            body,
            note=(
                "raw by-id ZPL print fetch keyed by p6's printId; query carries "
                "only apikey (stripped) and definePrintout=onlyCustomsDeclarations"
            ),
        )
        parsed = self.session.write_response(
            stem, text, transport="response", http_status=status
        )
        self.session.write_result(
            SEGMENT,
            dict(
                print_id=print_id,
                source_capture=str(booking.path),
                http_status=status,
                failure=harness.byid_failure(parsed),
                printout_compositions=[
                    entry.get("printoutComposition")
                    for entry in (parsed or [])
                    if isinstance(entry, dict)
                ]
                if isinstance(parsed, list)
                else None,
            ),
        )
