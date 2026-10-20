"""Build the sandbox evidence fixtures from the out-of-repo captures.

The captures stay under the XDG state directory, outside the repository
(``karrio-postnord/sandbox/<run>/`` below the state root). This module
reads the evidence-of-record files of the 2026-10-19 probe round, checks
that no apikey-shaped run survives outside the redactor's own
exemptions, and copies them: the responses, byte-identical except for
the redactions below, into ``tests/postnord/fixtures/sandbox/`` next to
a manifest recording each fixture's source run, source file, and
digests, and the
printouts, which are PostNord content the repository does not
distribute, into the ``sandbox/`` directory of the local fixture
directory (``$POSTNORD_FIXTURES_DIR``, or ``karrio-postnord/fixtures/``
below the state root; see tests/postnord/local_fixtures.py).

Redaction policy (CLAUDE.md "Evidence and redaction rules"): printIds,
bookingIds, item ids, and the dummy EORI are artifact values and stand as
captured. The customer number (``POSTNORD_CUSTOMER_NUMBER``) and the
application id (``POSTNORD_LIVE_APPLICATION_ID``, falling back to
``POSTNORD_APPLICATION_ID``) are kept only in ``.env``: a response that
carries either is written with the placeholder in its place, and its
manifest entry records the fixture's sha256 only, with no source digest
and ``byte_identical`` false. The 32-character apikey traveled as a query
parameter and was stripped wholesale at capture time; the build fails if
any 32-character alphanumeric run appears that the harness redactor's
exemptions (artifact-id keys, digest-shaped sha256 values, and a PDF's
trailer /ID document instance ids) do not explain.

Run it from the repository root::

    .venv/bin/python -m sandbox_tests.postnord.evidence
    .venv/bin/python -m sandbox_tests.postnord.evidence \\
        --state-root ~/.local/state --out /tmp/fixtures \\
        --printout-out /tmp/fixtures/printouts
"""

import argparse
import dataclasses
import hashlib
import json
import os
import pathlib
import re
import sys
import typing

from . import harness

Json = typing.Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "tests" / "postnord" / "fixtures" / "sandbox"
PROBE_NOTE = "docs/notes/sandbox/cn23-composition-sandbox-probe.md"
CAPTURE_DIR_NAME = "karrio-postnord/sandbox"
APIKEY_LIKE_RUN = re.compile(rb"[A-Za-z0-9]{32,}")
PDF_TRAILER_ID = re.compile(rb"/ID\s*\[<([A-Fa-f0-9]{32})>\s*<([A-Fa-f0-9]{32})>\]")
PDF_PAGE = re.compile(rb"/Type\s*/Page[^s]")
CUSTOMER_NUMBER_PLACEHOLDER = b"20000000"
APPLICATION_ID_PLACEHOLDER = b"7351"
PDF_MEDIA_BOX = re.compile(
    rb"/MediaBox\s*\[\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*\]"
)


@dataclasses.dataclass(frozen=True)
class FixtureSpec:
    """One committed fixture and the capture file behind it."""

    fixture: str
    kind: str
    segment: str
    run: str
    capture: str
    description: str
    notes: str = ""
    void: bool = False


ROUND_ONE = "20261019T120300Z"
ROUND_TWO = "20261019T120356Z"
ROUND_THREE = "20261019T120422Z"
ROUND_FIVE = "20261019T121021Z"
ROUND_FOUR = "20261019T121054Z"

CATALOG: typing.Tuple[FixtureSpec, ...] = (
    FixtureSpec(
        fixture="p1-cn23-gateway.response.json",
        kind="response.parsed",
        segment="p1_cn23_gateway",
        run=ROUND_ONE,
        capture="001-p1_cn23_gateway.response.parsed.json",
        description=(
            "91 SE to AL booked through the connector with the mapper-built "
            "customsDeclarationCN23: accepted, bookingId and item id allocated, "
            "printoutComposition {cn23: 1, label: 1}, and the two SAO-HR-25060301 "
            "phone/sms sanitizations under handlingResponse."
        ),
        notes=(
            "captured before the printId-retention fix (33d085f): the printId "
            "fields hold the <redacted> sentinel and the printout digest list "
            "was masked by the pre-fix apikey heuristic (closed for later "
            "captures by 32ce7ec); P1's real printId was never retained "
            "anywhere and is unrecoverable, so the fixture keeps the sentinel."
        ),
    ),
    FixtureSpec(
        fixture="p1-cn23-gateway.printout01.pdf",
        kind="printout",
        segment="p1_cn23_gateway",
        run=ROUND_ONE,
        capture="001-p1_cn23_gateway.printout01.pdf",
        description=(
            "the composed printout of the CN23 booking: one two-page A4 PDF, "
            "page 1 the International Parcel label, page 2 the CN23 customs "
            "declaration; the first CN23-composed capture in this project or "
            "the fork, and the candidate source for deriving CN23 stamping seeds."
        ),
    ),
    FixtureSpec(
        fixture="p2-invoice-gateway.response.json",
        kind="response.parsed",
        segment="p2_invoice_gateway",
        run=ROUND_TWO,
        capture="001-p2_invoice_gateway.response.parsed.json",
        description=(
            "18 SE to AL commercial customs-invoice booking rejected with "
            "SAI-BR-24111201: id allocation precedes customs consideration, "
            "so the invoice branch cannot be exercised on this lane."
        ),
        notes=(
            "the fault explanation's customer number is replaced by the "
            "placeholder 20000000; the capture's digest was withdrawn on "
            "2026-10-20."
        ),
    ),
    FixtureSpec(
        fixture="p3-no-customs-raw-18.response.json",
        kind="response.parsed",
        segment="p3_no_customs_raw-18",
        run=ROUND_THREE,
        capture="001-p3_no_customs_raw-18.response.parsed.json",
        description=(
            "raw minimal 18 booking with no customs and no application "
            "object: the same SAI-BR-24111201 allocation fault as p2."
        ),
        notes=(
            "the fault explanation's customer number is replaced by the "
            "placeholder 20000000; the capture's digest was withdrawn on "
            "2026-10-20."
        ),
    ),
    FixtureSpec(
        fixture="p3-no-customs-raw-91.response.json",
        kind="response.parsed",
        segment="p3_no_customs_raw-91",
        run=ROUND_THREE,
        capture="003-p3_no_customs_raw-91.response.parsed.json",
        description=(
            "raw minimal 91 booking with no customs and no application "
            "object: rejected with SACUS-BR-24100901 demanding an "
            "applicationId, the customs-linkage gate with neither linkage "
            "present."
        ),
    ),
    FixtureSpec(
        fixture="p5-no-customs-with-application-raw.response.json",
        kind="response.parsed",
        segment="p5_no_customs_with_application_raw",
        run=ROUND_FIVE,
        capture="001-p5_no_customs_with_application_raw.response.parsed.json",
        description=(
            "the p3-91 body unchanged plus the top-level application object "
            "carrying the configured four-digit application id: accepted, "
            "printoutComposition {label: 1} with every customs kind at 0."
        ),
        notes=(
            "captured after the printId fix (33d085f), so both printId "
            "fields are byte-real; the digest list was still masked "
            "(32ce7ec postdates the round)."
        ),
    ),
    FixtureSpec(
        fixture="p5-no-customs-with-application-raw.printout01.pdf",
        kind="printout",
        segment="p5_no_customs_with_application_raw",
        run=ROUND_FIVE,
        capture="001-p5_no_customs_with_application_raw.printout01.pdf",
        description=(
            "the bare one-page A4 label of the application-linked booking: "
            "with no customs declaration received, definePrintout=ALL "
            "prints no blank customs form."
        ),
    ),
    FixtureSpec(
        fixture="p4-byid-fetch-raw.response.json",
        kind="response.parsed",
        segment="p4_byid_fetch_raw",
        run=ROUND_FOUR,
        capture="001-p4_byid_fetch_raw.response.parsed.json",
        description=(
            "HTTP 200 with per-id FAIL 'id not found' from the "
            "onlyCustomsDeclarations by-id fetch."
        ),
        notes=(
            "VOID as evidence: the fetch keyed on the pre-fix <redacted> "
            "sentinel the p1 capture held, never a real printId, so the "
            "recorded answer is our artifact, not PostNord behavior; no "
            "claim about the by-id endpoint rests on it."
        ),
        void=True,
    ),
)


def changed_paths(original: Json, redacted: Json, path: str = "$") -> typing.List[str]:
    """JSON paths where ``redacted`` diverges from ``original``."""
    if original == redacted:
        return []
    if isinstance(original, dict) and isinstance(redacted, dict):
        paths: typing.List[str] = []
        for key in original.keys() | redacted.keys():
            paths.extend(
                changed_paths(
                    original.get(key), redacted.get(key), f"{path}.{key}"
                )
            )
        return paths
    if isinstance(original, list) and isinstance(redacted, list):
        return [
            changed
            for index, (left, right) in enumerate(zip(original, redacted))
            for changed in changed_paths(left, right, f"{path}[{index}]")
        ] or [f"{path}: length {len(original)} -> {len(redacted)}"]
    return [f"{path}: {original!r} -> {redacted!r}"]


def check_response(raw: bytes, source: pathlib.Path) -> Json:
    """Parse a response capture and refuse any redactor-visible secret in it.

    Running the parsed body through ``harness.redact`` with no configured
    secrets must be a no-op: every 32-character alphanumeric run has to
    sit under an exemption (artifact-id keys, digest-shaped sha256
    values), or the redactor would mask it and the fixture cannot commit.
    """
    parsed = json.loads(raw)
    paths = changed_paths(parsed, harness.redact(parsed, []))
    if paths:
        raise SystemExit(
            f"{source}: apikey-shaped runs outside the redactor's exemptions "
            f"at {', '.join(paths)}"
        )
    return parsed


def check_printout(raw: bytes, source: pathlib.Path) -> None:
    """Refuse a printout whose 32-character runs are not trailer /ID values.

    A PDF's only legitimate 32-hex runs are its trailer /ID document
    instance ids; anything else that length is treated as a secret.
    """
    trailer_ids = {
        value.decode("ascii")
        for pair in PDF_TRAILER_ID.findall(raw)
        for value in pair
    }
    unexplained = {
        run.decode("ascii", "replace")
        for run in APIKEY_LIKE_RUN.findall(raw)
    } - trailer_ids
    if unexplained:
        raise SystemExit(
            f"{source}: 32-character alphanumeric runs outside the PDF "
            f"trailer /ID values: {', '.join(sorted(unexplained))}"
        )


def page_geometry(raw: bytes) -> typing.Tuple[int, typing.List[float]]:
    media_box = PDF_MEDIA_BOX.search(raw)
    assert media_box, "no MediaBox in the printout"
    width = float(media_box.group(3)) - float(media_box.group(1))
    height = float(media_box.group(4)) - float(media_box.group(2))
    return len(PDF_PAGE.findall(raw)), [width, height]


def redaction_rules(
    environ: typing.Mapping[str, str],
) -> typing.Tuple[typing.Tuple[typing.Pattern[bytes], bytes], ...]:
    """The substitutions that keep the customer number and application id
    out of the fixtures; refuses to build without the customer number."""
    customer = (environ.get("POSTNORD_CUSTOMER_NUMBER") or "").strip()
    if not customer:
        raise harness.SandboxConfigError(
            "POSTNORD_CUSTOMER_NUMBER is not set; the build replaces it in "
            "the fixtures and cannot check them without it"
        )
    rules = [
        (
            re.compile(rb"(?<![0-9])" + re.escape(customer.encode()) + rb"(?![0-9])"),
            CUSTOMER_NUMBER_PLACEHOLDER,
        )
    ]
    application = (
        environ.get("POSTNORD_LIVE_APPLICATION_ID")
        or environ.get("POSTNORD_APPLICATION_ID")
        or ""
    ).strip()
    if application:
        value = re.escape(application.encode())
        rules.append(
            (
                re.compile(
                    rb'(?<="applicationId": )' + value + rb"(?![0-9])"
                    rb"|(?<=applicationId \()" + value + rb"(?=\))"
                ),
                APPLICATION_ID_PLACEHOLDER,
            )
        )
    return tuple(rules)


def redact(
    raw: bytes, rules: typing.Sequence[typing.Tuple[typing.Pattern[bytes], bytes]]
) -> bytes:
    for pattern, placeholder in rules:
        raw = pattern.sub(placeholder, raw)
    return raw


def manifest_entry(spec: FixtureSpec, raw: bytes, written: bytes) -> Json:
    """The provenance entry; a redacted fixture records no source digest."""
    digest = hashlib.sha256(written).hexdigest()
    byte_identical = written == raw
    entry: typing.Dict[str, Json] = dict(
        fixture=spec.fixture,
        kind=spec.kind,
        segment=spec.segment,
        source_run=spec.run,
        source_file=spec.capture,
        source_path=str(pathlib.PurePosixPath(spec.run) / spec.capture),
        source_sha256=digest if byte_identical else None,
        sha256=digest,
        byte_identical=byte_identical,
        description=spec.description,
        notes=spec.notes or None,
    )
    if spec.void:
        entry["void"] = True
    if spec.kind == "printout":
        pages, page_size_pt = page_geometry(raw)
        entry["pages"] = pages
        entry["page_size_pt"] = page_size_pt
    return entry


def local_printout_dir(environ: typing.Mapping[str, str]) -> pathlib.Path:
    """The ``sandbox/`` directory of the local fixture directory."""
    override = environ.get("POSTNORD_FIXTURES_DIR")
    root = (
        pathlib.Path(override).expanduser()
        if override
        else harness.state_root(environ) / "karrio-postnord" / "fixtures"
    )
    return root / "sandbox"


def build(
    state_root: pathlib.Path,
    out: pathlib.Path,
    printout_out: pathlib.Path,
    environ: typing.Mapping[str, str],
) -> typing.List[pathlib.Path]:
    """Write the responses and the manifest into ``out`` and the printouts
    into ``printout_out``; return the paths."""
    rules = redaction_rules(environ)
    captures = state_root / CAPTURE_DIR_NAME
    out.mkdir(parents=True, exist_ok=True)
    printout_out.mkdir(parents=True, exist_ok=True)
    entries: typing.List[Json] = []
    written: typing.List[pathlib.Path] = []
    for spec in CATALOG:
        source = captures / spec.run / spec.capture
        raw = source.read_bytes()
        if spec.kind == "printout":
            check_printout(raw, source)
        else:
            check_response(raw, source)
        content = raw if spec.kind == "printout" else redact(raw, rules)
        fixture = (printout_out if spec.kind == "printout" else out) / spec.fixture
        fixture.write_bytes(content)
        written.append(fixture)
        entries.append(manifest_entry(spec, raw, content))
    manifest = dict(
        generator="sandbox_tests/postnord/evidence.py",
        probe_note=PROBE_NOTE,
        capture_root=(
            "karrio-postnord/sandbox/ below the XDG state root "
            "(outside the repository)"
        ),
        redaction_policy=(
            "copies of the captured evidence-of-record files, byte-identical "
            "except that the customer number and the application id, kept "
            "only in .env, are replaced by the placeholders 20000000 and 7351 "
            "(those fixtures record no source digest; the captures' digests "
            "were withdrawn on 2026-10-20); printIds, bookingIds, item ids, "
            "and the dummy EORI SE5561234711 are artifact values that stand; "
            "the 32-character apikey traveled as a query parameter already "
            "stripped at capture time — the build fails on any 32-character "
            "alphanumeric run the harness redactor's exemptions do not "
            "explain, and a PDF's trailer /ID document instance ids are the "
            "one binary exception"
        ),
        fixtures=entries,
    )
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n"
    )
    written.append(manifest_path)
    return written


@dataclasses.dataclass(frozen=True)
class Arguments:
    state_root: pathlib.Path
    out: pathlib.Path
    printout_out: pathlib.Path


def parse_arguments(argv: typing.Sequence[str], environ: typing.Mapping[str, str]) -> Arguments:
    parser = argparse.ArgumentParser(
        description="Build the committed sandbox evidence fixtures from the captures."
    )
    parser.add_argument(
        "--state-root", type=pathlib.Path, default=harness.state_root(environ),
        help="directory whose karrio-postnord/sandbox/ holds the run captures "
        "(default: $XDG_STATE_HOME or ~/.local/state)",
    )
    parser.add_argument(
        "--out", type=pathlib.Path, default=DEFAULT_OUT,
        help=f"fixture directory (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--printout-out", type=pathlib.Path, default=local_printout_dir(environ),
        help="printout directory, outside the repository (default: "
        "$POSTNORD_FIXTURES_DIR/sandbox or "
        "$XDG_STATE_HOME/karrio-postnord/fixtures/sandbox)",
    )
    parsed = parser.parse_args(argv)
    return Arguments(
        parsed.state_root.expanduser(), parsed.out, parsed.printout_out.expanduser()
    )


def main(argv: typing.Sequence[str]) -> None:
    arguments = parse_arguments(argv, os.environ)
    for path in build(
        arguments.state_root, arguments.out, arguments.printout_out, os.environ
    ):
        print(path)


if __name__ == "__main__":
    main(sys.argv[1:])
