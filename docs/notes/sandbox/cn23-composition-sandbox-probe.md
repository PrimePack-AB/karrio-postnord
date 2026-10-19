---
title: "PostNord CN23 composition sandbox probes"
created: 2026-10-19
---

# PostNord CN23 composition sandbox probes

*Grounding the 91/CN23 composed-label and customs-gate questions in test-mode truth: what PostNord accepts without an applicationId, and what it composes when it accepts.*
*Repo-origin note, not ported from the fork: created 2026-10-19, evidencing the env-gated sandbox probe harness (commit b999082) and its printId fixes (33d085f, f815271). Captures live under `$XDG_STATE_HOME/karrio-postnord/sandbox/` — `~/.local/state/karrio-postnord/sandbox/` at the default root — and are cited by run directory, file name, and sha256 only. Credentials are referenced by environment variable name only; no apikey, customer number, EORI, or application id value appears in this note.*

## Method

The probes ran through the repository's env-gated harness (`sandbox_tests/`, commit b999082): no segment fires unless `POSTNORD_SANDBOX=1` is set alongside the sandbox credentials (`POSTNORD_APIKEY`, `POSTNORD_CUSTOMER_NUMBER`, `POSTNORD_EORI`), a live key in scope is a hard stop, and every call is refused unless it targets `https://atapi2.postnord.com/` with `testIndicator` true on the booking body.
Each segment fires once, ever: the marker directory under the state root records what ran, a rejected response is itself the evidence, and no flag exists to force a re-fire.
Each gated run draws on a booking-attempt budget (`POSTNORD_SANDBOX_MAX_BOOKINGS`, default four) reserved before the call.
Two rounds ran on 2026-10-19: 12:03–12:04 UTC (P1, P2, P3) and 14:10 UTC (P5, then P4).
P1 and P2 drove the connector's own mapper end to end; P3, P4, and P5 posted raw bodies past the connector's fail-fast guards so PostNord's own answers are observable.

## Captures

All paths are relative to `~/.local/state/karrio-postnord/sandbox/`; each file is identified by its sha256.

| Run | File | sha256 |
|---|---|---|
| 20261019T120300Z | `001-p1_cn23_gateway.printout01.pdf` | `0b5e7ae9ad4ad90c52554c824ca5a6bb14bc78d64ac31314e4a586b625e65e66` |
| 20261019T120300Z | `001-p1_cn23_gateway.request.json` | `redacted-2026-10-20` |
| 20261019T120300Z | `001-p1_cn23_gateway.response.parsed.json` | `7cb296174b6460f6feac5d6ea77922bfa1e2e05887dddbf32cbdea92553b9489` |
| 20261019T120356Z | `001-p2_invoice_gateway.request.json` | `redacted-2026-10-20` |
| 20261019T120356Z | `001-p2_invoice_gateway.response.parsed.json` | `433a1b35205e568e1987fab9f75193e33b807e7c0d55b4f1a9ed8b144e60537a` |
| 20261019T120422Z | `001-p3_no_customs_raw-18.request.json` | `redacted-2026-10-20` |
| 20261019T120422Z | `001-p3_no_customs_raw-18.response.parsed.json` | `20c60389eca778565cb80ebd0e89820373ef52aa7762d8fd0530be64db86d6b6` |
| 20261019T120422Z | `003-p3_no_customs_raw-91.request.json` | `redacted-2026-10-20` |
| 20261019T120422Z | `003-p3_no_customs_raw-91.response.parsed.json` | `28ddc3fb95c70d203fc4479d2a6cf42ead3739917142648ab6f53c1f14f225c2` |
| 20261019T121021Z | `001-p5_no_customs_with_application_raw.printout01.pdf` | `04ecd390123e80b5cda907a91317bc708f74a489fd28d2223074196d3fedc6dd` |
| 20261019T121021Z | `001-p5_no_customs_with_application_raw.request.json` | `redacted-2026-10-20` |
| 20261019T121021Z | `001-p5_no_customs_with_application_raw.response.parsed.json` | `32dcd1c61e5330274f4c9f73fea39cdf73a68aacdefdecdf28a7decc4a5be288` |
| 20261019T121054Z | `001-p4_byid_fetch_raw.request.json` | `5d5a33eb71d416e678cd07a57cdeb63add8451091c7b0afa5ffe3b07a07b879d` |
| 20261019T121054Z | `001-p4_byid_fetch_raw.response.parsed.json` | `fc77f529fbd2ee1aaa12b6014abd3fbfb034adaa2727c656461fb3600ed86155` |

Each run directory also holds a distilled `NNN-<segment>.result.json` and a `bookings.jsonl` ledger entry per booking attempt; the files above are the evidence of record.

## P1 — International Parcel CN23 through the connector (12:03)

A gateway-driven `postnord_postpaket_utrikes` (basic service 91) booking from Stockholm, SE to Tirana, AL, one 1.0 kg parcel, with the mapper-built `customsDeclarationCN23` (zero `postalCharges` in the `totalValue` currency, EORI threaded from the environment).
PostNord accepted it: `bookingId` `ILPN0010LBQRBGFFMCWLWZDUNDFQVS`, item id and tracking number `CC613724769SE`, and a printId allocated alongside the item id.
The `printoutComposition` was `{cn23: 1, label: 1}`, and the single printout is one two-page A4 PDF: page 1 the "International Parcel" label (`Item-ID`), page 2 the CN23 — the "Customs Declaration" heading, "Office of origin", the sender's certification box, and the "May be opened" inspection strip all present in the extracted text.
Two `SAO-HR-25060301` faults came back under `handlingResponse`: the consignee `phoneNo` and `smsNo` were removed as invalidly formatted for E.164 (original to `REMOVED`), a sanitization rather than a rejection.
The karrio parse returned tracking number `CC613724769SE`, meta `printout_composition` `[cn23, label]`, and empty `extra_documents` — the standalone customs documents opt-in was deliberately left off.
This is the headline: the fork's CN23 booking shape is sandbox-accepted with captured evidence for the first time — the zero-`postalCharges` acceptance claim in `_customs_declaration_cn23`'s docstring (fork commit 875debc8e, carried here by the extraction) now has a capture — and PostNord composes `{label: 1, cn23: 1}` for it in test mode.
That PDF is the first CN23-composed capture anywhere in this project or the fork, and it is the candidate source for deriving CN23 stamping seeds.

## P2 — customs-invoice parcel rejected (12:03:56)

A gateway-driven `postnord_parcel` (basic service 18) booking on the same SE-to-AL lane with a commercial `customsInvoice`.
PostNord rejected it with HTTP 400, `SAI-BR-24111201`: "Unable to allocate id for this basicServiceCode: 18, from country: SE, to country: AL" (the recorded explanation continues with the sandbox customer number, elided here).
Exactly one call was captured: the connector's by-id customs follow-up correctly did not fire on a rejected booking.

## P3 — no-customs raw bookings (12:04:22)

Minimal raw `ediInstruction` bodies — parties and goods item only, no customs object and no application object — posted straight to `/rest/shipment/v3/edi/labels/pdf`, one sub-case per basic service code.
Service 18 was rejected with HTTP 400 `SAI-BR-24111201`, the same allocation fault as P2: id allocation precedes customs consideration, so 18-to-AL cannot answer the no-customs question at all.
Service 91 was rejected with HTTP 400 `SACUS-BR-24100901`, "ApplicationId is invalid, should be 4 digit integer" — a customs-subsystem fault, not an allocation fault.
The comparison against P1 is the finding: P1's request carried a top-level `application` object with only a `name` (no `applicationId`) plus the inline CN23, and passed the customs subsystem; P3-91 carried neither and was rejected.
So inline customs satisfies the 91 customs gate with no `applicationId` anywhere, while a 91 booking with neither inline customs nor application linkage is rejected with the oblique `applicationId` demand.

## P5 — application-linked no-customs 91 accepted (14:10:21)

This segment was added after the first round (commit ccced54) to answer P3-91's rejection: it resends the P3-91 body unchanged plus the top-level `application` object carrying the configured four-digit application id (`POSTNORD_LIVE_APPLICATION_ID`, falling back to `POSTNORD_APPLICATION_ID`; the value is not recorded here).
PostNord accepted it: HTTP 200, no faults, `bookingId` `ILPN0010LBQQAZFHQPNVKBOBIGPFDM`, item id `CC613724786SE`, printId `49b588e17ba543f38d1565da2be73418`, and the same two `SAO-HR-25060301` phone/sms sanitizations as P1.
The `printoutComposition` was `{label: 1, cn23: 0}` — a one-page label-only PDF, no customs document — consistent with the declaration living externally under the application linkage.
This capture was written after the printId-retention fix (33d085f) and is the first to carry a real printId through the redactor, which is what confirmed the fix live.
The external-declaration path is therefore probed and open: application linkage alone satisfies the 91 customs gate, and PostNord composes no customs document for such a booking.

## P4 — by-id only-customs fetch (14:10:56, degraded)

The segment's design reads the latest P1 capture from the state directory — never re-booking — and, when it allocated a printId, posts `/rest/shipment/v3/labels/ids/pdf?definePrintout=onlyCustomsDeclarations` with that single id, raw and one shot.
The first round could not run it: the redactor's 32-character apikey heuristic had masked P1's printId in the parsed capture, and the ledger had no printId field, so the fetch had nothing real to key on (fixed by 33d085f, which whitelists the artifact-id keys and records printIds in the ledger).
The 14:10 run nevertheless fired, keyed on the literal `<redacted>` sentinel the pre-fix P1 capture still holds — `find_print_id` then accepted any truthy string — and PostNord answered HTTP 200 with per-id `FAIL`, "id not found".
That outcome matches the prior expectation from the fork's test-mode evidence (`docs/notes/sandbox/customs-declaration-live-verification.md`: by-id fetches return per-id FAIL "id not found" / "Unable to find EDI"), but as evidence it is degraded: the id queried was never a real printId, so the run shows only that a garbage id is not found.
`find_print_id` now refuses the sentinel (f815271), and both the P1 and P4 markers have fired, so a cleanly keyed by-id probe would require a fresh CN23 booking under a new segment.

## Scope limits

Everything here is test mode: `testIndicator` true means no EDI is sent downstream, so production composition may still differ, and the by-id and declaration endpoints' test-mode unreachability stands (P4's degraded run notwithstanding; the fork note above remains the reference).
SE-to-AL on service 18 fails id allocation outright (`SAI-BR-24111201`), so the invoice branch could not be exercised on this lane; the 2026-09-25 SE-to-NO capture remains the invoice-branch evidence (`docs/notes/sandbox/customs-invoice-live-verification.md`).
P1's PDF establishes what test mode composes for a CN23 booking, but the stamping seeds and the SDK customs classifier still verify CN22 only; deriving CN23 seeds from this capture remains open.
No committed evidence fixture derives from these captures yet, so published documentation pages outside `docs/notes/` make no claim on them — whether to commit redacted fixtures is an open decision.
