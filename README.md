# karrio.postnord
>
> [!WARNING]
> This project is actively in development, expect breaking changes.

This package is a PostNord extension of the [karrio](https://pypi.org/project/karrio) multi carrier shipping SDK.

## Requirements

`Python 3.11+`

## Installation

```bash
pip install git+https://github.com/PrimePack-AB/karrio-postnord.git
```

The `karrio` dependency must resolve to the fork SDK — upstream karrio cannot import this plugin; see [Fork SDK floor](#fork-sdk-floor) below.
The package registers through the `karrio.plugins` entry point group under the id `postnord`, so installing it makes the carrier available to every karrio SDK runtime, and uninstalling it removes the carrier.
A Karrio server builds its reference models at boot, so restart the API after installing or upgrading the plugin; `GET /v1/references` then lists the carrier.
A server deployment can also expose the package through the `KARRIO_PLUGINS` directory mount instead of installing it.

### Fork SDK floor

This connector is fork-coupled: it uses the document-stamping `PluginMetadata` fields that exist only in the [Joaqim/karrio](https://github.com/Joaqim/karrio) fork's SDK, not in upstream karrio, so a runtime on upstream karrio cannot import it.
The package declares a plain `karrio` dependency because no pip-solvable fork reference exists; the karrio the plugin runs against must therefore be a fork checkout providing the stamping SDK surface: `PluginMetadata.stamp_seeds` and `PluginMetadata.document_sections` together with `karrio.lib.StampSeed`, `StampPlacement`, `AnyOf`, `CustomsComposition`, and `classify_customs_composition`.
CI tests against the fork's `develop` branch, which provides it (last verified at a7355a5c8 on 2026-10-19), and checks these names by import before running the suite; `develop` is regenerated, so the requirement is stated by capability rather than by commit.

## Usage

```python
import karrio.sdk as karrio
from karrio.mappers.postnord.settings import Settings


# Initialize a carrier gateway
postnord = karrio.gateway["postnord"].create(
    Settings(
        apikey="...",            # PostNord API key (single credential, sent as a query param)
        customer_number="...",   # PostNord customer number
        application_id="...",    # PostNord application id
        issuer_code="Z12",       # consignor issuer code (default "Z12")
        account_country_code="SE",
        test_mode=True,          # True -> sandbox (atapi2.postnord.com); False -> production (api2.postnord.com)
    )
)
```

Check the [Karrio Mutli-carrier SDK docs](https://docs.karrio.io) for Shipping API requests.

## Authentication

PostNord uses a single `apikey`, sent as a query parameter on every call (the Booking, Pickup, Service Points, and Tracking APIs are unsecured beyond the key).
Authorization is granted per API product: a key may be authorized for Booking but not for the Transit Time product, in which case that product returns `403 "Invalid API Key"`.
`test_mode` selects the host — `atapi2.postnord.com` (sandbox) when on, `api2.postnord.com` (production) when off — so a production key supplied to a test-mode connection is rejected by the sandbox rather than creating real shipments.

## Connection settings

| Setting | Required | Default | Description |
| --------- | ---------- | --------- | ------------- |
| `apikey` | yes | — | PostNord API key (query-param credential) |
| `customer_number` | yes | — | PostNord customer number |
| `application_id` | yes | — | PostNord application id |
| `issuer_code` | no | `Z12` | Consignor issuer code |
| `account_country_code` | no | `SE` | Account country |
| `test_mode` | no | `false` | Route to sandbox vs production |

Connection config options (under the connection's config):

| Option | Default | Description |
| -------- | --------- | ------------- |
| `label_type` | `PDF` | Per-connection default label file format (`PDF` or `ZPL`), overridden per request by the shipment `label_type`. PostNord selects the format by endpoint path (`/labels/pdf` vs `/labels/zpl`). |
| `label_size` | — (unset) | PostNord physical label size, sent as the `labelType` query parameter: `standard` (190×105mm), `small` (75×105mm), or `ste` (PDF-only). Unset omits the parameter and PostNord defaults to `standard`. |
| `enable_transit_times` | `false` | Opt-in: call the Transit Time API to enrich `transit_days`/estimated delivery and filter by serviceability. Requires the key to be subscribed to the Transit Time product. |
| `language` | `en` | Default booking locale when a shipment sets no `options.language`. Leaving it unset still books in `en` unless `locale_by_recipient` resolves a Nordic locale first; setting it outranks `locale_by_recipient`. |
| `locale_by_recipient` | `false` | Derive the booking locale from the recipient country (`SE`→`sv`, `DK`→`da`, `NO`→`no`, `FI`→`fi`) when neither `options.language` nor `language` is set. The server also persists the derived locale on the shipment and its tracker. |
| `offer_tracked_letter` | `false` | Offer Tracked Letter (34) in rates. |
| `offer_export_letter` | `false` | Offer Export Letter (UX) in rates; requires issuer `Z12`. |
| `postnord_standalone_customs_documents` | `false` | Connection default for the shipment option of the same name: attach the standalone customs declaration of letter (CN22) and International Parcel (91, CN23) bookings with customs data (see [Customs declarations](#customs-declarations)). |

Tracked Letter (34) and Export Letter (UX) are rateable catalog services but are withheld from rate results until their `offer_*` toggle is enabled, so the default rate catalog is unchanged until a merchant opts in; Export Letter additionally requires the Sweden issuer (`Z12`). The other letter and registered-mail products (04, 86, LX, RR, RK, RL, RE, RQ) are offered ungated, with PostNord's booking API as their gate.

## Shipment options

| Option | Type | Default | Description |
| -------- | ------ | --------- | ------------- |
| `entry_code` | string | — | PostNord entry code (door code) for the recipient's building, e.g. an apartment entrance code. Sent as a shipment `freeText` with usage code `ZDC`; PostNord prints it as "Ref 2" on the label and maps it to the consignee reference. Max 50 characters: a longer value rejects the booking with an `ENTRY_CODE_LENGTH` message before any call to PostNord. PostNord does not document which services accept it — the value is passed through unverified and is ignored by services without door-code support. |
| `postnord_standalone_customs_documents` | bool | connection config, else `false` | Attach the standalone customs declaration of a letter (CN22) or International Parcel (91, CN23) booking with customs data to `docs.extra_documents`, fetched by id in the label's format. Read by the connector only; never sent to PostNord as an additional service. |
| `language` | string | `en` | Booking/notification locale (lowercase ISO 639-1), sent as the query `locale` (SMS/Email language) and uppercased as the body `language` element (label/document text). Resolved per request, then from connection config, then (with `locale_by_recipient` enabled) from the recipient's country code. PostNord's documented booking default is `sv`, but the connector sends `en` when nothing else resolves, so Swedish-market connections that expect Swedish SMS/Email text should set `config.language` to `sv`. |
| `sms_notification` | bool | — | Opt in to PostNord notifying the consignee by SMS (`additionalServiceCode` `A3`, consignee `smsNo`). Least intrusive channel; notification language follows the booking locale. |
| `email_notification` | bool | — | Opt in to e-mail notification (`A4`, consignee `emailAddress`). |
| `postnord_notify_by_letter` | bool | — | Opt in to letter notification (`A2`, consignee address). |
| `postnord_notify_by_phone` | bool | — | Opt in to voice-call notification (`A9`, consignee `phoneNo`). |
| `postnord_driver_notification` | bool | — | Opt in to driver notification (`B8`, consignee `phoneNo`). |
| `postnord_service_point_id`, `postnord_service_point_name` / `_street` / `_city` / `_postal_code` / `_country_code` | string | — | Book to a chosen service point (e.g. a Service Points v5 lookup result): the six values together send the point as the EDI `deliveryParty` and append `A7`, plus `A3` on the consignee phone (see [Service points](#service-points)). An id without complete details rejects the booking with a field error naming the missing options. Never sent as additional services. |

PostNord has no notification-suppress flag: the consignee is notified only when a notification additional service is booked, and channels combine freely — setting only `sms_notification` books SMS and nothing else. `false` or omitted books nothing, with one exception: a chosen service point appends `A3` on the consignee phone even against an explicit `sms_notification: false` (see [Service points](#service-points)), because the recipient must learn where to collect. Per-service rules apply (documented, not enforced here); PostNord validates them at booking, not the connector:

| Service | PostNord rule |
| --------- | --------------- |
| Parcel (18) | One of A2/A3/A4 must be booked. |
| MyPack Home (17) | Consignee SMS or e-mail contact data is mandatory, and additional service C7 (`postnord_flexchange`) is mandatory unless A6 or F1 is booked; the connector has no option for A6 or F1. |
| Return Pickup (20) | SMS is mandatory on both the consignor and the consignee party. |
| Return (24) | E-mail and SMS are mandatory on the return part. |

## Labels

The resolved `label_type` selects the booking endpoint: `/rest/shipment/v3/edi/labels/pdf` or `/rest/shipment/v3/edi/labels/zpl`.
Both return the label inline in `labelPrintout[].printout`.

The Booking API swagger documents `printout.encoding` as base64 only, but the ZPL endpoint returns raw UTF-8 ZPL text with `encoding: "none"` (observed live), sometimes without `labelFormat`.
The connector passes base64 printouts (or printouts without `encoding`) through and base64-encodes any other encoding, so `docs.label` is always base64; a missing `labelFormat` falls back to the requested label type.
The live ZPL body starts with persistent host commands (`^LL1520`, i.e. 190 mm at 8 dots/mm, and `^CI28` for UTF-8) followed by `^CW` font aliases for printer-memory fonts, all preserved verbatim.

## Pickups

`Pickup.schedule` uses one of two PostNord Booking API operations.

When `options.tracking_numbers` carries PostNord item ids and the pickup address country is SE, DK, or FI and equals `account_country_code`, the connector books through `POST /rest/shipment/v3/pickups/ids`, which only supports domestic pickups of items in SE, DK, and FI.
Its body is one entry per item id with the pickup window, so the pickup address, `instruction`, `package_location`, and `options.service` are not sent on this path.

Every other pickup is a pickup booking through `POST /rest/shipment/v3/pickups`, following PostNord's pickup guide (<https://guide.developer.postnord.com/>, Shipment / Booking / Booking APIs v3 / Book Pickups).
The request carries `messageFunction` `PickupBooking`, a uuid4 `messageId`, basic service code `0` (domestic/Nordic pickup), package type `PC`, and `itemId` `"0"`; the pickup address is the consignor, so no pickup party is sent.
The `instruction` (or `package_location`) is sent as a freeText with usage code `ADS`, only when one is given.
`options.service` may select `0` or `CR` (collection request); any other value is rejected with a field error before booking.
Pickups from countries other than SE, FI, and DK are rejected with a field error, because a collection request needs a consignee, which a Karrio pickup request cannot carry.
Item ids in `options.tracking_numbers` are ignored on this path, and shipment identifiers or client references are never sent as an `itemId`.
A domestic SE pickup without a consignee was accepted by the sandbox; `CR` and `/v3/pickups/ids` have not been verified there.

Both operations return a booking id, reported as `confirmation_number`; the first returned id, the pickup id on `/v3/pickups` (for example `PB015606512T`), is reported as `id`.
PostNord has no update or cancel route for either operation, so `Pickup.update` and `Pickup.cancel` return a `not_supported` message without calling PostNord.

## Service points

Service-point lookup (Service Points v5) is connector-local: Karrio has no unified service-point operation, so it is reached through the gateway proxy.

```python
import karrio.providers.postnord.service_points as service_points

request = service_points.service_points_request(
    dict(country_code="SE", postal_code="11528", number_of_points=3),
    postnord.settings,
)
points, messages = service_points.parse_service_points_response(
    postnord.proxy.find_service_points(request), postnord.settings
)
```

Passing `northing` and `easting` instead of an address selects the coordinate lookup.
Each point is a dict with `id`, `name`, `type`, `address` (the delivery address used for EDI and labels), `visiting_address` (where the customer goes to collect, when PostNord returns one), `coordinates`, `opening_hours`, and `distance`.

A chosen point books through the six `postnord_service_point_*` shipment options (see [Shipment options](#shipment-options)): the point is sent as the EDI `deliveryParty` — `partyIdentification` carrying the service point id with `partyIdType` `"156"` — plus the point's name and address, with `A7` appended automatically and `A3` following when the consignee has a phone; incomplete details reject the booking with a field error naming the missing options.

## Customs declarations

### At booking

When a shipment carries `customs` with at least one commodity, the booking embeds one customs structure selected by the service.
When both the shipper and the recipient are inside the EU VAT area, no customs structure is sent, no customs document is fetched, and none of the customs field checks below apply; a caller-supplied `customs` block is reported as a `customs_omitted_intra_eu` warning message instead.
The EU VAT area follows the DHL Freight Sweden connector's definition (`in_eu_vat_area` in `units.py`): Greece is accepted as `GR` or `EL`, Monaco (`MC`) and Northern Ireland (`GB` postal codes beginning `BT`) are inside it, and special fiscal territories such as Åland (`AX`, or `FI` 22000–22999), the Canary Islands, Ceuta, Melilla, Büsingen, Heligoland, Mount Athos, Livigno, Campione d'Italia, the French overseas departments and collectivities (including `FR` 97000–97999 and 98600–98899), and the Faroe Islands and Greenland (`DK` 3800–3999, a `DK` postal code prefixed `FO` or `GL`, or a three-digit `DK` postal code) are outside it.
Postal codes are compared after a leading country or territory code such as `FI-` or `AX` is removed.
Currently, letter services (`LETTER_SERVICES` in `units.py`) send a CN22 declaration (`customsDeclarationCN22`), International Parcel (91) sends a CN23 declaration (`customsDeclarationCN23`), and every other service is a parcel product and sends a customs invoice (`customsInvoice`).
International Parcel (91) books the CN23 unconditionally — PostNord's published requirement for Postpaket Utrikes is a CN23 at any value (customs documents pages and Postpaket Utrikes terms §2), not a CN22.
Duties after booking, such as printing the customs documents and attaching the invoice copies to the parcel, are the consumer's.

CN22 mapping:

| Unified input | CN22 field |
| --------------- | ------------ |
| `customs.content_type` | `categoryOfItem.categoryType` (see below) |
| `customs.commodities[]` | `detailedDescription[]`: `title` (or `description`) as `content`, `quantity`, `grossWeight` in KGM, `value`, `hs_code` as `hsTariffNumber`, `origin_country` as `countryCode`, 1-based `rowNo` |
| parcel weights | `totalGrossWeight` in KGM: sum of the parcel weights (including packaging), else sum of the commodity line weights |
| commodity values | `totalValue`: sum of the line values, currency of the first commodity that sets one |
| `shipper.country_code` | `countryOfOrigin` |
| `customs.options.eori_number` (else the shipper `state_tax_id`) / `voec_number` / `ioss_number` | `EORIorPersonalIdNumber` / `voec` / `ioss` |

`content_type` accepts Karrio's values or PostNord's own, ignoring case and extra whitespace: `documents`→`DOCUMENT`, `gift`→`GIFT`, `sample`→`COMMERCIAL SAMPLE`, `merchandise`→`SALE OF GOODS`, `return_merchandise`→`RETURNED GOODS`, `other`→`OTHER`.
Other values are sent verbatim, and an absent `content_type` sends no `categoryOfItem`.

A CN22 without any of EORI, VOEC, or IOSS under `customs.options` and without a shipper `state_tax_id` to use as the EORI is rejected with a field error before any call, matching PostNord's rejection `SACUS-BR-24062502`.
Commodity `weight` and `value_amount` are per unit, so each line carries them multiplied by `quantity`, on both the CN22 and the customs invoice.
A CN22 accepts at most 13 commodity lines; more are rejected before any call to PostNord.
A commodity with neither `title` nor `description` is rejected before any call, on the CN22 and the customs invoice alike.
The CN23 branch of International Parcel (91) reuses the CN22 mapping and these checks in full, minus the CN22-only `countryOfOrigin`, and books `postalCharges` — required by the booking swagger but absent from the unified model — as a zero amount in the `totalValue` currency, a shape the PostNord sandbox accepted (test mode; `tests/postnord/fixtures/sandbox/p1-cn23-gateway.response.json`).

Customs invoice mapping:

| Unified input | Customs invoice field |
| --------------- | ----------------------- |
| `customs.commercial_invoice` | `type`: `COMMERCIAL` when true, `PROFORMA` when false or omitted |
| (fixed) | `declarationType` `invoiceExportDeclaration`, `invoice.reasonForExportation` `1000` (permanent export) |
| shipper | `seller`: `company_name` (or `person_name`), address, `federal_tax_id` as `vatNo`, connection `customer_number` as `partyIdentification`, `customs.options.eori_number` (else the shipper `state_tax_id`) as `eoriNo` |
| recipient | `buyer`: same address mapping, tax id as `vatNo` when present |
| party `person_name` (or `company_name`), `phone_number`, `email` | `contacts` |
| `customs.options.voec_number` / `ioss_number` | `voec` / `ioss` |
| `customs.invoice` (or the shipment `reference`), `customs.invoice_date` | `invoice.invoiceNo`, `invoice.shippingDate` |
| `customs.commodities[]` | `detailedDescription[]`: `quantity`, `hs_code`, `title` (or `description`), `origin_country`, weight in KGM as `netWeight` and `grossWeight`, `itemValue` |
| commodity weights and values | `totalNetWeight` (sum of the line weights), `invoiceTotal` (sum of the line values, currency of the first commodity that sets one) |
| parcel weights | `totalGrossWeight`: sum of the parcel weights (including packaging), else sum of the commodity line weights |

A customs invoice is rejected with a field error before any call when a commodity has neither `title` nor `description`, when the shipper has no `federal_tax_id`, when neither `customs.invoice` nor `reference` is set, when the shipper or recipient lacks a contact name or phone number, or when a commodity lacks `hs_code` or `origin_country`.
Registration numbers are optional on the customs invoice.

Registration-number keys under shipment `options` are rejected with a field error, because unknown shipment options would otherwise be dropped silently.

For bookings with customs data, PostNord composes the customs document into the booking printout itself: `docs.label` is that composed printout, returned unchanged, and `meta.printout_composition` reports the composed kinds PostNord declares, e.g. `["cn22", "label"]`.
For letter services the CN22 composes in both formats — one PDF or one ZPL carrying the CN22 section and the shipping label section; in a PDF the two sections may share one A4 page or sit on separate pages (a sandbox export letter booking returned the tracked letter label on page 1 and the CN22 on page 2), and verification accepts both layouts.
For International Parcel (91), a test-mode sandbox booking carrying the mapper-built CN23 was accepted with `printoutComposition` `{cn23: 1, label: 1}` and one two-page A4 PDF — the parcel label on page 1, the CN23 on page 2 (`tests/postnord/fixtures/sandbox/p1-cn23-gateway.response.json`; the printout's page count and digest are recorded in `tests/postnord/fixtures/sandbox/manifest.json`, and the printout itself is not distributed); test mode sends no EDI downstream, so production composition may differ.
The connector verifies the label with the SDK customs classifier (`lib.classify_customs_composition`) using PostNord's declared section markers (`DOCUMENT_SECTIONS` in `providers/postnord/stamping.py`).
A label that does not classify as the shipping label composed with the branch's declaration is still returned unchanged, with a `postnord_unexpected_label_composition` warning message naming the expected and the classified composition; the booking never fails on it.
Letter (CN22) labels are verified in both formats.
International Parcel (91) labels are verified on PDF against the CN23 page-text markers seeded from that capture, read from the classifier's matched kinds because its composition vocabulary is closed to the CN22; a ZPL label skips the check, no ZPL CN23 printout having been captured.
Customs-invoice labels declare no section markers in any format and are never content-verified; bookings without customs data or within the EU VAT area are not verified either.
Every customs-declared booking also attests the server-declared `meta.printout_composition` against the kinds its customs branch composes — `{label, cn22}` for letters, `{label, cn23}` for International Parcel (91), `{label, customsInvoice}` for parcel products: a disagreement warns with `postnord_printout_composition_mismatch`, an absent declaration stays silent, and the booking never fails on it.
The signature-strip stamping seeds cover the composed CN22 (`label_cn22`, both formats) and the composed CN23 on PDF (`label_cn23`, keyword "Sender's signature", measured on that sandbox capture); no ZPL CN23 seed exists because no ZPL CN23 printout has been captured.
The live 2026-09-28 captures of 91, made while the connector still embedded a CN22, show the parcel label followed by an upright CN22 V2 (a second `^XA`...`^XZ` format in ZPL, a second page in PDF) and stay load-bearing for the `label_cn22` stamping seeds; replayed against the CN23 branch they now warn by design — the attestation sees the declared CN22 composition on both formats, and the PDF content check also finds no CN23 markers.

For parcel-product bookings with customs data, the connector also fetches the standalone customs document (`POST /rest/shipment/v3/labels/ids/{pdf,zpl}` with `definePrintout=onlyCustomsDeclarations`), in the label's format and keyed by the booking's `printId`, and attaches it to `docs.extra_documents`.
For letter services and International Parcel (91), no standalone document is fetched unless the `postnord_standalone_customs_documents` opt-in is set, per shipment in `options` or on the connection config; with the opt-in the same by-id fetch attaches the standalone declaration — the CN22 for letters, the CN23 for International Parcel (91) — in addition to the label, identically for PDF and ZPL.
The document category is the kind PostNord reports in `printoutComposition` (`cn22`, `customsInvoice`, …), falling back to `customs_declaration`.
A failed fetch never fails the booking; it surfaces as a message.

### After booking

`create_customs_declaration` (`POST /rest/shipment/v3/customs/declaration`) and `create_customs_declaration_pdf` (`.../declaration/pdf`) declare customs for an item whose booking was already sent.
The caller builds the declaration with the generated `karrio.schemas.postnord.customs_declaration_request` types and owns its content: exactly one id, exactly one of `customsDeclarationCN22`, `customsDeclarationCN23`, or `customsInvoice`, and `updateIndicator` (`Original`, `Update`, `Deletion`; Update and Deletion are not supported for issuers Z11, Z13, and Z14).
Karrio builds the envelope, enforces the id, branch, and 13-line constraints, submits, and reports; it does not reconcile or retract earlier declarations.

```python
import karrio.schemas.postnord.customs_declaration_request as postnord_customs
from karrio.providers.postnord import customs

declaration = postnord_customs.CustomsDeclarationRequestType(
    updateIndicator="Original",
    ids=[postnord_customs.IDType(id="00373500454541020957", idType="ITEMID")],
    customsDeclarationCN22=postnord_customs.CustomsDeclarationCN22Type(
        countryOfOrigin="SE",
        EORIorPersonalIdNumber="SE5561234711",
        categoryOfItem=postnord_customs.CategoryOfItemType(categoryType=["GIFT"]),
        detailedDescription=[
            postnord_customs.CustomsDeclarationCN22DetailedDescriptionType(
                content="Paperback novels",
                quantity=postnord_customs.TotalNumberOfPackagesType(value=2),
                grossWeight=postnord_customs.WeightType(value=0.5, unit="KGM"),
                value=postnord_customs.PostalChargesType(amount=250.0, currency="SEK"),
                hsTariffNumber="07019010",
                countryCode="SE",
                rowNo=1,
            )
        ],
        totalGrossWeight=postnord_customs.WeightType(value=0.5, unit="KGM"),
        totalValue=postnord_customs.PostalChargesType(amount=250.0, currency="SEK"),
    ),
)

request = customs.customs_declaration_request(declaration, postnord.settings)
result, messages = customs.parse_customs_declaration_response(
    postnord.proxy.create_customs_declaration(request), postnord.settings
)
```

For the PDF variant, pass `paper_size` (A4/A5/A6/LETTER/LABEL), `rotate` (0/90/180/270), `multi_pdf`, `page_horizontal_align`, or `page_vertical_align` to `customs_declaration_request`, call `create_customs_declaration_pdf`, and parse with `parse_customs_declaration_pdf_response`.
The result holds `booking_id` and one `id_information` entry per id with its `OK`/`FAIL` status; the PDF variant adds `documents` as `ShippingDocument` entries.
Rejections, including PostNord's "EDI must have been sent earlier", return `None` with messages.

The schema generator annotates digit-only string fields (`partyIdType`, invoice `postalCode`, `reasonForExportation`, `transportModeBorder`, `basicServiceCode`) as `int`; pass them as strings so leading zeros survive.
`BuyerType` is one class covering the invoice seller, buyer, and ship-to parties; populate only the fields each party needs, as none are validated client-side.
Live checks found the digital endpoint's success response to be the bare `bookingResponseCN` object and intra-EU declarations (SE→PL) accepted.

## Supported operations

| Operation | Notes |
| ----------- | ------- |
| Rating | Static rates from the connection's service levels / server-side RateSheet (no carrier call by default). Optionally enriched with live transit times when `enable_transit_times` is on. |
| Shipment | Booking + label retrieval in one call (`/rest/shipment/v3/edi/labels/pdf`, or `/labels/zpl` when the resolved label type is ZPL). |
| Pickup | Domestic pickup by item id (`/v3/pickups/ids`) or pickup booking (`/v3/pickups`) via `Pickup.schedule`; see [Pickups](#pickups). |
| Tracking | Event-based via Track & Trace v7 (`findByIdentifier`); degrades to link-only (tracking URL + generic status) when the key isn't authorized for the T&T product. |
| Returns | Booked via the shipment create flow with a return service code. |
| Service points | Connector-local lookup (`gateway.proxy.find_service_points`). |

## Limitations

Tracking uses PostNord Track & Trace v7 (`findByIdentifier`) for full event history and normalized statuses. Per-product authorization applies (as with Transit Time): if the key is not subscribed to the Track & Trace product, tracking degrades gracefully to link-only — a tracking URL plus a single generic status, no events.

Cancellation is not available over the REST API: PostNord's REST `/v3/edi` ignores `updateIndicator: "Deletion"` and re-books a duplicate, and the id-based delete endpoint is absent from the published spec. The connector therefore never cancels and never reports a false success — cancel returns an explicit failure message pending PostNord's v3 REST reference manual.

Manifest is not supported: PostNord has no scan-form/end-of-day manifest endpoint. Use `Pickup.schedule` for courier collection.

Transit-time enrichment is opt-in (`enable_transit_times`, default off) because it requires a key subscribed to the Transit Time product. When enabled but unavailable, rating degrades gracefully to static transit days with a warning rather than failing.

## Development

Clone this repository next to a checkout of the [Joaqim/karrio](https://github.com/Joaqim/karrio) fork, create a virtual environment, and install the fork SDK together with the connector:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # -e ../karrio/modules/sdk, fork-coupled (see Fork SDK floor)
.venv/bin/pip install -e .
```

Run the test suite from the repository root; running it from another directory can resolve a different checkout's provider code first:

```bash
.venv/bin/python -m unittest discover -f -s tests -v
```

Regenerate the `karrio/schemas/postnord` modules after editing `schemas/*.json` by pointing `ROOT` at the karrio monorepo checkout:

```bash
ROOT=../karrio ./generate
```

## License

Copyright (c) 2026 PrimePack AB.
This Karrio Connector Plugin is distributed under the GNU Lesser General Public License v3.0; see [LICENSE](LICENSE).

## Trademarks and affiliation

PrimePack AB is not affiliated with, endorsed by, or sponsored by PostNord or any of its subsidiaries.
PrimePack AB does not own karrio and is not affiliated with Karrio Inc.
PostNord and karrio are names or trademarks of their respective owners and are used only to identify the carrier and the SDK this plugin works with.
The PostNord API specifications are not included in this repository; see [the development guide](docs/development/index.md#api-specifications-and-manuals) for where to obtain them.
