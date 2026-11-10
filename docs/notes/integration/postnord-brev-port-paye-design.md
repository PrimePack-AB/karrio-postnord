---
title: "PostNord Brev (Port Payé): postnord_brev carrier design"
created: 2026-11-10
---

Design note for the `postnord_brev` carrier, originating in this repository on 2026-11-10.
Status: design settled with the product owner on 2026-11-10, pending the owner's review of this note before implementation planning; the PostNord licensing questions in "Franking asset and licensing" await the kundintegration request (draft in the appendix).

## Product definition

`postnord_brev` is prepaid domestic Swedish letter mail: First Class letters (1:a-klassbrev inrikes) sent under the sender's port payé agreement, paid against invoice, with no PostNord API interaction anywhere in the flow.
The connector composes and returns the complete shipping label; nothing is booked, no identifier is allocated by PostNord, and the letters flow through e-fakturaunderlag (ELIN) and physical inlämning like any port payé mail.

The marking obligations come from the Särskilda villkor for 1:a-klassbrev inrikes (gäller fr o m 2025-01-01), §1.3: recipient name and address; one clear and complete Swedish sender designation (the payment-responsible party); and "portobeteckning enligt kliché som finns att hämta på postnord.se" — PostNord "är inte skyldig att befordra försändelser utan ovan angiven märkning", which is the fail-closed posture this design adopts throughout.
The same terms give the format envelope: max 2 kg, min 140×90 mm, length+width+thickness ≤ 900 mm, envelope or omslag required.

The customer number (kundnummer) has an honest citation boundary: no public document requires it on the item itself — the terms require it on the e-fakturaunderlag/transportsedel (§2.2) — but senders commonly print it under the mark, and the cross-border IBRS instruction on the klichéer page points the same way ("OBS! Glöm inte att ange nummer under etiketten").
Our label prints it under the mark as product policy mandated in session: no kundnummer, no label.
The svarspost inrikes terms (gäller fr o m 2023-05-02) show the domestic customer-number format as eight digits grouped 3-3-2.

Tracking does not exist for this product and the carrier does not claim it: the 1:a-klassbrev inrikes product page states "Spårbart: Nej", and Skicka rätt med PostNord (2026-01-26) assigns barcodes only to tracked letter services.

## Decisions

All settled with the product owner on 2026-11-10:

- Separate carrier plugin (`postnord_brev`), not a service inside the postnord carrier.
- Connector-side label rendering; approach B, self-contained provider (below).
- Franking basis is the port payé agreement; the label carries the First Class kliché plus kundnummer.
- One service in v1: domestic First Class, SE→SE only.
- The label document is SVG only, with `label_type="SVG"` forced by the provider.
- The label text is hard-coded Swedish and the weight renders in grams regardless of input units.
- Kundnummer resolution: shipment metadata override, else the connection's required `customer_number`; unresolvable is a hard failure.
- The franking asset is consumer-supplied in v1 (fail-closed when absent); a connector-drawn mark is parked pending PostNord's answer.
- No tracking, pickup, manifest, or cancel capability.
- Multi-part label panels are deferred: the fixture below is the minimally viable label.

## Architecture

A second carrier in this repository, discovered beside the first through a new pyproject entry point, mirroring the existing plugin layout:

- `karrio/plugins/postnord_brev/` — `METADATA` (slug `postnord_brev`, one `service_levels` entry, `connection_configs` for the franking asset).
- `karrio/mappers/postnord_brev/` — minimal hand-written mapper (settings, proxy); no generated schemas because there is no wire format.
- `karrio/providers/postnord_brev/` — `units.py` (service code `postnord_brev_first_class`, guard tables), `settings.py` (`customer_number` required, `franking_asset` optional base64), `shipment/create.py` (guards, render, details), and rate handling that rides the universal rating mixin exactly as the postnord carrier does.
- `karrio/plugins/postnord_brev/templates/label.svg.j2` — the label template as versioned package data.

Capabilities duck-type from the proxy: rating and shipping only.
Omitting `get_tracking` matters server-side as well as client-side: karrio creates a Tracker at purchase only when the proxy implements tracking, so no dead tracker rows are ever minted for brev shipments.

Approach B (self-contained provider) was chosen over riding the SDK's `ShippingMixinProxy` (approach A) or rendering through `karrio.addons.label` (approach C) because the label is product identity: a template owned and versioned here, fixture-tested for exact output, with guards in the house fail-closed style and no coupling to the mixin's template-context contract.
The SDK facts the approach rests on were verified against the fork checkout at `develop` 92605aa53 (snapshot-2026.11.05.6) on 2026-11-10:

- The upstream `generic` connector is the only no-HTTP shipment precedent and composes `RatingMixinProxy.get_rates` with `ShippingMixinProxy.create_shipment`; its tracking-number minting (parcel `reference_number`, else a uuid-derived integer string) is the scheme this design mirrors.
- The SDK's `LabelType` enum knows PDF, ZPL and PNG only, but a provider-returned `label_type` wins over the request at persistence (`buy_shipment_label` merges response details over the payload), and the fork's admin label-preview tests exercise SVG output through the whole local path — so provider-forced SVG needs no server changes.
- Purchase requires a persisted rate (`require_selected_rate`), but the fetch can be entirely local; the postnord carrier already rates this way, so the seeded ServiceLevel is the existing mechanism.
- Per-service capability gating does not exist in karrio, which is the decisive reason brev is its own carrier.
- jinja2 is not a declared SDK dependency (it reaches the server only transitively), so the connector declares it explicitly in `[project]` dependencies; it is pip-resolvable and adds no fork coupling — the `[tool.primepack] karrio-ref` pin is untouched.

## Data flow

Purchase is the normal two-step karrio flow.

`fetch_rates` is entirely local: the seeded ServiceLevel carries an SE-only zone, so non-SE lanes simply produce no quote — the first, gentlest layer of the domestic gate.
`buy` with the selected rate enters `create_shipment`, which resolves inputs (kundnummer chain; franking asset), enforces the guards below, mints the shipment identifier from the parcel `reference_number` with the uuid fallback (required by `ShipmentDetails` even though nothing tracks it), renders the template, inlines the franking asset as a base64 data URI, and returns `ShipmentDetails` with the SVG label and `label_type="SVG"`.

Two deliberate omissions: `payment.account_number` is not in the kundnummer chain (the brev connection's own required `customer_number` covers it; a third fallback would blur a mandatory field into optional resolution), and customs-declared bookings are rejected rather than silently stripped — a customs-declared SE→SE letter is confused input.

## Guards

Each guard raises `lib.exceptions.FieldError` with a field-keyed message before any rendering, following the pattern of the postnord carrier's build-time checks:

- Lane: shipper and recipient country must both be `SE`.
- Parcel count: exactly one parcel; a letter is one mailpiece.
- Weight: required, total ≤ 2 kg, rendered in grams regardless of input unit.
- Dimensions: when present, length+width+thickness ≤ 900 mm; absent is allowed because letters routinely carry no dimensions.
- Kundnummer: shipment metadata override, else the connection's `customer_number`; unresolvable fails.
- Franking asset: required, base64, sniffed as SVG or PNG by decoded magic prefix; anything else names the two accepted formats and the klichéer download in its message.
- Customs: any customs declaration on the shipment is rejected.

The 140×90 mm minimum is documented as unenforced, for the same absent-dimensions reason.

## Label contract

One 100×180 mm SVG, `viewBox="0 0 100 180"`, `width`/`height` in millimetres authoritative for sizing; the `@page` style block is retained for HTML-print wrappers and is inert inside pure SVG.
All text is hard-coded Swedish (Avsändare, Vikt, Kundnummer, Datum); the engine line and tagline carry the connector's own branding (PrimePack, "Fix your Ship — Shipify AB") hard-coded as in the fixture, and the timestamp is derived from the shipment.

The minimally viable label is the fixture agreed in session — the PART 1 panel of the proven template, everything else deferred:

- Sender block, top left.
- Franking asset inlined as a base64 data URI, top right, `preserveAspectRatio` fit inside the postage slot.
- Kundnummer under the mark.
- Engine line with timestamp, address-window corner marks, vertical tagline.
- Recipient block at 4.23 mm glyphs — comfortably above Skicka rätt's ≥2.4 mm minimum character height for addresses, which must remain "tydlig och störst av alla adresser".
- Vikt in grams and Datum at the panel's foot.

Two geometry notes for implementation: the fixture's postage slot is 32×18 mm while the actual 1:a-klassbrev kliché artboard is 41.2×7.6 mm, so `meet` fitting renders the official asset at ~78% of artboard scale — nothing published mandates a size ("placera väl synligt" is the only instruction), but the slot should be widened toward artboard scale if the deferred panels permit; and the lower ~108 mm of the canvas stays empty, which is consistent with the postoperatörszon requirement (a print-free, light, ≥150×30 mm surface for PostNord's sorting code, bottom-right on C4/C5/E65 and landscape, top-right on standing C4) — recorded as consistent-with rather than claimed intent, since 150 mm exceeds the 100 mm label width and the zone is ultimately an envelope-level property.

Porting the engine template to package data removes the engine-context artifacts: the commented-out recipient-phone block (with its stray `--`) goes, and the bare `metadata`/`customer_number`/`postage_image_url` top-level variables are replaced by the connector's own context (the karrio `shipment`, the resolved kundnummer, the franking asset), since the connector controls the render end to end.
Deferred PARTs 2+ arrive later as template revisions with their own fixture updates.

## Franking asset and licensing

The First Class kliché is PostNord's own artwork: a bar over "PP" plus bold "Sverige, Port Payé", artboard 41.2×7.6 mm, no customer number inside.
PostNord publishes it openly for agreement customers — EPS and PDF per block under `postnord.se/siteassets/images/0.-foretag/forberedelser/klicheer/` (`1a-klassbrev-pp-kliche.pdf`, `1a-klassbrev-pp-kliche2.eps`), linked from the klichéer page (canonical Swedish path `postnord.se/foretag/forberedelser/klicheer`, English mirror `/en/business/preparations/label-blocks/`) — with the stated intent of new printing and reprinting on preprinted Port Payé envelopes, posting rules in the per-service special terms, and in most cases a registered invoice basis.

No redistribution licence is published anywhere, and the designations are protected (the svarspost inrikes terms reserve the words "Porto Betalt", "Porto Payé" and "PP" against confusable third-party marks).
Accordingly: the connector never ships the artwork; the connection supplies it as base64 SVG or PNG (the agreement customer downloading the official asset is the intended user), the repo's cite-don't-commit rule holds, and tests use a synthetic inline SVG.

Two questions go to PostNord customer integration (kundintegration@postnord.com, draft in the appendix): whether a connector-rendered reproduction of the mark satisfies "portobeteckning enligt kliché" (fidelity), and whether embedding the published artwork in integration-generated labels — or redistributing it inside a vendor's software package — is permitted.
Until answered, the consumer-supplied asset is the only path; a self-drawn default marking is the parked enhancement those answers would unlock.

## Testing

Fully offline, shaped like the phone-policy modules:

- A happy-path render against an SE→SE fixture asserting parsed SVG content: viewBox, kundnummer text, gram weight, inline franking-asset data URI, party lines.
- One test per guard asserting the field-keyed `FieldError`.
- Rate tests: the single service appears for SE lanes and nothing for others.
- Identifier minting: `reference_number` preferred, uuid fallback shape.
- A no-HTTP proof (`lib.request` patched, `assert_not_called`) even though the carrier never imports it.
- The test franking asset is a tiny synthetic SVG; real artwork never enters the repository.

Fixtures must use synthetic Swedish addresses — the karrio canonical Moncton/Vancouver fixtures cannot pass the SE→SE guard.

## Documentation and evidence

At implementation: a new concepts page for the brev carrier; a README section; CLAUDE.md code-map and current-state entries; and citation-table additions for the Särskilda villkor 1:a-klassbrev inrikes (2025-01-01), Skicka rätt med PostNord (2026-01-26), both klichéer page paths, and the svarspost inrikes terms (2023-05-02), all accessed 2026-11-10, with local copies destined for `vendor/` per the existing table's conventions.
Claims discipline follows the established rules: the label is our own content (no PostNord-returned printout rules apply), published pages make no sandbox claims because no PostNord host is ever contacted, and behaviour claims cite the terms above.

## Open items

- Kundintegration answers on fidelity and embedding/redistribution; the self-drawn mark and any default asset depend on them.
- Whether agreement or ELIN instruction material says anything about kundnummer on the item (public sources are silent; our printing of it is product policy).
- Deferred label PARTs 2+, with the postage-slot resize toward kliché artboard scale and any postoperatörszon refinement.
- Version bump at release (calendar scheme; 2026.11.0 is current).
- Everything this design leans on is upstream-identical karrio machinery, so an upstreamable future stays open; nothing here requires new fork SDK surface.

## Citations

All web sources accessed 2026-11-10.

- Särskilda villkor för 1:a-klassbrev inrikes, gäller fr o m 2025-01-01 — listed at `postnord.se/foretag/priser-och-villkor/tjanstevillkor-avtalskunder`.
- Skicka rätt med PostNord, 2026-01-26 — `postnord.se/siteassets/pdf/ovrigt/skicka-ratt-med-postnord-20260126.pdf`.
- Klichéer / label blocks — `postnord.se/foretag/forberedelser/klicheer` and `postnord.se/en/business/preparations/label-blocks/`; First Class assets under `postnord.se/siteassets/images/0.-foretag/forberedelser/klicheer/` (`pdf/1a-klassbrev-pp-kliche.pdf`, `eps/1a-klassbrev-pp-kliche2.eps`).
- Särskilda villkor för Svarspost inrikes, gäller fr o m 2023-05-02 — kundnummer format and designation-word protection.
- 1:a-klassbrev inrikes product page — `postnord.se/foretag/skicka/brev-och-paket/1a-klassbrev-inrikes` ("Spårbart: Nej").
- Fork SDK facts verified against the Joaqim/karrio checkout at `develop` 92605aa53 (snapshot-2026.11.05.6): `ShippingMixinProxy` in `karrio/universal/mappers/shipping_proxy.py`, `generate_label` in `karrio/addons/label.py`, raw-SVG passthrough in `karrio/addons/renderer.py`, `LabelType` in `karrio/core/units.py`, the response-over-payload merge in the server's `buy_shipment_label`, and `require_selected_rate` in `karrio/server/core/utils.py`.

## Appendix: kundintegration draft

Draft handed to the product owner on 2026-11-10 for sending to kundintegration@postnord.com; this appendix records it so the questions survive the session.

```text
To: kundintegration@postnord.com
Subject: Port payé label blocks — franking instructions and usage terms for label-generating integration

Hej,

We build shipping-platform integrations against PostNord's APIs (Booking APIs,
Track & Trace) and are adding support for domestic First Class letters sent under
our customers' port payé agreements: the integration composes and prints the
complete shipping label, including the franking marking.

From the label blocks page
(postnord.se/foretag/forberedelser/klicheer, accessed 2026-11-10) we see the
"First Class Mail" block with Port Payé, published as EPS/PDF for agreement
customers. Three questions:

1. Which document states the current requirements for the franking marking on
   port payé domestic letters — required content, wording, dimensions, and
   placement? We would like the current edition's title and version so we can
   cite it.
2. May an integration vendor embed the published label-block artwork (or a
   reproduction of it) in labels it generates for agreement customers, and may
   that artwork be redistributed inside the vendor's software package? If not,
   may we reproduce the marking's required text and geometry ourselves?
3. Is there a technical annex for storkunder describing complete label
   composition for domestic letters (address window placement, kundnummer
   placement, weight indication)?

Vänliga hälsningar,
```
