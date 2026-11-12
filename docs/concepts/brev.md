---
title: "PostNord Brev (Port Payé)"
---

`postnord_brev` is this package's second carrier: domestic Swedish First Class letters (1:a-klassbrev inrikes) sent under the sender's port payé agreement, rated and labelled entirely by the connector.
No PostNord API is contacted anywhere in the flow — nothing is booked, no identifier is allocated by PostNord, and the letters flow through PostNord's port payé invoicing and inlämning channels like any agreement customer's mail.
The connector composes and returns the complete shipping label, and the marking obligations it encodes come from the Särskilda villkor för 1:a-klassbrev inrikes (gäller fr o m 2025-01-01), which also state that PostNord is not obliged to forward items lacking the required marking — the posture behind the fail-closed guards below.

## No API, by design

Label generation is local, by design, for the same reasons the postnord carrier's [rating](rating.md) makes no carrier call: the flow works with no API key or product authorization, has no PostNord-side failure mode, and never sends shipment data anywhere.
There is no host to point at; the connection's `test_mode` flag exists as a generic karrio setting but selects nothing.
What an API would otherwise validate — the lane, the letter format, the marking — is enforced by the guards below before any label is rendered.

## Connection settings

| Setting | Required | Description |
| --------- | ---------- | ------------- |
| `customer_number` | yes | Port payé agreement customer number, printed as Kundnummer on every label (see below). |
| `franking_asset` | yes | The port payé franking mark (kliché) as base64 SVG or PNG — a bare base64 string or a full `data:` URI — inlined into the label. |

Both settings are enforced at purchase: a shipment whose kundnummer cannot be resolved, or whose connection carries no franking asset, fails with a field error before any label is rendered.
An asset that decodes to neither SVG nor PNG fails the same way, naming the two accepted formats and where to obtain the mark.

The intended source of the franking asset is PostNord's label-blocks page, `postnord.se/foretag/forberedelser/klicheer` (English mirror: `postnord.se/en/business/preparations/label-blocks/`, both accessed 2026-11-10), which publishes the First Class Mail block as EPS and PDF for agreement customers.
The agreement customer downloading the official asset is the intended user of this setting: PostNord publishes no redistribution licence for the artwork, so the connector never ships it and expects each connection to supply its own.

## Submitting the franking asset

The connect form is a plain text field — karrio carrier settings carry no per-field help text — so this page is the field's reference.

PostNord publishes the kliché as EPS and PDF while the connector accepts SVG or PNG, so converting the downloaded asset is part of the submission:

1. Download the First Class Mail kliché from the klichéer page: `eps/1a-klassbrev-pp-kliche2.eps` or `pdf/1a-klassbrev-pp-kliche.pdf` under the siteassets path in the citation table.
2. Convert it to SVG or PNG (for example `inkscape 1a-klassbrev-pp-kliche2.eps --export-type=svg`).
3. Base64 the converted file: `base64 -w0 kliche.svg`.
4. Paste the result into the Franking Asset field — a bare base64 string or a full `data:image/svg+xml;base64,…` / `data:image/png;base64,…` URI both work.

A submitted value that decodes to neither SVG nor PNG — the raw EPS or PDF, for example — fails at purchase with a field error naming the accepted formats and the download page.

## Rating and purchase

Rating is static, exactly as for the postnord carrier: one service, `postnord_brev_first_class`, carrying a single Sweden-only zone, so non-SE lanes simply produce no quote — the first, gentlest layer of the domestic gate.
Prices come from the connection's service levels or a server-side rate sheet.
Purchase is the normal two-step karrio flow: fetch rates, then buy with the selected rate.
The returned label is one 100×180 mm SVG document with `label_type` forced to `SVG` by the provider; a request-side PDF, ZPL, or PNG label type is not produced.

## The label

The label document is a single-root, well-formed SVG: a `<style>` element carrying an `@page` rule for 100 mm × 180 mm sits inside the svg root.
Standalone `.svg` consumers therefore get a valid document, and HTML print wrappers pick up the page sizing from the embedded style.
All label text is fixed Swedish (Avsändare, Kundnummer, Vikt, Datum), and the weight prints in grams whatever unit the request declared.
The franking asset is inlined as a base64 data URI, so the label is self-contained and prints offline, and the kundnummer prints under the franking mark.
A shipper contact line prints under the sender block when the shipper has contact data (see below).

## Limits enforced at purchase

Each guard rejects the shipment with a field-keyed error before any rendering, encoding the format envelope of the Särskilda villkor för 1:a-klassbrev inrikes (gäller fr o m 2025-01-01):

- Lane: the shipper and the recipient must both be in Sweden.
- Parcel count: exactly one parcel — a letter is one mailpiece.
- Weight: required, at most 2 kg in total.
- Dimensions: when all three are given, length + width + thickness at most 900 mm; absent is allowed because letters routinely carry no dimensions, and the terms' 140×90 mm minimum format is left unenforced for the same reason.
- Customs: any customs declaration rejects the purchase — a customs-declared Swedish-domestic letter is confused input.

The lane guard is defense-in-depth: the karrio SDK's own origin gate usually catches a non-SE shipper first, because the brev connection's `account_country_code` defaults to `SE`, so end users see the SDK's origin-not-serviced message rather than the carrier's.

Beyond the guards, the label applies no text truncation: over-long sender or recipient lines overflow their areas, and the sender is responsible for fit.

## Kundnummer on the label

The terms require the kundnummer on the invoice basis (the e-fakturaunderlag/transportsedel), not on the item itself, and no public document requires it on the label.
Printing it under the mark is this connector's policy — senders commonly do the same — so a purchase whose kundnummer cannot be resolved fails outright.
Resolution takes the shipment metadata `postnord_port_paye_customer_number`, else the connection's `customer_number`.

## Shipper contact

The shipper's e-mail prints whenever present.
The phone number prints per `postnord_phone_number_policy`, the same option name as the postnord carrier's, set on the connection config and overridable per shipment in `options`: the default `always` prints it, and `omit_when_email_suffices` drops it exactly when an e-mail is present, keeping phone numbers off the label.
Phone digits are normalized by stripping spaces and dashes.
The brev policy knows those two values; anything else — including the postnord carrier's `omit_unless_required` — resolves fail-safe to `always`.
At least one contact is not mandatory: the terms require only a complete sender designation, and this carrier follows that ruling.

## No tracking, by design

The 1:a-klassbrev inrikes product page states "Spårbart: Nej" (`postnord.se/foretag/skicka/brev-och-paket/1a-klassbrev-inrikes`, accessed 2026-11-10), and the carrier claims no tracking.
The reference number reported at purchase — the parcel's `reference_number`, else a locally minted ten-digit numeric id — is a shipment identifier for your records, not a PostNord tracking id.
Pickup, manifest, and cancel are likewise absent: there is nothing with PostNord to book, collect, manifest, or cancel.
