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

## Self-franking, not Frankeringsservice

PostNord's Frankeringsservice is the subscription lane: an abonnemang billed monthly in advance, ordered in Företagsportalen as an agreement customer, under which franking is delegated to PostNord — the sender marks each envelope with PostNord's barcode (Frankeringsservice streckkod A, which PostNord derives from the kundnummer) and a Swedish sender matching the payment-responsible party, and PostNord then prices every item by weight and destination country, covering both 1:a-klassbrev inrikes and utrikes (`postnord.se/foretag/foretagslosningar/posttjanster/frankeringsservice/`, accessed 2026-11-19).
This carrier serves the other lane: the sender who keeps franking in-house under the port payé agreement and pays postage against invoice through the e-fakturaunderlag, with no abonnemang, no PostNord-issued barcode, and no API.
What that lane requires of the sender is the marking set the Särskilda villkor för 1:a-klassbrev inrikes (§1.3) makes mandatory — recipient name and address, one clear and complete Swedish sender designation (the payment-responsible party), and the franking designation per the kliché from postnord.se — which is exactly what this label produces and the guards enforce, so declining Frankeringsservice adds no marking obligation on this carrier's mail.
One scope difference: Frankeringsservice covers utrikes letters as well, while this carrier is domestic Sweden only.

## Submitting the letters: the ELIN fakturaunderlag

The connector's part ends at the label: nothing in the flow reports the letters to PostNord, so the sender carries a manual submission duty on every mailing.
The terms state it as §2.2 (Fakturaunderlag och Transportsedel): before every inlämning a completed electronic fakturaunderlag must always be sent to PostNord, and a transportsedel must accompany the letters at the inlämning (Särskilda villkor för Brev Utrikes, ej spårbart (1:a-klassbrev), gäller fr o m 2026-05-04, §2.2 — the held first-party copy, whose §-references are verified against it; the ELIN page states the same rule for letter submissions generally).
The underlag is made in ELIN, PostNord's Elektroniska fakturaunderlag tool (`postnord.se/vara-verktyg/elektroniska-fakturaunderlag/`, accessed 2026-11-19): the sender logs into the PostNord Portal — agreement customers register interest and receive portal access, account type Business — and creates the fakturaunderlag from saved templates and submits it digitally.
The transportsedel is generated automatically; print it and send it along with the letters at inlämning, to the staff at the service location or to the driver at pickup.
The tool is free for agreement customers holding a credit agreement on letter services (kreditavtal på brevtjänster), and physical fakturaunderlag were discontinued on 1 January 2022, so ELIN is the only form the underlag takes.
The terms also bill defensively: when a submitted item's design or information does not match the completed fakturaunderlag, PostNord may charge per the price list for the service the item actually meets the conditions for (§5.2), so the underlag should be made to match what is submitted.
One number-format quirk the ELIN FAQ flags: the tool expects an 8-digit kundnummer and offers a conversion function under its saved-details settings when yours has nine digits.

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
Consumers that store the asset ahead of booking can refuse it when it is configured: `karrio.providers.postnord_brev.label.check_franking_asset(decoded_bytes)` raises `ValueError` unless the PDF conversion can draw it (a PNG Pillow decodes, or an SVG svglib parses into a drawing of positive size).

## Rating and purchase

Rating is static, exactly as for the postnord carrier: one service, `postnord_brev_first_class`, carrying a single Sweden-only zone, so non-SE lanes simply produce no quote — the first, gentlest layer of the domestic gate.
Prices come from the connection's service levels or a server-side rate sheet.
Purchase is the normal two-step karrio flow: fetch rates, then buy with the selected rate.
The returned label honours the request's `label_type`: `PDF` (the default) receives a converted one-page 100×180 mm PDF, `SVG` receives the raw SVG document, and any other requested type fails with a field error naming the two.

## The label

The label is rendered once as a single-root, well-formed SVG: a `<style>` element carrying an `@page` rule for 100 mm × 180 mm sits inside the svg root.
Standalone `.svg` consumers therefore get a valid document, and HTML print wrappers pick up the page sizing from the embedded style.
For the default PDF output the SVG converts through svglib/reportlab — pure Python, so no system cairo or fonts are involved — with the franking asset re-drawn into its slot as native vector (SVG asset) or raster (PNG asset) geometry, because svglib cannot load data-URI images; the slot rect and aspect rule come from the template itself, so the template stays the single source of the label geometry.
A PNG asset is drawn as an inline image, which carries no alpha channel, so transparent pixels are flattened onto white and 16-bit grey is scaled to 8 bits; a PNG that does not decode fails the conversion rather than leaving the slot empty.
All label text is fixed Swedish (Avsändare, Kundnummer, Vikt, Datum), and the weight prints in grams whatever unit the request declared.
The franking asset is inlined as a base64 data URI in the SVG form, so that document is self-contained and prints offline, and the kundnummer prints under the franking mark.
A shipper contact line prints under the sender block when the shipper has an e-mail or phone number (see below).

One platform caveat: karrio servers store `label_type` through a fixed PDF/ZPL/PNG choice set, so an `SVG` label requested through a server deployment is persisted as PDF bytes mismatch — request the default PDF there; explicit SVG labels are for direct SDK consumers, whose persistence has no such gate.

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

The shipper's e-mail prints whenever present, and its phone number prints only when it has no e-mail (phone digits normalized by stripping spaces and dashes); the recipient's e-mail and phone number never print.
This follows the product-owner ruling of 2026-11-20 and holds whatever `postnord_phone_number_policy` says: brev connections still accept that option for parity with the postnord carrier, but no brev request is sent anywhere, so it has no effect on this carrier.
The line is fitted to the sender column so it always ends before the Kundnummer column: it shrinks from 2.24 mm down to 1.8 mm, measured in Helvetica (the face the PDF is drawn in), and a contact still too long at 1.8 mm is cut with an ellipsis.
At least one contact is not mandatory: the terms require only a complete sender designation, and this carrier follows that ruling.

## Engine line and tagline

The engine line — the small bold line at the label's top right — is configurable through `postnord_brev_stamp_pattern`, set on the connection config and overridable per shipment in `options`.
The value is jinja2 template syntax rendered against a small fixed context: `shipper.company_name`, `shipper.person_name`, `reference` (the shipment's reference field), `stamp` (the rendering time as YYYYMMDDHHMM), `date` (the ISO date), and `year`.
The default `{{ shipper.company_name }} – {{ stamp }}` prints the sender company — falling back to the person name when the company is unset — beside the rendering time, so `"{{ shipper.company_name }} — {{ reference }}"` reproduces the sender-and-reference form.
The pattern renders in a sandboxed jinja2 environment, and the rendered text is escaped into the SVG like every other label value.
Guards fail closed with a field error naming the option: a pattern over 200 characters, an invalid or unsupported template — `{% include %}` among them, for which jinja2 raises a loader `TypeError` rather than a template error — or a render exceeding 80 characters all reject the purchase.

The vertical right-margin tagline is `postnord_brev_label_tagline`, resolved on the same two layers: set text prints centred on the address-window band, reading top to bottom, at most 60 characters, and unset prints no line at all.

## No tracking, by design

The 1:a-klassbrev inrikes product page states "Spårbart: Nej" (`postnord.se/foretag/skicka/brev-och-paket/1a-klassbrev-inrikes`, accessed 2026-11-10), and the carrier claims no tracking.
The reference number reported at purchase — the parcel's `reference_number`, else a locally minted ten-digit numeric id — is a shipment identifier for your records, not a PostNord tracking id.
Pickup, manifest, and cancel are likewise absent: there is nothing with PostNord to book, collect, manifest, or cancel.
