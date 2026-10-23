---
title: "Labels"
---

The resolved `label_type` — the shipment request's value, else the connection config — selects the booking endpoint: `/rest/shipment/v3/edi/labels/pdf` or `/rest/shipment/v3/edi/labels/zpl`.
Both return the printout inline in `labelPrintout[].printout`, and the connector returns it as `docs.label`.

## Formats

Both formats are first-class.
PDF suits paper workflows; ZPL suits thermal printers and is the format the connector's composed-label verification was built around, so ZPL is the recommended format where a thermal printer is available.
The connection config `label_size` (`standard` 190×105 mm, `small` 75×105 mm, or `ste`) is sent as the `labelType` query parameter; unset omits it and PostNord defaults to `standard`.

## ZPL transport encoding

The booking specification documents `printout.encoding` as base64 only, but the ZPL endpoint returns raw UTF-8 ZPL text with `encoding: "none"` — a recorded spec gap (see [docs/notes/sandbox/zpl-label-encoding.md](../notes/sandbox/zpl-label-encoding.md)).
The connector normalizes per printout: base64 passes through, anything else is treated as raw UTF-8 and base64-encoded, so `docs.label` is always base64 and karrio's label pipeline (`bundle_zpls`, document serving) receives a uniform input.
A missing `labelFormat` falls back to the requested label type.
The ZPL body starts with persistent host commands — `^LL1520` (190 mm at 8 dots/mm) and `^CI28` (UTF-8) — followed by `^CW` font aliases, all preserved verbatim.

## Composed printouts

For bookings with customs data, PostNord composes the customs document into the booking printout itself: one PDF or one ZPL carrying both the declaration section and the label section.
`docs.label` is that composed printout, returned unchanged, and `meta.printout_composition` lists the kinds PostNord declares, for example `["cn22", "label"]`.
For International Parcel (91), the committed test-mode capture shows the composition `{cn23: 1, label: 1}` as one two-page A4 PDF — the parcel label on page 1, the CN23 on page 2 ([response](../../tests/postnord/fixtures/sandbox/p1-cn23-gateway.response.json), [printout record](../../tests/postnord/fixtures/sandbox/manifest.json); the printout itself is not distributed); test mode sends no EDI downstream, so production composition may differ.

The connector verifies the composed label with the SDK customs classifier using PostNord's declared section markers (`DOCUMENT_SECTIONS` in `karrio/providers/postnord/stamping.py`).
A label that does not classify as the shipping label composed with the branch's declaration is still returned unchanged, with a `postnord_unexpected_label_composition` warning naming the expected and the classified composition; the booking never fails on it.
CN22 labels are verified in both formats.
CN23 labels (International Parcel 91) are verified on PDF against the CN23 page-text markers seeded from that capture, read from the classifier's matched kinds because its composition vocabulary is closed to the CN22; a ZPL label skips the check, which predates the ZPL CN23 section marker. The CN23 signature-strip seed covers both formats; its ZPL geometry and the ZPL marker `^FX CN23_CUSTOMS_DECLARATION^FS` are measured on a locally held ZPL printout listed in [docs/development/index.md](../development/index.md).
Customs-invoice labels declare no section markers in any format and are never content-verified, and bookings without customs data or within the EU VAT area are not verified.
The classifier anchors accept the template variance PostNord's printouts show — the letter CN22 rotated beside the label versus the parcel services' separate upright CN22 format — and the working capture record is [docs/notes/sandbox/booking-printout-composition-verification.md](../notes/sandbox/booking-printout-composition-verification.md).

Every customs-declared booking additionally attests the server-declared `meta.printout_composition` against the kinds its customs branch composes — `{label, cn22}` for letters, `{label, cn23}` for International Parcel (91), `{label, customsInvoice}` for parcel products.
A disagreement warns with `postnord_printout_composition_mismatch`, an absent declaration stays silent, and neither ever fails the booking; the pre-CN23 91 captures, which compose a CN22, therefore warn by design when replayed.

## Standalone customs documents

For parcel-product bookings with customs data, the connector also fetches the standalone customs document (`POST /rest/shipment/v3/labels/ids/{pdf,zpl}` with `definePrintout=onlyCustomsDeclarations`, keyed by the booking's `printId`, in the label's format) and attaches it to `docs.extra_documents`.
Because the invoice is also composed into the label printout, the standalone document duplicates it; the composition metadata lets a consumer decide which to keep.

For letter services and International Parcel (91), no standalone document is fetched unless the `postnord_standalone_customs_documents` opt-in is set (per shipment in `options`, else the connection config); with the opt-in, the standalone declaration — CN22 for letters, CN23 for 91 — is attached in addition to the label, identically for PDF and ZPL.
A failed fetch never fails the booking; it surfaces as a message.

## Entry code

The `entry_code` shipment option carries a recipient building's door code.
It is sent as a shipment `freeText` with usage code `ZDC`; PostNord prints it as "Ref 2" on the label and maps it to the consignee reference.
A value longer than 50 characters rejects the booking with an `ENTRY_CODE_LENGTH` message before any call to PostNord.
PostNord does not document which services accept it — the value is passed through unverified and ignored by services without door-code support.
