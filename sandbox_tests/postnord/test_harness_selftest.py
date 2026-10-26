"""Offline self-tests for the sandbox harness: guards, redaction, one-shot, budget.

Every test here is pure and local: no network, no live credentials, no
gate. A synthetic apikey exercises the redactor; temporary directories
exercise the markers, the budget, the capture writer, and the p4 capture
finder, so the machinery the live segments rely on is verified before any
probe fires.
"""

import base64
import dataclasses
import datetime
import hashlib
import json
import pathlib
import tempfile
import typing
import unittest

from . import harness, payloads

NOW = datetime.datetime(2026, 10, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
SYNTHETIC_APIKEY = "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6"

GATED_ENVIRONMENT = {
    "POSTNORD_SANDBOX": "1",
    "POSTNORD_APIKEY": SYNTHETIC_APIKEY,
    "POSTNORD_CUSTOMER_NUMBER": "12345678",
    "POSTNORD_EORI": "SE556000123401",
}


def gated_config(**overrides) -> harness.SandboxConfig:
    return harness.load_config({**GATED_ENVIRONMENT, **overrides}, NOW)


def offline_session(state_home: pathlib.Path) -> harness.Session:
    """A capture-capable session with the gate off, rooted at ``state_home``.

    The disabled config also keeps the transport guard uninstalled, so the
    self-tests never touch the SDK's network plumbing.
    """
    config = gated_config(XDG_STATE_HOME=str(state_home))
    return harness.Session(dataclasses.replace(config, enabled=False))


def _skipped_case() -> unittest.TestCase:
    class _skipped(unittest.TestCase):
        def runTest(self):
            pass

    return _skipped()


class TestGate(unittest.TestCase):
    def test_gate_off_skips(self):
        config = harness.load_config({}, NOW)
        self.assertFalse(config.enabled)
        self.assertEqual(harness.skip_reason(config), "POSTNORD_SANDBOX is not 1")
        with self.assertRaises(unittest.SkipTest) as skipped:
            harness._require(config, "p1_cn23_gateway")
        self.assertIn("POSTNORD_SANDBOX is not 1", str(skipped.exception))

    def test_missing_credentials_skip(self):
        for missing in ("POSTNORD_APIKEY", "POSTNORD_CUSTOMER_NUMBER", "POSTNORD_EORI"):
            with self.subTest(variable=missing):
                environment = dict(GATED_ENVIRONMENT)
                environment.pop(missing)
                config = harness.load_config(environment, NOW)
                self.assertEqual(harness.skip_reason(config), f"{missing} is not set")

    def test_gated_config_runs(self):
        self.assertIsNone(harness.skip_reason(gated_config()))


class TestRefusals(unittest.TestCase):
    def test_live_key_present_refuses(self):
        with self.assertRaises(harness.SandboxConfigError) as refused:
            gated_config(POSTNORD_LIVE_APIKEY="anythingAtAll")
        self.assertIn("POSTNORD_LIVE_APIKEY", str(refused.exception))

    def test_empty_apikey_refuses(self):
        with self.assertRaises(harness.SandboxConfigError) as refused:
            gated_config(POSTNORD_APIKEY="")
        self.assertIn("POSTNORD_APIKEY is empty", str(refused.exception))

    def test_bad_booking_budget_refuses(self):
        for value in ("four", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(harness.SandboxConfigError):
                    gated_config(POSTNORD_SANDBOX_MAX_BOOKINGS=value)

    def test_default_booking_budget_is_four(self):
        self.assertEqual(gated_config().max_bookings, 4)

    def test_booking_budget_override(self):
        config = gated_config(POSTNORD_SANDBOX_MAX_BOOKINGS="2")
        self.assertEqual(config.max_bookings, 2)


class TestHostGuard(unittest.TestCase):
    def test_sandbox_origin_accepted(self):
        for url in (
            "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/pdf?apikey=x",
            "https://atapi2.postnord.com/rest/shipment/v3/labels/ids/pdf",
        ):
            with self.subTest(url=url):
                self.assertEqual(harness.check_url(url), url)

    def test_production_host_refused(self):
        with self.assertRaises(harness.SandboxConfigError):
            harness.check_url(
                "https://api2.postnord.com/rest/shipment/v3/edi/labels/pdf"
            )

    def test_non_postnord_and_lookalike_hosts_refused(self):
        for url in (
            "http://atapi2.postnord.com/rest/shipment/v3/edi/labels/pdf",
            "https://atapi2.postnord.com.evil.example/rest",
            "https://evil.example/rest/shipment/v3/edi/labels/pdf",
            "https://tracking.postnord.com/",
        ):
            with self.subTest(url=url):
                with self.assertRaises(harness.SandboxConfigError):
                    harness.check_url(url)

    def test_booking_body_requires_test_indicator_true(self):
        path = "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/pdf"
        harness.check_booking_body(path, json.dumps({"testIndicator": True}))
        for body in (
            json.dumps({"testIndicator": False}),
            json.dumps({"updateIndicator": "Original"}),
            "not json",
        ):
            with self.subTest(body=body):
                with self.assertRaises(harness.SandboxConfigError):
                    harness.check_booking_body(path, body)

    def test_non_booking_body_takes_no_test_indicator(self):
        harness.check_booking_body(
            "https://atapi2.postnord.com/rest/shipment/v3/labels/ids/pdf",
            json.dumps([{"id": "123"}]),
        )


class TestRedaction(unittest.TestCase):
    def test_strip_query_removes_apikey(self):
        self.assertEqual(
            harness.strip_query(
                "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/pdf"
                "?apikey=SECRET&labelType=small"
            ),
            "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/pdf",
        )

    def test_redact_masks_synthetic_key_and_query(self):
        artifact = dict(
            url=(
                "https://atapi2.postnord.com/rest/shipment/v3/labels/ids/pdf"
                f"?apikey={SYNTHETIC_APIKEY}&definePrintout=onlyCustomsDeclarations"
            ),
            body=dict(deep=[f"prefix {SYNTHETIC_APIKEY} suffix"]),
        )
        safe = json.dumps(harness.redact(artifact, [SYNTHETIC_APIKEY]))
        self.assertNotIn(SYNTHETIC_APIKEY, safe)
        self.assertNotIn("apikey=", safe)
        self.assertNotIn("definePrintout", safe)
        self.assertIn(harness.REDACTED, safe)

    def test_redact_masks_any_32_character_token(self):
        unknown_key = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
        safe = harness.redact(f"<{unknown_key}>", [])
        self.assertNotIn(unknown_key, safe)
        self.assertIn(harness.REDACTED, safe)

    def test_redact_retains_print_and_booking_ids(self):
        # A printId is a 32-character alphanumeric run, exactly what the
        # apikey heuristic masks; under the artifact-id keys it must stand.
        print_id = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
        artifact = dict(
            bookingResponse=dict(
                bookingId="ILPN0010LBQRBGFFMCWLWZDUNDFQVS",
                idInformation=[
                    dict(
                        ids=[
                            dict(
                                idType="itemId",
                                value="CC613724769SE",
                                printId=print_id,
                            )
                        ]
                    )
                ],
            ),
            labelPrintout=[dict(itemIds=[dict(printId=print_id, status="OK")])],
        )
        safe = harness.redact(artifact, [SYNTHETIC_APIKEY])
        self.assertEqual(
            safe["bookingResponse"]["idInformation"][0]["ids"][0]["printId"], print_id
        )
        self.assertEqual(safe["labelPrintout"][0]["itemIds"][0]["printId"], print_id)
        self.assertEqual(
            safe["bookingResponse"]["bookingId"], "ILPN0010LBQRBGFFMCWLWZDUNDFQVS"
        )

    def test_redact_masks_the_secret_even_under_artifact_keys(self):
        embedded = f"x{SYNTHETIC_APIKEY}x"
        safe = harness.redact(dict(printId=embedded, booking_id=embedded), [SYNTHETIC_APIKEY])
        self.assertEqual(safe, dict(printId=f"x{harness.REDACTED}x", booking_id=f"x{harness.REDACTED}x"))

    def test_redact_retains_sha256_digest_lists(self):
        # with_document_metadata records each printout's digest under a
        # "sha256" key; masking the harness's own evidence digests is the
        # same evidence-loss class as masking a printId.
        digest_a = "a" * 64
        digest_b = "0123456789abcdef" * 4
        artifact = dict(
            printout=dict(
                data=dict(
                    omitted="printout data stored as raw bytes alongside",
                    files=["001-p1_cn23_gateway.printout01.pdf"],
                    sha256=[digest_a, digest_b],
                )
            ),
            single=dict(sha256=digest_a),
        )
        safe = harness.redact(artifact, [SYNTHETIC_APIKEY])
        self.assertEqual(safe["printout"]["data"]["sha256"], [digest_a, digest_b])
        self.assertEqual(safe["single"]["sha256"], digest_a)

    def test_redact_masks_non_digest_values_under_sha256_keys(self):
        # Retention under "sha256" is shape-scoped: a 32-character
        # apikey-looking value, or a 64-character non-hex one, still masks.
        keylike = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
        safe = harness.redact(
            dict(sha256=[keylike, "G" * 64], nested=dict(sha256=keylike)), []
        )
        self.assertEqual(
            safe,
            dict(
                sha256=[harness.REDACTED, harness.REDACTED + harness.REDACTED],
                nested=dict(sha256=harness.REDACTED),
            ),
        )

    def test_redact_masks_the_secret_inside_a_retained_digest(self):
        hex_secret = "abc123def456abc123def456abc123de"
        digest = f"0123456789abcdef{hex_secret}0123456789abcdef"
        safe = harness.redact(dict(sha256=digest), [hex_secret])
        self.assertNotIn(hex_secret, safe["sha256"])
        self.assertIn(harness.REDACTED, safe["sha256"])

    def test_redact_retains_the_by_id_member_id(self):
        # The by-id labels fetch keys on the printId under the generic
        # member key "id"; the apikey shares the request only as a query
        # parameter, and the query is dropped wholesale, so retaining the
        # id value cannot retain the key.
        print_id = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
        artifact = dict(
            url=(
                "https://atapi2.postnord.com/rest/shipment/v3/labels/ids/pdf"
                f"?apikey={SYNTHETIC_APIKEY}&definePrintout=onlyCustomsDeclarations"
            ),
            data=[{"id": print_id}],
        )
        safe = harness.redact(artifact, [SYNTHETIC_APIKEY])
        self.assertEqual(safe["data"], [{"id": print_id}])
        self.assertEqual(
            safe["url"],
            "https://atapi2.postnord.com/rest/shipment/v3/labels/ids/pdf",
        )
        self.assertNotIn(SYNTHETIC_APIKEY, json.dumps(safe))

    def test_redact_retains_the_by_id_response_echoed_id(self):
        # A by-id response member echoes the queried printId as a string
        # under "itemIds" (the entry's list of members shares the key);
        # masking it hides which id PostNord reported on.
        print_id = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
        body = [
            {
                "itemIds": [
                    {
                        "itemIds": print_id,
                        "status": "FAIL",
                        "errorResponse": {"message": "id not found"},
                    }
                ]
            }
        ]
        safe = harness.redact(body, [SYNTHETIC_APIKEY])
        self.assertEqual(safe, body)
        self.assertEqual(
            harness.redact(dict(item_ids=print_id), []), dict(item_ids=print_id)
        )
        embedded = f"x{SYNTHETIC_APIKEY}x"
        self.assertEqual(
            harness.redact(dict(itemIds=embedded), [SYNTHETIC_APIKEY]),
            dict(itemIds=f"x{harness.REDACTED}x"),
        )

    def test_redact_masks_32_character_tokens_under_unlisted_keys(self):
        keylike = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
        safe = harness.redact(
            dict(token=keylike, value=keylike, note=f"id {keylike}"), []
        )
        self.assertEqual(safe["token"], harness.REDACTED)
        self.assertEqual(safe["value"], harness.REDACTED)
        self.assertEqual(safe["note"], f"id {harness.REDACTED}")

    def test_redact_leaves_short_identifiers(self):
        value = dict(shipmentId="P3-NOCUSTOMS-18", partyId="12345678")
        self.assertEqual(harness.redact(value, []), value)


class TestOneShot(unittest.TestCase):
    def test_fired_segment_never_refires(self):
        class _skipped(unittest.TestCase):
            def runTest(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            marker = "p3_no_customs_raw-18"
            self.assertFalse(session.oneshot.already_fired(marker))
            harness.require_fire(_skipped(), session, marker)
            self.assertTrue(session.oneshot.already_fired(marker))
            with self.assertRaises(unittest.SkipTest) as skipped:
                harness.require_fire(_skipped(), session, marker)
            self.assertIn("already ran once", str(skipped.exception))

    def test_markers_are_per_segment(self):
        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            session.oneshot.fire("p1_cn23_gateway")
            self.assertFalse(session.oneshot.already_fired("p2_invoice_gateway"))


class TestBookingBudget(unittest.TestCase):
    def test_exhaustion_skips(self):
        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            session.budget = harness.BookingBudget(0)
            with self.assertRaises(unittest.SkipTest) as skipped:
                harness.require_booking(self, session)
            self.assertIn("booking budget exhausted", str(skipped.exception))

    def test_reserve_counts_before_the_call(self):
        budget = harness.BookingBudget(1)
        self.assertTrue(budget.reserve())
        self.assertEqual(budget.attempts, 1)
        self.assertFalse(budget.reserve())


class TestCaptures(unittest.TestCase):
    def test_capture_writes_redacted_request_and_parsed_response(self):
        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            stem = session.next_stem("p1_cn23_gateway")
            session.write_request(
                stem,
                "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/pdf"
                f"?apikey={SYNTHETIC_APIKEY}",
                dict(
                    testIndicator=True,
                    shipment=[dict(service=dict(basicServiceCode="91"))],
                ),
            )
            label = base64.b64encode(b"%PDF-1.4 sandbox label bytes").decode()
            print_id = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
            body = {
                "bookingResponse": {
                    "bookingId": "ILPN0010LBQRBGFFMCWLWZDUNDFQVS",
                    "idInformation": [
                        {
                            "status": "OK",
                            "ids": [
                                {
                                    "idType": "itemId",
                                    "value": "CC613724769SE",
                                    "printId": print_id,
                                }
                            ],
                        }
                    ],
                },
                "labelPrintout": [
                    {
                        "printoutComposition": {"shippingLabel": 1, "cn22orcn23": 1},
                        "printout": {
                            "id": 1,
                            "type": "label",
                            "labelFormat": "PDF",
                            "encoding": "base64",
                            "data": label,
                        },
                    }
                ],
            }
            session.write_response(stem, json.dumps(body))

            request = json.loads(
                (session.capture_dir / f"{stem}.request.json").read_text()
            )
            self.assertEqual(
                request["url"],
                "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/pdf",
            )
            response = json.loads(
                (session.capture_dir / f"{stem}.response.parsed.json").read_text()
            )
            data = response["body"]["labelPrintout"][0]["printout"]["data"]
            self.assertIn("omitted", data)
            self.assertEqual(data["files"], [f"{stem}.printout01.pdf"])
            self.assertEqual(
                data["sha256"],
                [hashlib.sha256(base64.b64decode(label)).hexdigest()],
            )
            document = session.capture_dir / f"{stem}.printout01.pdf"
            self.assertEqual(
                document.read_bytes(), base64.b64decode(label)
            )
            self.assertNotIn(SYNTHETIC_APIKEY, (session.capture_dir / f"{stem}.request.json").read_text())
            self.assertEqual(
                response["body"]["bookingResponse"]["idInformation"][0]["ids"][0][
                    "printId"
                ],
                print_id,
            )
            self.assertEqual(
                response["body"]["bookingResponse"]["bookingId"],
                "ILPN0010LBQRBGFFMCWLWZDUNDFQVS",
            )

    def test_capture_retains_the_by_id_request_id(self):
        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            stem = session.next_stem("p4_byid_fetch_raw")
            print_id = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
            session.write_request(
                stem,
                "https://atapi2.postnord.com/rest/shipment/v3/labels/ids/pdf"
                f"?apikey={SYNTHETIC_APIKEY}&definePrintout=onlyCustomsDeclarations",
                [{"id": print_id}],
                note="raw by-id print fetch keyed by p1's printId",
            )
            request = json.loads(
                (session.capture_dir / f"{stem}.request.json").read_text()
            )
            self.assertEqual(request["data"], [{"id": print_id}])
            self.assertEqual(
                request["url"],
                "https://atapi2.postnord.com/rest/shipment/v3/labels/ids/pdf",
            )
            self.assertNotIn(SYNTHETIC_APIKEY, json.dumps(request))

    def test_log_booking_records_the_print_id(self):
        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            print_id = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
            session.log_booking(
                "p1_cn23_gateway",
                "postnord.test_p1_cn23_gateway.TestSandboxP1CN23Gateway"
                ".test_book_91_to_albania_with_cn23",
                tracking_number="CC613724769SE",
                booking_id="ILPN0010LBQRBGFFMCWLWZDUNDFQVS",
                print_id=print_id,
            )
            lines = (session.capture_dir / "bookings.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["print_id"], print_id)
            self.assertEqual(entry["booking_id"], "ILPN0010LBQRBGFFMCWLWZDUNDFQVS")
            self.assertNotIn(SYNTHETIC_APIKEY, lines[0])

    def test_latest_segment_capture_prefers_the_newest_run(self):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = pathlib.Path(directory)
            for run in ("20261018T000000Z", "20261019T000000Z"):
                run_dir = sandbox / run
                run_dir.mkdir()
                (run_dir / "001-p1_cn23_gateway.response.parsed.json").write_text(
                    json.dumps(
                        {
                            "body": {
                                "bookingResponse": {
                                    "idInformation": [
                                        {
                                            "ids": [
                                                {
                                                    "idType": "itemId",
                                                    "value": "1",
                                                    "printId": f"print-{run}",
                                                }
                                            ]
                                        }
                                    ]
                                }
                            }
                        }
                    )
                )
            latest = harness.latest_segment_capture(sandbox, "p1_cn23_gateway")
            assert latest is not None
            self.assertEqual(latest.run_dir.name, "20261019T000000Z")
            self.assertEqual(
                harness.find_print_id(latest.parsed), "print-20261019T000000Z"
            )

    def test_latest_segment_capture_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(
                harness.latest_segment_capture(pathlib.Path(directory), "p1_cn23_gateway")
            )

    def test_latest_run_captures_returns_the_newest_run_in_call_order(self):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = pathlib.Path(directory)
            segment = "p6_cn23_standalone_gateway"
            (sandbox / "20261018T000000Z").mkdir()
            (sandbox / "20261018T000000Z" / f"001-{segment}.response.parsed.json").write_text(
                json.dumps({"body": "old"})
            )
            run_dir = sandbox / "20261026T000000Z"
            run_dir.mkdir()
            for stem, body in (("002", "byid"), ("001", "booking")):
                (run_dir / f"{stem}-{segment}.response.parsed.json").write_text(
                    json.dumps({"body": body})
                )
            (run_dir / f"003-{segment}.result.json").write_text("{}")
            captures = harness.latest_run_captures(sandbox, segment)
            self.assertEqual(
                [(c.run_dir.name, c.parsed["body"]) for c in captures],
                [("20261026T000000Z", "booking"), ("20261026T000000Z", "byid")],
            )
            latest = harness.latest_segment_capture(sandbox, segment)
            assert latest is not None
            self.assertEqual(latest.parsed["body"], "byid")
            self.assertEqual(harness.latest_run_captures(sandbox, "p9_absent"), [])
            self.assertEqual(
                harness.latest_run_captures(sandbox / "missing", segment), []
            )

    def test_byid_failure_accepts_only_a_usable_printout(self):
        printout = {"labelFormat": "PDF", "data": base64.b64encode(b"%PDF-1.4").decode()}
        self.assertIsNone(
            harness.byid_failure(
                [{"itemIds": [{"status": "OK"}], "printout": printout}]
            )
        )
        self.assertEqual(
            harness.byid_failure(
                [
                    {
                        "itemIds": [
                            {"status": "FAIL", "errorResponse": {"message": "id not found"}}
                        ],
                        "printout": printout,
                    }
                ]
            ),
            "per-id FAIL: id not found",
        )
        self.assertEqual(
            harness.byid_failure(
                [{"itemIds": [{"status": "OK"}], "printoutComposition": {"cn23": 0}}]
            ),
            "no printout data in the by-id response",
        )
        self.assertEqual(
            harness.byid_failure({"compositeFault": {"faults": []}}),
            "the by-id response is not a labelPrintout list",
        )
        self.assertEqual(
            harness.byid_failure(None),
            "the by-id response is not a labelPrintout list",
        )

    def test_find_print_id_and_absence(self):
        parsed = {
            "body": {
                "bookingResponse": {
                    "idInformation": [
                        {"ids": [{"idType": "shipmentId", "value": "s1"}]},
                        {"ids": [{"idType": "itemId", "value": "i1", "printId": "print-1"}]},
                    ]
                }
            }
        }
        self.assertEqual(harness.find_print_id(parsed), "print-1")
        self.assertIsNone(harness.find_print_id({"body": {}}))

    def test_find_print_id_refuses_the_redaction_sentinel(self):
        # A pre-fix capture holds the sentinel where the printId belongs;
        # keying a by-id fetch on it queries an id that never existed.
        parsed = {
            "body": {
                "labelPrintout": [
                    {"itemIds": [{"itemIds": "CC613724769SE", "printId": harness.REDACTED}]}
                ]
            }
        }
        self.assertIsNone(harness.find_print_id(parsed))

    def test_extract_documents_handles_by_id_list_shape(self):
        documents = harness.extract_documents(
            [
                {
                    "itemIds": [{"status": "FAIL"}],
                    "printout": {
                        "labelFormat": "ZPL",
                        "encoding": "none",
                        "data": "^XA^PW609",
                    },
                }
            ]
        )
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].extension, "zpl")
        self.assertEqual(documents[0].data, b"^XA^PW609")

    def test_capture_gateway_calls_pairs_tracer_records(self):
        import karrio.sdk as karrio

        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            gateway = karrio.gateway["postnord"].create(
                dict(
                    id="selftest",
                    test_mode=True,
                    carrier_id="postnord",
                    apikey=SYNTHETIC_APIKEY,
                    customer_number="12345678",
                    issuer_code="Z12",
                    account_country_code="SE",
                )
            )
            gateway.tracer.trace(
                {
                    "request_id": "r1",
                    "url": (
                        "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/pdf"
                        f"?apikey={SYNTHETIC_APIKEY}"
                    ),
                    "data": json.dumps({"testIndicator": True}),
                },
                "request",
            )
            gateway.tracer.trace(
                {"request_id": "r1", "response": json.dumps({"bookingResponse": {}})},
                "response",
            )

            bodies = session.capture_gateway_calls(gateway, "p1_cn23_gateway")
            self.assertEqual(bodies, [{"bookingResponse": {}}])
            files = sorted(path.name for path in session.capture_dir.iterdir())
            self.assertEqual(
                files,
                [
                    "001-p1_cn23_gateway.request.json",
                    "001-p1_cn23_gateway.response.parsed.json",
                ],
            )
            safe = (session.capture_dir / files[0]).read_text()
            self.assertNotIn(SYNTHETIC_APIKEY, safe)
            self.assertNotIn("apikey", safe)

    def test_gateway_resolves_the_sandbox_origin_in_test_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            gateway = session.gateway()
            self.assertTrue(gateway.settings.test_mode)
            self.assertEqual(gateway.settings.server_url, harness.SANDBOX_ORIGIN)
            harness.check_url(gateway.settings.server_url or "")


class TestPayloads(unittest.TestCase):
    """The probe payloads serialize onto the intended PostNord branches.

    Request building is offline, so the shapes the live segments will send
    are pinned here before any probe fires: p1 onto the CN23 branch with
    zero postalCharges, p2 onto the commercial customs invoice, and the raw
    body onto a customs-less ediInstruction with the test flag.
    """

    def setUp(self):
        self.maxDiff = None
        import karrio.core.models as models
        import karrio.lib as lib

        self.models = models
        self.lib = lib
        with tempfile.TemporaryDirectory() as directory:
            self.gateway = offline_session(pathlib.Path(directory)).gateway()

    def _serialized(self, payload: dict) -> typing.Any:
        request = self.gateway.mapper.create_shipment_request(
            self.models.ShipmentRequest(**payload)
        )
        return self.lib.to_dict(request.serialize())

    def test_cn23_payload_books_the_cn23_branch(self):
        body = self._serialized(
            payloads.cn23_payload("SE556000123401", "P1-CN23-GATEWAY")
        )
        self.assertTrue(body["testIndicator"])
        entry = body["shipment"][0]
        self.assertEqual(entry["service"]["basicServiceCode"], "91")
        self.assertIn("customsDeclarationCN23", entry)
        self.assertNotIn("customsDeclarationCN22", entry)
        self.assertNotIn("customsInvoice", entry)
        declaration = entry["customsDeclarationCN23"]
        self.assertEqual(
            declaration["EORIorPersonalIdNumber"], "SE556000123401"
        )
        self.assertEqual(
            declaration["postalCharges"], {"amount": 0, "currency": "SEK"}
        )
        self.assertEqual(len(declaration["detailedDescription"]), 2)
        self.assertEqual(
            entry["parties"]["consignee"]["party"]["address"]["countryCode"], "AL"
        )

    def test_standalone_cn23_payload_sets_the_connector_opt_in(self):
        plain = self.gateway.mapper.create_shipment_request(
            self.models.ShipmentRequest(
                **payloads.cn23_payload("SE556000123401", "P1-CN23-GATEWAY")
            )
        )
        standalone = self.gateway.mapper.create_shipment_request(
            self.models.ShipmentRequest(
                **payloads.cn23_payload(
                    "SE556000123401",
                    "P6-CN23-STANDALONE",
                    standalone_customs_documents=True,
                )
            )
        )
        self.assertFalse(plain.ctx.get("standalone_customs_documents"))
        self.assertIs(standalone.ctx["standalone_customs_documents"], True)
        self.assertTrue(standalone.ctx.get("customs_declared"))
        self.assertEqual(standalone.ctx.get("basic_service_code"), "91")
        self.assertEqual((standalone.ctx.get("label_type") or "PDF").upper(), "PDF")
        body = self.lib.to_dict(standalone.serialize())
        self.assertIn("customsDeclarationCN23", body["shipment"][0])
        self.assertNotIn(
            "postnord_standalone_customs_documents", json.dumps(body)
        )

    def test_invoice_payload_books_the_commercial_invoice_branch(self):
        body = self._serialized(
            payloads.invoice_payload("SE556000123401", "P2-INVOICE-GATEWAY")
        )
        entry = body["shipment"][0]
        self.assertEqual(entry["service"]["basicServiceCode"], "18")
        self.assertIn("customsInvoice", entry)
        self.assertNotIn("customsDeclarationCN23", entry)
        invoice = entry["customsInvoice"]
        self.assertEqual(invoice["type"], "COMMERCIAL")
        self.assertEqual(invoice["seller"]["eoriNo"], "SE556000123401")
        self.assertEqual(invoice["buyer"]["countryCode"], "AL")

    def test_raw_booking_body_carries_no_customs_and_flags_test(self):
        for code in ("18", "91"):
            with self.subTest(basic_service_code=code):
                body = payloads.raw_booking_body(code, "12345678")
                self.assertTrue(body["testIndicator"])
                self.assertEqual(body["updateIndicator"], "Original")
                self.assertNotIn("application", body)
                entry = body["shipment"][0]
                self.assertEqual(entry["service"], {"basicServiceCode": code})
                self.assertEqual(
                    sorted(entry),
                    [
                        "goodsItem",
                        "parties",
                        "service",
                        "shipmentIdentification",
                    ],
                )
                self.assertEqual(
                    entry["parties"]["consignor"]["partyIdentification"],
                    {"partyId": "12345678", "partyIdType": "160"},
                )

    def test_raw_booking_body_injects_the_application_object(self):
        body = payloads.raw_booking_body(
            "91",
            "12345678",
            application={"name": "Karrio", "applicationId": 7351},
        )
        self.assertEqual(
            body["application"], {"name": "Karrio", "applicationId": 7351}
        )
        self.assertTrue(body["testIndicator"])
        self.assertNotIn("customsDeclarationCN23", body["shipment"][0])


class TestApplicationId(unittest.TestCase):
    """The p5 application-id gate: absent skips, malformed refuses, valid builds."""

    def test_absent_skips(self):
        for environment in ({}, {"POSTNORD_APPLICATION_ID": ""}):
            with self.subTest(environment=environment):
                self.assertIsNone(payloads.application_object(environment))
        from .test_p5_no_customs_with_application_raw import require_application

        with self.assertRaises(unittest.SkipTest) as skipped:
            require_application(_skipped_case(), {})
        self.assertIn("POSTNORD_LIVE_APPLICATION_ID", str(skipped.exception))

    def test_malformed_refuses(self):
        for value in ("12345", "12", "abcd", "24 58", "0x58"):
            with self.subTest(value=value):
                with self.assertRaises(harness.SandboxConfigError) as refused:
                    payloads.application_object(
                        {"POSTNORD_LIVE_APPLICATION_ID": value}
                    )
                self.assertIn("4-digit", str(refused.exception))

    def test_valid_id_builds_the_application_object(self):
        self.assertEqual(
            payloads.application_object({"POSTNORD_LIVE_APPLICATION_ID": "7351"}),
            {"name": "Karrio", "applicationId": 7351},
        )
        self.assertEqual(
            payloads.application_object({"POSTNORD_APPLICATION_ID": " 9999 "}),
            {"name": "Karrio", "applicationId": 9999},
        )

    def test_live_variable_wins_over_the_fallback(self):
        self.assertEqual(
            payloads.application_object(
                {
                    "POSTNORD_LIVE_APPLICATION_ID": "7351",
                    "POSTNORD_APPLICATION_ID": "1111",
                }
            ),
            {"name": "Karrio", "applicationId": 7351},
        )


class TestPublicQuery(unittest.TestCase):
    def test_public_query_drops_only_the_apikey(self):
        self.assertEqual(
            harness.public_query(
                "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/zpl"
                f"?apikey={SYNTHETIC_APIKEY}&labelType=small&locale=en"
            ),
            {"labelType": "small", "locale": "en"},
        )
        self.assertEqual(
            harness.public_query(
                f"https://atapi2.postnord.com/x?APIKEY={SYNTHETIC_APIKEY}"
            ),
            {},
        )

    def test_write_request_keeps_the_non_credential_query(self):
        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            stem = session.next_stem("p7_label_size_small_zpl")
            session.write_request(
                stem,
                "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/zpl"
                f"?apikey={SYNTHETIC_APIKEY}&labelType=small&locale=en",
                dict(testIndicator=True),
            )
            text = (session.capture_dir / f"{stem}.request.json").read_text()
            request = json.loads(text)
            self.assertEqual(
                request["url"],
                "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/zpl",
            )
            self.assertEqual(request["query"], {"labelType": "small", "locale": "en"})
            self.assertNotIn(SYNTHETIC_APIKEY, text)
            self.assertNotIn("apikey", text.lower())

    def test_write_request_omits_an_empty_query(self):
        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            stem = session.next_stem("p1_cn23_gateway")
            session.write_request(
                stem,
                "https://atapi2.postnord.com/rest/shipment/v3/edi/labels/pdf"
                f"?apikey={SYNTHETIC_APIKEY}",
                dict(testIndicator=True),
            )
            request = json.loads(
                (session.capture_dir / f"{stem}.request.json").read_text()
            )
            self.assertNotIn("query", request)


class TestP7LabelSizeSegments(unittest.TestCase):
    """The p7 bookings reach the intended endpoint with the intended labelType.

    The connector's request is intercepted at the proxy's ``lib.request``,
    so each case's URL and body are pinned offline before anything fires.
    """

    def setUp(self):
        from . import test_p7_label_size as p7

        self.p7 = p7

    def test_cases_fire_in_the_approved_order_with_distinct_markers(self):
        self.assertEqual(
            self.p7.CASES,
            (("small", "ZPL"), ("small", "PDF"), ("ste", "PDF"), ("ste", "ZPL")),
        )
        segments = [self.p7.segment_name(*case) for case in self.p7.CASES]
        self.assertEqual(
            segments,
            [
                "p7_label_size_small_zpl",
                "p7_label_size_small_pdf",
                "p7_label_size_ste_pdf",
                "p7_label_size_ste_zpl",
            ],
        )
        methods = unittest.TestLoader().getTestCaseNames(
            self.p7.TestSandboxP7LabelSize
        )
        self.assertEqual(
            list(methods),
            [
                f"test_{index}_{size}_{fmt.lower()}"
                for index, (size, fmt) in enumerate(self.p7.CASES, start=1)
            ],
        )
        self.assertLessEqual(len(self.p7.CASES), harness.DEFAULT_MAX_BOOKINGS)

    def test_gateway_carries_the_connection_label_size(self):
        with tempfile.TemporaryDirectory() as directory:
            session = offline_session(pathlib.Path(directory))
            self.assertIsNone(
                session.gateway().settings.connection_config.label_size.state
            )
            gateway = session.gateway(dict(label_size="ste"))
            self.assertEqual(
                gateway.settings.connection_config.label_size.state, "ste"
            )
            self.assertTrue(gateway.settings.test_mode)
            self.assertEqual(gateway.settings.server_url, harness.SANDBOX_ORIGIN)

    def test_each_case_books_the_cn23_branch_on_its_format_endpoint(self):
        from unittest import mock

        import karrio.core.models as models
        import karrio.sdk as karrio

        for label_size, label_format in self.p7.CASES:
            with self.subTest(label_size=label_size, label_format=label_format):
                with tempfile.TemporaryDirectory() as directory:
                    session = offline_session(pathlib.Path(directory))
                    gateway = session.gateway(dict(label_size=label_size))
                    with mock.patch(
                        "karrio.mappers.postnord.proxy.lib.request"
                    ) as request:
                        request.return_value = "{}"
                        karrio.Shipment.create(
                            models.ShipmentRequest(
                                **payloads.cn23_payload(
                                    "SE556000123401",
                                    self.p7.reference(label_size, label_format),
                                    label_type=label_format,
                                )
                            )
                        ).from_(gateway)
                    self.assertEqual(request.call_count, 1)
                    url = request.call_args[1]["url"]
                    self.assertEqual(
                        harness.strip_query(url),
                        f"{harness.SANDBOX_ORIGIN}/rest/shipment/v3/edi/labels/"
                        f"{label_format.lower()}",
                    )
                    self.assertEqual(
                        harness.public_query(url)["labelType"], label_size
                    )
                    harness.check_url(url)
                    body = json.loads(request.call_args[1]["data"])
                    harness.check_booking_body(url, json.dumps(body))
                    entry = body["shipment"][0]
                    self.assertEqual(entry["service"]["basicServiceCode"], "91")
                    self.assertIn("customsDeclarationCN23", entry)
                    self.assertEqual(
                        entry["parties"]["consignee"]["party"]["address"][
                            "countryCode"
                        ],
                        "AL",
                    )
