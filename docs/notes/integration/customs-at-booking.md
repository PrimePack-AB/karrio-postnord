---
title: "PostNord customs data at booking"
created: 2026-09-25
---

# PostNord customs data at booking

*Consumer-facing summary of how unified `customs` data becomes the booking request's customs structure.*
*Ported from the fork (Joaqim/karrio, branch docs-openspec): `docs/notes/postnord/customs-at-booking.md`, created 2026-09-25, last changed 2026-09-28. Sandbox evidence: `../sandbox/customs-invoice-live-verification.md`; CN22 evidence: `../sandbox/customs-declaration-live-verification.md`.*

Consumer-facing summary of how the PostNord connector turns unified `customs` data into the booking request, as implemented for the `nordic-customs-invoice-mapping` OpenSpec change on branch `feat-postnord-customs-invoice` (removed from the fork on 2026-10-20).

## Product groups

A shipment carrying `customs` with at least one commodity sends exactly one customs structure, selected by the booked service.
Letter services send a CN22 declaration (`customsDeclarationCN22`).
International Parcel (`postnord_postpaket_utrikes`, 91) sends a CN23 declaration (`customsDeclarationCN23`).
Every other service is a parcel product and sends a customs invoice (`customsInvoice`), with no CN22 or CN23.

| Group | Services (basicServiceCode) | Customs structure |
|---|---|---|
| Letters | `postnord_tracked` (04), `postnord_tracked_letter` (34), `postnord_export_letter` (UX), `postnord_varubrev_first_class` (86), `postnord_expressbrev` (LX), `postnord_rek` (RR), `postnord_rek_retur` (RK), `postnord_rek_extra` (RL), `postnord_rekommanderet_brev` (RE), `postnord_rekommanderet_quickbrev` (RQ), `postnord_varde` (VV), `postnord_afleveringsattest` (AF) | CN22 |
| International Parcel | `postnord_postpaket_utrikes` (91) | CN23 |
| Parcel products | all other services, for example `postnord_mypack_home`, `postnord_mypack_collect`, `postnord_parcel`, `postnord_pallet`, and any service code the connector does not list | customs invoice |

The letter set is `LETTER_SERVICES` and the CN23 service is `INTERNATIONAL_PARCEL_SERVICE`, both in `karrio/providers/postnord/units.py` and applied by `customs_structure`, so a service added later is a parcel product unless it is added to one of them.
Selecting CN23 and applying value thresholds such as PostNord Sweden's SEK 2 000 were not implemented at the time of this note.

Ported-note update (2026-10-13): International Parcel (91) now books a CN23 declaration (`customsDeclarationCN23`) unconditionally — PostNord's published requirement for Postpaket Utrikes is a CN23 at any value — reusing the CN22 mapping and checks minus the CN22-only `countryOfOrigin` and booking `postalCharges` as a zero amount.
The README's customs section carries the current behavior.

Ported-note update (2026-10-19): corrected the product-group sentence and table above, which listed International Parcel (91) as a customs-invoice parcel product; the connector books a CN23 for 91.
A test-mode sandbox probe found that PostNord's customs gate for a 91 booking accepts either an inline CN23 or application linkage and rejects a booking with neither with `SACUS-BR-24100901` ([cn23-composition-sandbox-probe.md](../sandbox/cn23-composition-sandbox-probe.md)).

## Shipments within the EU VAT area

When both the shipper and the recipient are inside the EU VAT area, the booking carries no CN22, CN23, or customs invoice, the standalone customs document is not fetched, and none of the fail-fast checks below run.
Callers may therefore attach customs data to every shipment; when they do and the shipment stays inside the EU VAT area, the response carries a warning message with code `customs_omitted_intra_eu` ("Customs data was not sent: the shipment from SE to PL stays within the EU VAT area"), the same code the DHL Freight Sweden connector uses.
The definition matches the DHL Freight Sweden connector and is implemented connector-locally as `in_eu_vat_area` in `karrio/providers/postnord/units.py`: the SDK's `EUCountry` members plus `GR`, Monaco (`MC`), and Northern Ireland (`GB` postal codes beginning `BT`), excluding Åland (`AX`, or `FI` 22000–22999), the Canary Islands (`IC`, or `ES` 35000–35999 and 38000–38999), Ceuta (`ES` 51000–51999), Melilla (`ES` 52000–52999), Büsingen (`DE` 78266), Heligoland (`DE` 27498), Mount Athos (`GR` or `EL` 63086), Livigno (`IT` 23041), Campione d'Italia (`IT` 22061), the French overseas departments and collectivities (`GP`, `GF`, `MQ`, `RE`, `YT`, or `FR` 97000–97999 and 98600–98899), and the Faroe Islands and Greenland (`DK` 3800–3999, a `DK` postal code prefixed `FO` or `GL`, or a three-digit `DK` postal code).
A postal code is compared after it is trimmed and upper-cased, a leading country code or territory code (`AX` under `FI`, `FO` and `GL` under `DK`, `IC` and `EA` under `ES`) followed by a hyphen, a space, or, except for `GB`, a digit is removed, and its spaces are dropped, so `FI-22100`, `AX22100`, and `GB BT1 1AA` read as `22100`, `22100`, and `BT11AA`.
`JE`, `GY`, `IM`, and `BT` are never removed, because they begin United Kingdom postcodes.
A parcel from Sweden to Mariehamn (`FI` 22100) therefore still carries a customs invoice.

## Customs invoice field sources

| PostNord field | Unified source |
|---|---|
| `type` | `customs.commercial_invoice`: true sends `COMMERCIAL`, false or omitted sends `PROFORMA`, regardless of `content_type` |
| `declarationType` | always `invoiceExportDeclaration` |
| `seller` | shipper: `company_name` (else `person_name`) as `name`, address lines as `streets`, `city`, `postal_code`, `country_code` |
| `seller.vatNo` | shipper `federal_tax_id` |
| `seller.partyIdentification` | connection `customer_number` with `partyIdType` `160` |
| `seller.eoriNo` | `customs.options.eori_number`, else the shipper `state_tax_id` |
| `buyer` | recipient, mapped like the seller; `vatNo` from the recipient tax id when present |
| `seller.contacts`, `buyer.contacts` | `person_name` (else `company_name`) as `name`, `phone_number` as `phoneNo`, `email` as `emailAddress` |
| `voec`, `ioss` | `customs.options.voec_number`, `customs.options.ioss_number` |
| `invoice.invoiceNo` | `customs.invoice`, else the shipment `reference` |
| `invoice.shippingDate` | `customs.invoice_date`, passed through unchanged (PostNord expects `YYYY-MM-DD`) |
| `invoice.reasonForExportation` | always `1000` (permanent export, covering sale, gift, and sample) |
| `detailedDescription[]` | per commodity: `quantity`, `hs_code` as `hsTariffNumber`, `title` (else `description`) as `content`, `origin_country` as `countryOfOrigin`, `weight` × `quantity` in KGM as both `netWeight` and `grossWeight`, `value_amount` × `quantity` and `value_currency` as `itemValue` |
| `totalNetWeight` | sum of the line weights in KGM |
| `totalGrossWeight` | sum of the parcel weights in KGM, which include packaging; the sum of the line weights only when no parcel weight is given |
| `invoiceTotal` | sum of the line values, rounded to two decimals, in the currency of the first commodity that sets one |

Commodity `value_amount` and `weight` are per unit, so each line carries them multiplied by `quantity`, and the value and net-weight totals sum the lines.
The CN22 is built the same way: its `totalValue` sums the line values and its `totalGrossWeight` follows the same parcel-weight rule as the invoice.
Postal codes are sent as strings, so a Norwegian `0154` keeps its leading zero.

## Fail-fast errors

These checks run before any request is sent for shipments leaving the EU VAT area, and each failure returns a `SHIPPING_SDK_FIELD_ERROR` message.
The checks run in sequence, so a request can fail on one check before the next is evaluated; the registration-placement check, the line-content check, and the customs invoice field checks each name every offending field at once.

| Condition | Details key | Message |
|---|---|---|
| Customs invoice without shipper tax id | `shipper.federal_tax_id` | shipper VAT number is required for a PostNord customs invoice |
| Customs invoice without `customs.invoice` and without `reference` | `customs.invoice` | invoice number is required for a PostNord customs invoice; send customs.invoice or a shipment reference |
| Shipper or recipient without person and company name | `shipper.person_name` / `recipient.person_name` | contact name is required for a PostNord customs invoice |
| Shipper or recipient without phone number | `shipper.phone_number` / `recipient.phone_number` | contact phone number is required for a PostNord customs invoice |
| Commodity without HS code | `customs.commodities[<i>].hs_code` | HS tariff number is required for a PostNord customs invoice line |
| Commodity without origin country | `customs.commodities[<i>].origin_country` | country of origin is required for a PostNord customs invoice line |
| Commodity without title and description (CN22, CN23, and customs invoice) | `customs.commodities[<i>].title` | PostNord requires a title or description for each customs line |
| CN22 or CN23 without any of EORI, VOEC, or IOSS and without a shipper `state_tax_id` | `customs.options` | a customs declaration requires at least one of eori_number, voec_number, or ioss_number, or a shipper state_tax_id to use as the EORI |
| CN22 or CN23 with more than 13 commodities | `customs.commodities` | customs.commodities exceeds the 13-line customs declaration limit |
| Registration numbers under shipment `options` | `options.<key>` | customs registration number; send it under customs.options |

The CN22 and CN23 registration rule mirrors PostNord's rejection `SACUS-BR-24062502`.
It is not applied to customs invoices, because the sandbox accepted a parcel customs invoice without registration numbers; the production probe confirmed the same (see `../sandbox/customs-invoice-live-verification.md`).

Ported-note update (2026-10-19): corrected claims that did not match the code when the note was ported: the EU VAT area admits Monaco and Northern Ireland, `seller.vatNo` takes the shipper `federal_tax_id` only, `seller.eoriNo` falls back to the shipper `state_tax_id`, the registration and 13-line checks apply to CN22 and CN23 and a shipper `state_tax_id` satisfies the registration check, the line-content check was missing, and the checks run in sequence rather than reporting every missing field at once.

## Composed customs invoice document

PostNord composes the customs invoice into the booking's label printout (`printoutComposition` `{label: 1, customsInvoice: 1}`), and `meta.printout_composition` lists the composed kinds.
For parcel-product bookings with customs data, the connector also fetches the standalone customs document with `POST /rest/shipment/v3/labels/ids/{pdf,zpl}` and `definePrintout=onlyCustomsDeclarations`, keyed by the booking's `printId` (else the item id), in the label's format.
The document is attached to `docs.extra_documents` with the category PostNord reports, `customsInvoice` for parcel products.
Because the invoice is also page 2 of the label printout, the standalone document duplicates it.
A failed fetch never fails the booking; it is reported as messages next to the shipment details.
Letter services and, since the CN23 change, International Parcel fetch the standalone declaration only when `postnord_standalone_customs_documents` is set (shipment option, else connection config); by default a letter's CN22 is composed into `docs.label` in both PDF and ZPL (openspec change `stamp-embedded-customs-forms`, 2026-09-28).

Ported-note update (2026-10-19): the connector verifies International Parcel's CN23 composition on PDF labels, against CN23 page-text markers in `DOCUMENT_SECTIONS` (`karrio/providers/postnord/stamping.py`) seeded from a test-mode sandbox capture in which PostNord composed one CN23 page into a 91 label (`sandbox/p1-cn23-gateway.printout01.pdf` in the local fixture directory described in [docs/development](../../development/index.md#local-postnord-printouts), [cn23-composition-sandbox-probe.md](../sandbox/cn23-composition-sandbox-probe.md)); a mismatch is a `postnord_unexpected_label_composition` warning and the label is returned unchanged.
A ZPL 91 label skips the content check, and the `label_cn23` signature stamping seed covers PDF only, because no ZPL CN23 printout has been captured.
Every customs-declared booking also attests the declared `meta.printout_composition` against its branch's kinds (`{label, cn23}` for 91), warning with `postnord_printout_composition_mismatch` on a disagreement.
The capture is test-mode, which sends no EDI downstream, so production composition may differ (see the README's customs section).

## Example

This payload is the `CustomsInvoiceShipmentPayload` fixture in `tests/postnord/test_shipment.py`, whose expected booking body is asserted by `test_create_shipment_customs_invoice_request`.

```python
{
    "shipper": {
        "address_line1": "Sandhamnsgatan 61",
        "city": "Stockholm",
        "postal_code": "11528",
        "country_code": "SE",
        "state_code": "Stockholm",
        "person_name": "John Sender",
        "company_name": "ACME Sender AB",
        "phone_number": "+46701234567",
        "email": "sender@example.com",
        "federal_tax_id": "SE556123471101",
    },
    "recipient": {
        "address_line1": "Karl Johans gate 22",
        "city": "Oslo",
        "postal_code": "0154",
        "country_code": "NO",
        "person_name": "Kari Receiver",
        "company_name": "Receiver AS",
        "phone_number": "+4791234567",
        "email": "receiver@example.com",
    },
    "parcels": [
        {
            "weight": 1.5,
            "width": 20.0,
            "height": 10.0,
            "length": 30.0,
            "weight_unit": "KG",
            "dimension_unit": "CM",
            "packaging_type": "small_box",
        }
    ],
    "service": "postnord_parcel",
    "options": {"insurance": 500.0},
    "reference": "ORDER-7788",
    "customs": {
        "content_type": "merchandise",
        "commercial_invoice": True,
        "invoice": "INV-2026-001",
        "invoice_date": "2026-09-25",
        "commodities": [
            {
                "title": "Wool socks",
                "quantity": 2,
                "weight": 0.2,
                "weight_unit": "KG",
                "value_amount": 150.0,
                "value_currency": "SEK",
                "hs_code": "6115950000",
                "origin_country": "SE",
            },
            {
                "description": "Knitted cap",
                "quantity": 1,
                "weight": 0.1,
                "weight_unit": "KG",
                "value_amount": 200.0,
                "value_currency": "SEK",
                "hs_code": "6505003000",
                "origin_country": "SE",
            },
        ],
        "options": {"eori_number": "SE556000123401"},
    },
}
```

The resulting `customsInvoice` element, with the fixture's connection `customer_number` `00000000`:

```json
{
  "declarationType": "invoiceExportDeclaration",
  "type": "COMMERCIAL",
  "seller": {
    "partyIdentification": {"partyId": "00000000", "partyIdType": "160"},
    "vatNo": "SE556123471101",
    "name": "ACME Sender AB",
    "streets": ["Sandhamnsgatan 61"],
    "city": "Stockholm",
    "postalCode": "11528",
    "countryCode": "SE",
    "contacts": {"name": "John Sender", "phoneNo": "+46701234567", "emailAddress": "sender@example.com"},
    "eoriNo": "SE556000123401"
  },
  "buyer": {
    "name": "Receiver AS",
    "streets": ["Karl Johans gate 22"],
    "city": "Oslo",
    "postalCode": "0154",
    "countryCode": "NO",
    "contacts": {"name": "Kari Receiver", "phoneNo": "+4791234567", "emailAddress": "receiver@example.com"}
  },
  "invoice": {"invoiceNo": "INV-2026-001", "shippingDate": "2026-09-25", "reasonForExportation": "1000"},
  "detailedDescription": [
    {
      "quantity": 2,
      "hsTariffNumber": "6115950000",
      "content": "Wool socks",
      "countryOfOrigin": "SE",
      "netWeight": {"value": 0.4, "unit": "KGM"},
      "grossWeight": {"value": 0.4, "unit": "KGM"},
      "itemValue": {"amount": 300.0, "currency": "SEK"}
    },
    {
      "quantity": 1,
      "hsTariffNumber": "6505003000",
      "content": "Knitted cap",
      "countryOfOrigin": "SE",
      "netWeight": {"value": 0.1, "unit": "KGM"},
      "grossWeight": {"value": 0.1, "unit": "KGM"},
      "itemValue": {"amount": 200.0, "currency": "SEK"}
    }
  ],
  "totalNetWeight": {"value": 0.5, "unit": "KGM"},
  "totalGrossWeight": {"value": 1.5, "unit": "KGM"},
  "invoiceTotal": {"amount": 500.0, "currency": "SEK"}
}
```
