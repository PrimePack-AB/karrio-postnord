"""Offline checks on the committed sandbox evidence fixtures.

The fixtures under fixtures/sandbox/ back the sandbox citations in the
probe note (docs/notes/sandbox/cn23-composition-sandbox-probe.md): each
is a byte-identical copy of a capture file named by the manifest. These
tests pin that identity through the manifest's recorded sha256 values,
tie the manifest's source shas back to the note's capture table, and
keep every fixture free of apikey-shaped runs using the sandbox harness
redactor's exemption semantics, mirrored here so the offline suite
stands alone of sandbox_tests.
"""

import hashlib
import json
import pathlib
import re
import typing
import unittest

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "sandbox"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"
PROBE_NOTE = (
    pathlib.Path(__file__).resolve().parents[2]
    / "docs"
    / "notes"
    / "sandbox"
    / "cn23-composition-sandbox-probe.md"
)
NOTE_ROW = re.compile(
    r"^\| (\d{8}T\d{6}Z) \| `([^`]+)` \| `([0-9a-f]{64})` \|$", re.MULTILINE
)
# The harness redactor's exemptions, mirrored: artifact-id keys retain any
# identifier run, and sha256 keys retain only digest-shaped values. The
# digest rule widens the harness's exact "sha256" key by suffix so the
# manifest's source_sha256 keys admit their digests; both admit only
# 64-lowercase-hex values, which no 32-character apikey is.
ARTIFACT_ID_KEYS = frozenset({"printid", "print_id", "bookingid", "booking_id", "id"})
APIKEY_RUN = re.compile(r"[A-Za-z0-9]{32,}")
SHA256 = re.compile(r"[0-9a-f]{64}")
APIKEY_RUN_BYTES = re.compile(rb"[A-Za-z0-9]{32,}")
PDF_TRAILER_ID = re.compile(rb"/ID\s*\[<([A-Fa-f0-9]{32})>\s*<([A-Fa-f0-9]{32})>\]")
PDF_PAGE = re.compile(rb"/Type\s*/Page[^s]")
KINDS = ("response.parsed", "printout")
EXPECTED_SEGMENTS = {
    "p1_cn23_gateway": {"response.parsed", "printout"},
    "p2_invoice_gateway": {"response.parsed"},
    "p3_no_customs_raw-18": {"response.parsed"},
    "p3_no_customs_raw-91": {"response.parsed"},
    "p5_no_customs_with_application_raw": {"response.parsed", "printout"},
    "p4_byid_fetch_raw": {"response.parsed"},
}


def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def note_capture_table() -> typing.Dict[typing.Tuple[str, str], str]:
    """The note's capture table as {(run, file): sha256}."""
    return {
        (run, file): sha
        for run, file, sha in NOTE_ROW.findall(PROBE_NOTE.read_text())
    }


def unexplained_runs(
    value: typing.Any, parent: str = "", path: str = "$"
) -> typing.List[typing.Tuple[str, str]]:
    """(path, run) pairs the redaction exemptions cannot explain."""
    found: typing.List[typing.Tuple[str, str]] = []
    if isinstance(value, dict):
        for key, entry in value.items():
            found.extend(unexplained_runs(entry, str(key), f"{path}.{key}"))
    elif isinstance(value, list):
        for index, entry in enumerate(value):
            found.extend(unexplained_runs(entry, parent, f"{path}[{index}]"))
    elif isinstance(value, str) and parent.lower() not in ARTIFACT_ID_KEYS:
        for run in APIKEY_RUN.findall(value):
            if not (parent.lower().endswith("sha256") and SHA256.fullmatch(run)):
                found.append((path, run))
    return found


def pdf_runs_outside_the_trailer_ids(raw: bytes) -> typing.List[str]:
    """32-character runs in a printout that are not trailer /ID values."""
    trailer_ids = {
        value.decode("ascii")
        for pair in PDF_TRAILER_ID.findall(raw)
        for value in pair
    }
    return sorted(
        {
            run.decode("ascii", "replace")
            for run in APIKEY_RUN_BYTES.findall(raw)
        }
        - trailer_ids
    )


class TestSandboxEvidenceManifest(unittest.TestCase):
    def test_manifest_lists_exactly_the_committed_fixtures(self):
        committed = sorted(
            path.name for path in FIXTURE_DIR.iterdir() if path.name != "manifest.json"
        )
        listed = sorted(entry["fixture"] for entry in manifest()["fixtures"])
        self.assertEqual(listed, committed)

    def test_manifest_provenance_fields(self):
        document = manifest()
        self.assertTrue(document["generator"].endswith("sandbox_tests/postnord/evidence.py"))
        self.assertTrue(document["probe_note"].endswith("cn23-composition-sandbox-probe.md"))
        self.assertTrue(pathlib.Path(document["probe_note"]).is_file())
        self.assertIn("karrio-postnord/sandbox", document["capture_root"])
        self.assertTrue(document["redaction_policy"])

    def test_every_fixture_matches_its_recorded_sha(self):
        for entry in manifest()["fixtures"]:
            with self.subTest(fixture=entry["fixture"]):
                digest = hashlib.sha256(
                    (FIXTURE_DIR / entry["fixture"]).read_bytes()
                ).hexdigest()
                self.assertEqual(digest, entry["sha256"])
                if entry["byte_identical"]:
                    self.assertEqual(digest, entry["source_sha256"])

    def test_source_shas_match_the_probe_note_capture_table(self):
        table = note_capture_table()
        pinned = 0
        for entry in manifest()["fixtures"]:
            source = (entry["source_run"], entry["source_file"])
            with self.subTest(fixture=entry["fixture"]):
                self.assertIn(source, table)
                self.assertEqual(entry["source_sha256"], table[source])
                pinned += 1
        # every fixture, the printouts included, is pinned by the note
        self.assertEqual(pinned, 8)

    def test_fixture_set_covers_the_probe_rounds(self):
        kinds_by_segment: typing.Dict[str, typing.Set[str]] = {}
        for entry in manifest()["fixtures"]:
            self.assertIn(entry["kind"], KINDS)
            self.assertEqual(
                entry["fixture"].endswith(".pdf"),
                entry["kind"] == "printout",
            )
            kinds_by_segment.setdefault(entry["segment"], set()).add(entry["kind"])
        self.assertEqual(kinds_by_segment, EXPECTED_SEGMENTS)


class TestSandboxEvidenceSecrets(unittest.TestCase):
    def test_no_json_fixture_carries_an_unexplained_run(self):
        for path in sorted(FIXTURE_DIR.glob("*.json")):
            with self.subTest(fixture=path.name):
                self.assertEqual(unexplained_runs(json.loads(path.read_text())), [])

    def test_printout_runs_are_trailer_id_values_only(self):
        printouts = 0
        for entry in manifest()["fixtures"]:
            if entry["kind"] != "printout":
                continue
            printouts += 1
            raw = (FIXTURE_DIR / entry["fixture"]).read_bytes()
            with self.subTest(fixture=entry["fixture"]):
                self.assertEqual(pdf_runs_outside_the_trailer_ids(raw), [])
        self.assertEqual(printouts, 2)

    def test_apikey_scan_flags_planted_runs(self):
        keylike = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
        self.assertEqual(
            unexplained_runs(dict(value=keylike, note=f"id {keylike}")),
            [("$.value", keylike), ("$.note", keylike)],
        )

    def test_apikey_scan_exempts_only_the_redactor_semantics(self):
        keylike = "z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4"
        digest = "0123456789abcdef" * 4
        artifact = dict(
            printId=keylike,
            ids=[dict(id=keylike)],
            sha256=[digest],
            source_sha256=digest,
        )
        self.assertEqual(unexplained_runs(artifact), [])
        # an apikey-shaped value under a digest key is not digest-shaped
        self.assertEqual(
            unexplained_runs(dict(sha256=keylike)), [("$.sha256", keylike)]
        )

    def test_printout_page_counts_match_the_manifest(self):
        for entry in manifest()["fixtures"]:
            if entry["kind"] != "printout":
                continue
            raw = (FIXTURE_DIR / entry["fixture"]).read_bytes()
            with self.subTest(fixture=entry["fixture"]):
                self.assertEqual(len(PDF_PAGE.findall(raw)), entry["pages"])
                self.assertEqual(len(entry["page_size_pt"]), 2)

    def test_the_void_capture_is_labeled_and_fails_per_id(self):
        (void_entry,) = [e for e in manifest()["fixtures"] if e.get("void")]
        self.assertEqual(void_entry["segment"], "p4_byid_fetch_raw")
        body = json.loads((FIXTURE_DIR / void_entry["fixture"]).read_text())["body"]
        member = body[0]["itemIds"][0]
        self.assertEqual(member["status"], "FAIL")
        self.assertEqual(member["errorResponse"]["message"], "id not found")


if __name__ == "__main__":
    unittest.main()
