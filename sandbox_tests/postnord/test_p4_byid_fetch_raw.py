"""Sandbox segment ``p4_byid_fetch_raw``: the only-customs by-id print, raw.

Reads the latest ``p1_cn23_gateway`` capture from the state directory —
never re-booking — and, when it allocated a printId, posts
``/rest/shipment/v3/labels/ids/pdf?definePrintout=onlyCustomsDeclarations``
with that single id, raw, one shot. The expected possible outcome is a
per-id FAIL ("id not found", "Unable to find EDI"); that negative is itself
the evidence, because it says whether test mode composed a separately
printable customs declaration for the CN23 booking at all. Skips, without
burning the marker, while no p1 capture or no printId exists.
"""

import unittest

from . import harness

SEGMENT = "p4_byid_fetch_raw"
FETCH_PATH = "/rest/shipment/v3/labels/ids/pdf"


class TestSandboxP4ByIdFetchRaw(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment(SEGMENT)

    def test_fetch_only_customs_declarations_by_print_id(self):
        self.maxDiff = None
        latest = harness.latest_segment_capture(
            self.session.config.sandbox_dir, "p1_cn23_gateway"
        )
        if latest is None:
            self.skipTest(
                "no p1_cn23_gateway capture exists yet; run that segment first"
            )
        print_id = harness.find_print_id(latest.parsed)
        if not print_id:
            self.skipTest(
                f"the latest p1_cn23_gateway capture ({latest.path}) allocated no printId"
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
                "raw by-id print fetch keyed by p1's printId; query carries only "
                "apikey (stripped) and definePrintout=onlyCustomsDeclarations"
            ),
        )
        parsed = self.session.write_response(
            stem, text, transport="response", http_status=status
        )
        self.session.write_result(
            SEGMENT,
            dict(
                print_id=print_id,
                source_capture=str(latest.path),
                http_status=status,
                member_statuses=[
                    dict(
                        status=member.get("status"),
                        error=(member.get("errorResponse") or {}).get("message"),
                    )
                    for entry in (parsed or [])
                    if isinstance(entry, dict)
                    for member in (entry.get("itemIds") or [])
                ]
                if isinstance(parsed, list)
                else None,
                printout_compositions=[
                    entry.get("printoutComposition")
                    for entry in (parsed or [])
                    if isinstance(entry, dict)
                ]
                if isinstance(parsed, list)
                else None,
            ),
        )
