"""Live PostNord sandbox harness: gating, guards, budget, one-shot markers, captures.

Every live probe runs only when ``POSTNORD_SANDBOX=1`` and the sandbox
credentials are set, only against ``https://atapi2.postnord.com/``, and only
with ``testIndicator`` true on every booking body. A live key anywhere in
the environment is a hard stop. Each segment fires once, ever: the marker
directory under the XDG state directory records what ran, and a rejected
response is itself the evidence, so nothing retries and no flag can force a
re-fire. The configuration parsing, guards, budget, markers, and redaction
are pure; the effects (the transport guard, the capture files, and the
gateway) live in ``Session``, built once per process by ``session()``.
"""

import base64
import dataclasses
import datetime
import functools
import hashlib
import json
import os
import pathlib
import re
import sys
import typing
import unittest
import urllib.error
import urllib.parse
import urllib.request

import karrio.core.utils.helpers as helpers
import karrio.lib as lib
import karrio.sdk as karrio

SANDBOX_HOST = "atapi2.postnord.com"
SANDBOX_ORIGIN = f"https://{SANDBOX_HOST}"
# The only path prefix allowed to book: POST /rest/shipment/v3/edi/labels/
# creates shipments (which PostNord exposes no cancel endpoint for). The
# by-id labels fetch re-prints an existing booking and books nothing.
BOOKING_PATH_PREFIX = "/rest/shipment/v3/edi/labels/"
DEFAULT_MAX_BOOKINGS = 4
REDACTED = "<redacted>"
# PostNord apikeys are 32-character alphanumeric tokens; any such run is
# masked wherever it appears, so a rotated or unexpected key cannot survive.
APIKEY_LIKE = re.compile(r"[A-Za-z0-9]{32}")
# Artifact identifiers PostNord allocates are evidence, not credentials:
# the repo's redaction carve-out lets printIds and bookingIds stand in
# captures and notes. Keys carrying them (the API's camelCase and the
# ledger's snake_case forms) skip the apikey heuristic only; the literal
# configured secrets are still masked inside them.
ARTIFACT_ID_KEYS = frozenset(
    {"printid", "print_id", "bookingid", "booking_id"}
)
DOCUMENT_EXTENSIONS = {"PDF": "pdf", "ZPL": "zpl"}


class SandboxConfigError(ValueError):
    """Raised when the sandbox environment is malformed or unsafe."""


@dataclasses.dataclass(frozen=True)
class SandboxConfig:
    enabled: bool
    apikey: typing.Optional[str]
    customer_number: typing.Optional[str]
    eori: typing.Optional[str]
    max_bookings: int
    sandbox_dir: pathlib.Path
    markers_dir: pathlib.Path
    capture_dir: pathlib.Path


def state_root(environ: typing.Mapping[str, str]) -> pathlib.Path:
    """``$XDG_STATE_HOME``, or ``~/.local/state`` when it is unset."""
    state_home = environ.get("XDG_STATE_HOME") or str(
        pathlib.Path(environ.get("HOME") or pathlib.Path.home()) / ".local" / "state"
    )
    return pathlib.Path(state_home)


def load_config(
    environ: typing.Mapping[str, str],
    now: datetime.datetime,
) -> SandboxConfig:
    """Read the sandbox configuration from an environment mapping.

    A live key present at all, or an empty apikey, raise rather than skip:
    both mean the run cannot be trusted to stay in the sandbox. Unknown or
    negative booking budgets also raise, so a typo never widens what a run
    books. No variable selects the host: test mode always resolves the
    connector's atapi2 sandbox origin.
    """
    enabled = environ.get("POSTNORD_SANDBOX") == "1"
    if enabled:
        if "POSTNORD_LIVE_APIKEY" in environ:
            raise SandboxConfigError(
                "POSTNORD_LIVE_APIKEY is present in the environment; "
                "a live key in scope is a hard stop"
            )
        if environ.get("POSTNORD_APIKEY") == "":
            raise SandboxConfigError("POSTNORD_APIKEY is empty")

    raw_budget = environ.get("POSTNORD_SANDBOX_MAX_BOOKINGS") or ""
    try:
        max_bookings = int(raw_budget) if raw_budget.strip() else DEFAULT_MAX_BOOKINGS
    except ValueError:
        raise SandboxConfigError(
            f"POSTNORD_SANDBOX_MAX_BOOKINGS must be an integer, got {raw_budget!r}"
        )
    if max_bookings < 0:
        raise SandboxConfigError("POSTNORD_SANDBOX_MAX_BOOKINGS must not be negative")

    sandbox_dir = state_root(environ) / "karrio-postnord" / "sandbox"
    return SandboxConfig(
        enabled=enabled,
        apikey=environ.get("POSTNORD_APIKEY") or None,
        customer_number=environ.get("POSTNORD_CUSTOMER_NUMBER") or None,
        eori=environ.get("POSTNORD_EORI") or None,
        max_bookings=max_bookings,
        sandbox_dir=sandbox_dir,
        markers_dir=sandbox_dir / "markers",
        capture_dir=sandbox_dir / now.astimezone(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        ),
    )


def check_url(url: str) -> str:
    """Return ``url``, raising unless it targets the sandbox origin.

    The scheme must be https and the host exactly ``atapi2.postnord.com``,
    so the production host ``api2.postnord.com``, plain http, and lookalike
    hosts are all refused.
    """
    parts = urllib.parse.urlsplit(str(url))
    if parts.scheme != "https" or parts.netloc.lower() != SANDBOX_HOST:
        raise SandboxConfigError(
            f"Refusing a sandbox call to {parts.netloc or url!r}; "
            f"only {SANDBOX_ORIGIN} is allowed"
        )
    return url


def booking_path(url: str) -> typing.Optional[str]:
    """The URL's path when it books a shipment, else None."""
    path = urllib.parse.urlsplit(str(url)).path
    return path if path.startswith(BOOKING_PATH_PREFIX) else None


def check_booking_body(url: str, data: typing.Union[bytes, str]) -> None:
    """Refuse a booking body whose ``testIndicator`` is not true.

    Only the booking path creates shipments, so only its bodies carry the
    test flag; the by-id labels fetch re-prints and takes none.
    """
    if booking_path(url) is None:
        return
    try:
        body = json.loads(data)
    except ValueError:
        raise SandboxConfigError(f"Booking body for {booking_path(url)} is not JSON")
    if not isinstance(body, dict) or body.get("testIndicator") is not True:
        raise SandboxConfigError(
            "Refusing a booking body without testIndicator true"
        )


def skip_reason(config: SandboxConfig) -> typing.Optional[str]:
    """Why a segment does not run under ``config``, or None when it runs."""
    if not config.enabled:
        return "POSTNORD_SANDBOX is not 1"
    if not config.apikey:
        return "POSTNORD_APIKEY is not set"
    if not config.customer_number:
        return "POSTNORD_CUSTOMER_NUMBER is not set"
    if not config.eori:
        return "POSTNORD_EORI is not set"
    return None


def strip_query(url: str) -> str:
    """``url`` without its query string, where the apikey credential travels."""
    parts = urllib.parse.urlsplit(str(url))
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def redact(value: typing.Any, secrets: typing.Iterable[typing.Optional[str]]) -> typing.Any:
    """Copy ``value`` with query strings stripped and apikey-like runs masked.

    Values under the artifact-id keys keep their 32-character identifier
    runs: a printId or bookingId is booking evidence the carve-out permits,
    and only the literal configured secrets are masked inside them.
    """

    masked = [secret for secret in secrets if secret]

    def _mask(text: str, mask_keylike: bool = True) -> str:
        for secret in masked:
            text = text.replace(secret, REDACTED)
        return APIKEY_LIKE.sub(REDACTED, text) if mask_keylike else text

    def _walk(item: typing.Any) -> typing.Any:
        if isinstance(item, dict):
            walked = {}
            for key, entry in item.items():
                name = str(key).lower()
                if name in ARTIFACT_ID_KEYS and isinstance(entry, str):
                    walked[key] = _mask(entry, mask_keylike=False)
                elif name == "url" and isinstance(entry, str):
                    walked[key] = _mask(strip_query(entry))
                else:
                    walked[key] = _walk(entry)
            return walked
        if isinstance(item, (list, tuple)):
            return [_walk(entry) for entry in item]
        if isinstance(item, str):
            return _mask(item)
        return item

    return _walk(value)


def decoded_body(value: typing.Any) -> typing.Any:
    """A JSON text body decoded, empty bodies such as ``[]`` included; other values unchanged."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return value


class BookingBudget:
    """Count of booking attempts against a fixed limit.

    An attempt is counted when reserved, before the booking call, so a
    booking whose response is lost still consumes budget.
    """

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.attempts = 0

    def reserve(self) -> bool:
        if self.attempts >= self.limit:
            return False
        self.attempts += 1
        return True


class OneShot:
    """Segment markers: a segment that fired once never fires again.

    The marker is written before the call, so a segment whose response was
    lost or rejected counts as run; the rejection is the evidence and no
    flag exists to force a re-fire.
    """

    def __init__(self, markers_dir: pathlib.Path) -> None:
        self.markers_dir = markers_dir

    def marker_path(self, segment: str) -> pathlib.Path:
        return self.markers_dir / f"{segment}.done"

    def already_fired(self, segment: str) -> bool:
        return self.marker_path(segment).exists()

    def fire(self, segment: str) -> None:
        self.markers_dir.mkdir(parents=True, exist_ok=True)
        self.marker_path(segment).write_text(
            datetime.datetime.now(datetime.timezone.utc).isoformat() + "\n"
        )


@dataclasses.dataclass(frozen=True)
class Document:
    """One printout's raw bytes plus the metadata kept in the parsed capture."""

    index: int
    label_format: str
    data: bytes

    @property
    def extension(self) -> str:
        return DOCUMENT_EXTENSIONS.get(self.label_format.upper(), "bin")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def extract_documents(body: typing.Any) -> typing.List[Document]:
    """The raw printout documents of a booking or by-id response body.

    Both shapes carry base64 (or raw-text ZPL) document bytes: the booking
    response nests them under ``labelPrintout[].printout``, the by-id
    response holds one ``printout`` per list entry.
    """
    entries: typing.List[typing.Any]
    if isinstance(body, dict):
        entries = body.get("labelPrintout") or []
    elif isinstance(body, list):
        entries = body
    else:
        return []

    documents: typing.List[Document] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        printout = entry.get("printout") or {}
        data = printout.get("data")
        if not data:
            continue
        label_format = (printout.get("labelFormat") or "PDF").upper()
        raw = (
            base64.b64decode(data)
            if (printout.get("encoding") or "base64").lower() == "base64"
            else data.encode("utf-8")
        )
        documents.append(
            Document(
                index=len(documents) + 1,
                label_format=label_format,
                data=raw,
            )
        )
    return documents


def with_document_metadata(
    body: typing.Any, documents: typing.List[Document], stem: str
) -> typing.Any:
    """Copy ``body`` with printout data replaced by file and digest metadata."""
    if not documents:
        return body

    def names(document: Document) -> str:
        return f"{stem}.printout{document.index:02d}.{document.extension}"

    omitted = {
        "omitted": "printout data stored as raw bytes alongside",
        "file": names(documents[0]),
        "files": [names(document) for document in documents],
        "sha256": [document.sha256 for document in documents],
    }

    def _walk(item: typing.Any) -> typing.Any:
        if isinstance(item, dict):
            printout = item.get("printout")
            if isinstance(printout, dict) and printout.get("data"):
                return {**item, "printout": {**printout, "data": omitted}}
            return {key: _walk(entry) for key, entry in item.items()}
        if isinstance(item, list):
            return [_walk(entry) for entry in item]
        return item

    return _walk(body)


def find_print_id(parsed: typing.Any) -> typing.Optional[str]:
    """The printId accompanying the first assigned item id, anywhere in ``parsed``.

    Mirrors the connector's ``shipment.create._first_print_id``: the by-id
    labels endpoint resolves printIds, not item ids.
    """
    stack = [parsed]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item.get("idType") == "itemId" and item.get("printId"):
                return str(item["printId"])
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return None


@dataclasses.dataclass(frozen=True)
class SegmentCapture:
    """The latest parsed capture of a segment, and where it came from."""

    run_dir: pathlib.Path
    path: pathlib.Path
    parsed: typing.Any


def latest_segment_capture(
    sandbox_dir: pathlib.Path, segment: str
) -> typing.Optional[SegmentCapture]:
    """The newest ``NNN-<segment>.response.parsed.json`` under ``sandbox_dir``.

    Run directories are UTC timestamps, so their names sort chronologically.
    """
    if not sandbox_dir.is_dir():
        return None
    for run_dir in sorted((p for p in sandbox_dir.iterdir() if p.is_dir()), reverse=True):
        captures = sorted(run_dir.glob(f"*-{segment}.response.parsed.json"))
        if captures:
            path = captures[-1]
            return SegmentCapture(
                run_dir=run_dir,
                path=path,
                parsed=json.loads(path.read_text()),
            )
    return None


class Session:
    """Process-wide sandbox state: config, guards, budget, markers, captures."""

    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self.budget = BookingBudget(config.max_bookings)
        self.oneshot = OneShot(config.markers_dir)
        self.sequence = 0
        self.booking_calls = 0
        if config.enabled:
            self._install_transport_guard()

    def gateway(self):
        """Create a test-mode gateway on the connector's sandbox origin."""
        gateway = karrio.gateway["postnord"].create(
            dict(
                id="sandbox",
                test_mode=True,
                carrier_id="postnord",
                apikey=self.config.apikey,
                customer_number=self.config.customer_number,
                issuer_code="Z12",
                account_country_code="SE",
            )
        )
        if not gateway.settings.test_mode:
            raise SandboxConfigError("The sandbox gateway is not in test mode")
        check_url(gateway.settings.server_url or "")
        return gateway

    def _install_transport_guard(self) -> None:
        """Refuse any carrier call off the sandbox origin, past the budget, or unflagged.

        The SDK's ``request`` opens connections through the module-level
        ``helpers.urlopen``, so wrapping it covers every proxy call.
        """
        original = helpers.urlopen

        def guarded_urlopen(request, *args, **kwargs):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            check_url(url)
            if booking_path(url) is not None:
                self.booking_calls += 1
                if self.booking_calls > self.budget.attempts:
                    raise SandboxConfigError(
                        "Refusing a booking call without a reserved budget attempt"
                    )
                check_booking_body(url, request.data)
            return original(request, *args, **kwargs)

        setattr(helpers, "urlopen", guarded_urlopen)

    def raw_post(
        self,
        path: str,
        body: typing.Any,
        params: typing.Optional[typing.Mapping[str, str]] = None,
    ) -> typing.Tuple[int, str]:
        """POST ``body`` as JSON to the sandbox ``path`` with the apikey query.

        Deliberately bypasses the connector's mapper and proxy: the raw
        segments observe what PostNord itself answers, without the
        connector's fail-fast guards in the way. The host and, on the
        booking path, the ``testIndicator`` flag are asserted before the
        request is sent; an HTTP error is returned, not raised, because a
        rejection is the evidence.
        """
        query = dict(apikey=self.config.apikey, **(params or {}))
        url = f"{SANDBOX_ORIGIN}{path}?{urllib.parse.urlencode(query)}"
        check_url(url)
        check_booking_body(url, json.dumps(body))
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()

    @functools.cached_property
    def capture_dir(self) -> pathlib.Path:
        self.config.capture_dir.mkdir(parents=True, exist_ok=True)
        print(f"sandbox captures: {self.config.capture_dir}", file=sys.stderr)
        return self.config.capture_dir

    def _secrets(self) -> typing.Tuple[typing.Optional[str], ...]:
        return (self.config.apikey,)

    def _write_json(self, name: str, value: typing.Any) -> None:
        safe = redact(value, self._secrets())
        (self.capture_dir / name).write_text(
            json.dumps(safe, ensure_ascii=False, indent=1, default=str) + "\n"
        )

    def next_stem(self, label: str) -> str:
        self.sequence += 1
        return f"{self.sequence:03d}-{label}"

    def write_request(
        self, stem: str, url: str, body: typing.Any, note: typing.Optional[str] = None
    ) -> None:
        """Write a call's request: the query-stripped URL and the parsed body."""
        self._write_json(
            f"{stem}.request.json",
            dict(
                url=strip_query(url),
                **({"note": note} if note else {}),
                data=decoded_body(body) if isinstance(body, str) else body,
            ),
        )

    def write_response(
        self,
        stem: str,
        text: typing.Any,
        transport: str = "response",
        http_status: typing.Optional[int] = None,
    ) -> typing.Any:
        """Write a call's parsed response, printout bytes stored alongside.

        Label and customs document data never lands base64-inline in the
        JSON: each printout becomes a ``NNN-<label>.printoutNN.<ext>`` file
        next to it, referenced by name and sha256.
        """
        body = decoded_body(text)
        documents = extract_documents(body)
        for document in documents:
            (self.capture_dir / f"{stem}.printout{document.index:02d}.{document.extension}").write_bytes(
                document.data
            )
        self._write_json(
            f"{stem}.response.parsed.json",
            dict(
                transport=transport,
                **({"http_status": http_status} if http_status is not None else {}),
                body=with_document_metadata(body, documents, stem),
            ),
        )
        return body

    def write_result(self, label: str, result: typing.Any) -> None:
        """Write a segment's probe result (karrio parse, probe summary)."""
        self._write_json(f"{self.next_stem(label)}.result.json", result)

    def drain_calls(self, gateway) -> typing.List[typing.Dict[str, typing.Any]]:
        """The gateway's traced calls since the last drain, paired by request id."""
        records = sorted(gateway.tracer.drain_records(), key=lambda r: r.timestamp)
        calls: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
        for record in records:
            data = dict(lib.to_dict(record.data) or {})
            for field in ("data", "response", "error"):
                if field in data:
                    data[field] = decoded_body(data[field])
            calls.setdefault(data.get("request_id") or str(record.timestamp), {})[
                record.key
            ] = data

        return [
            dict(
                url=call["request"].get("url"),
                data=call["request"].get("data"),
                **(
                    {"transport": "error", "text": call["error"].get("error")}
                    if "error" in call
                    else {"transport": "response", "text": call["response"].get("response")}
                ),
            )
            for call in calls.values()
            if "request" in call
        ]

    def capture_gateway_calls(self, gateway, label: str) -> typing.List[typing.Any]:
        """Capture the gateway's traced calls since the last capture, redacted."""
        bodies: typing.List[typing.Any] = []
        for call in self.drain_calls(gateway):
            stem = self.next_stem(label)
            self.write_request(stem, call["url"], call["data"])
            bodies.append(self.write_response(stem, call["text"], call["transport"]))
        return bodies

    def log_booking(
        self,
        segment: str,
        test: str,
        tracking_number: typing.Optional[str] = None,
        booking_id: typing.Optional[str] = None,
        print_id: typing.Optional[str] = None,
    ) -> None:
        """Append the segment's ledger entry, printId included when allocated.

        The by-id endpoints resolve printIds, so the ledger is where a
        booking's printId must survive even when no segment reads it back.
        """
        entry = dict(
            segment=segment,
            test=test,
            tracking_number=tracking_number,
            booking_id=booking_id,
            print_id=print_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        with (self.capture_dir / "bookings.jsonl").open("a") as log:
            log.write(json.dumps(redact(entry, self._secrets())) + "\n")


def _require(config: SandboxConfig, segment: str) -> None:
    reason = skip_reason(config)
    if reason:
        raise unittest.SkipTest(f"segment {segment} skipped: {reason}")


def require_booking(test: unittest.TestCase, session: Session) -> None:
    """Skip unless a booking attempt remains, reserving one before the call."""
    if not session.budget.reserve():
        test.skipTest(
            f"booking budget exhausted "
            f"(POSTNORD_SANDBOX_MAX_BOOKINGS={session.budget.limit})"
        )


def require_fire(test: unittest.TestCase, session: Session, marker: str) -> None:
    """Skip when the marker fired once; else write it before the call fires."""
    if session.oneshot.already_fired(marker):
        test.skipTest(
            f"segment {marker} already ran once "
            f"({session.oneshot.marker_path(marker)}); a rejected response is the "
            "evidence, so it never re-fires"
        )
    session.oneshot.fire(marker)


@functools.cache
def config() -> SandboxConfig:
    return load_config(os.environ, datetime.datetime.now())


@functools.cache
def session() -> Session:
    return Session(config())


def require_segment(segment: str) -> Session:
    """Skip the calling test class unless the sandbox runs; else the session."""
    _require(config(), segment)
    return session()
