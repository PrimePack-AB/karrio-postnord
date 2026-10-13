---
title: "Customs"
---

When a shipment carries `customs` with at least one commodity and travels out of the EU VAT area, the booking embeds exactly one customs structure, selected by the booked service.
The connector builds the structure, validates it before any carrier call, and composes or fetches the resulting documents (see [Labels](labels.md)).

## Structure selection

| Service family | Structure | Notes |
|----------------|-----------|-------|
| Letter services | `customsDeclarationCN22` | the postal CN22; requires at least one of EORI, VOEC, IOSS under `customs.options` |
| International Parcel (91) | `customsDeclarationCN23` | booked unconditionally — PostNord's published requirement for Postpaket Utrikes is a CN23 at any value, not a value-threshold CN22 |
| Every other service | `customsInvoice` | commercial or proforma invoice; registration numbers optional |

The selection is `customs_structure` in `karrio/providers/postnord/units.py`, keyed by basic service code; a service added later is a parcel product unless it is added to `LETTER_SERVICES`.

## The EU VAT area

When both the shipper and the recipient are inside the EU VAT area, no customs structure is sent, no customs document is fetched, and none of the customs checks run.
Supplied customs data is reported as a `customs_omitted_intra_eu` warning instead, so callers may attach customs data to every shipment unconditionally.

The definition (`in_eu_vat_area` in `units.py`) matches the DHL Freight Sweden connector: the EU member states plus Greece under either `GR` or `EL`, plus Monaco (`MC`), minus the special fiscal territories, plus Northern Ireland.

| Treatment | Territories |
|-----------|-------------|
| Inside (added beyond the SDK's EU list) | Monaco `MC`; Greece as `GR` alongside the VAT-prefix `EL`; Northern Ireland by `GB` postcode prefix `BT` (inside the EU VAT area for goods) |
| Outside (own country code) | Åland `AX`; the Canary Islands `IC`; the French overseas departments `GP`, `GF`, `MQ`, `RE`, `YT` |
| Outside (postcode range within a member state) | Åland `FI` 22000–22999; Canary Islands `ES` 35000–35999 and 38000–38999; Ceuta `ES` 51000–51999; Melilla `ES` 52000–52999; Büsingen `DE` 78266; Heligoland `DE` 27498; Mount Athos `GR` 63086; Livigno `IT` 23041; Campione d'Italia `IT` 22061 |

A parcel from Sweden to Mariehamn (`FI` 22100) therefore still carries customs.

## CN22 and CN23 mapping

The CN22 branch maps the unified customs payload onto the postal declaration: `content_type` normalized through PostNord's category vocabulary (`merchandise` → `SALE OF GOODS`, `gift` → `GIFT`, and so on, with unknown values passed verbatim), one `detailedDescription` row per commodity, `totalGrossWeight` from the parcel weights, and `totalValue` summing the per-line values.
Commodity `weight` and `value_amount` are per unit, so every line carries them multiplied by `quantity`.
Registration numbers (`eori_number`, `voec_number`, `ioss_number`) ride `customs.options` — a provider-level enum exists because the core karrio `CustomsOption` enum carries no VOEC or IOSS members, and a registration number placed under shipment `options` rejects with a field error so it is never silently dropped.

A CN22 without any registration number rejects before any carrier call, mirroring PostNord's rejection `SACUS-BR-24062502`, and declarations accept at most 13 commodity lines.
The CN23 branch of International Parcel reuses the CN22 mapping and checks in full, minus the CN22-only `countryOfOrigin`, and books the swagger-required `postalCharges` as a zero amount in the `totalValue` currency.

## Customs invoice mapping

The invoice branch builds a commercial document: `commercial_invoice` selects `COMMERCIAL` versus `PROFORMA`, the shipper and recipient become the `seller` and `buyer` parties with contacts, tax ids, and the connection's customer number as `partyIdentification`, and the commodities become `detailedDescription` lines with both net and gross weights.
`invoiceNo` comes from `customs.invoice` or falls back to the shipment `reference`; `reasonForExportation` is always `1000` (permanent export).

Fail-fast checks reject an invoice before any carrier call when the shipper has no tax id, when no invoice number can be resolved, when a party lacks a contact name or phone number, or when a commodity lacks an HS code or origin country.
Registration numbers are not required on the invoice branch.

## Norwegian goods in transit

Norway-to-Norway shipments routed via Sweden or Finland (NVIT) require per-goods-line customs data — trade description, six-digit HS code, net weight, gross weight, and packaging — from 2026-04-01.
The invoice branch carries fields for most of this, but the connector does not yet map per-parcel linkage, split shipments, or return procedure codes; the working record of requirements and gaps is [docs/notes/integration/nvit-customs-facts.md](../notes/integration/nvit-customs-facts.md).

## After booking

A declaration for an already-booked item can be submitted, updated, or deleted through the connector-local declaration proxy, with the caller owning the declaration content.
The [post-booking declaration guide](../guides/customs-declaration-proxy.md) walks through it.
