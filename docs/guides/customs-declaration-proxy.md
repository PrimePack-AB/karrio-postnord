---
title: "Post-booking customs declaration"
---

Submitting a customs declaration for an already-booked PostNord item — after the fact, updating it, or deleting it — goes through the connector's declaration proxy.
The unified karrio API has no customs-declaration operation, so this capability is connector-local, reached via `gateway.proxy.create_customs_declaration` and `gateway.proxy.create_customs_declaration_pdf` (the `find_service_points` precedent).
The full working guide, with the caller conventions and expectations recorded during verification, is [docs/notes/integration/customs-declaration-proxy.md](../notes/integration/customs-declaration-proxy.md); this page is the entry point.

Correctness of the declaration content is the caller's responsibility.
Karrio builds the wire envelope, enforces the envelope constraints, submits, and reports; it does not reconcile, replace, verify, or retract previously submitted declarations.

```
  workflow driver (Python, connector-local)
        │  booked item id + declaration content
        ▼
  customs.customs_declaration_request(declaration, gateway.settings)
        │  validates: ids[] exactly 1, exactly one branch, 13-line limit
        ▼
  gateway.proxy.create_customs_declaration(request)   — or _pdf(request)
        │  POST /rest/shipment/v3/customs/declaration[/pdf]
        ▼
  parse → booking_id, per-id status (OK|FAIL); PDF variant adds documents[]
```

## The declaration object

The envelope is the generated `karrio.schemas.postnord.customs_declaration_request.CustomsDeclarationRequestType`.
Three branches exist, exactly one per request: `customsDeclarationCN22` (the postal CN22 letters book automatically), `customsDeclarationCN23` (adds `postalCharges` and per-item `itemIds`), and `customsInvoice` (adds the `seller`/`buyer`/`shipTo` parties and the `invoice` block).

`ids` carries exactly one entry — the booked item id — with an `idType` such as `ITEMID`.
`updateIndicator` selects `Original`, `Update`, or `Deletion`; omitting it means Original, and Update/Deletion require an existing Original and are not supported for the Danish (Z11), Norwegian (Z13), or Finnish (Z14) issuers.

## Conventions the caller must know

Pass digit-only strings through as strings.
The schema generator annotates digit-only swagger string fields (`partyIdType`, invoice `postalCode`, `reasonForExportation`, `transportModeBorder`, `basicServiceCode`) as `int`, but they travel to PostNord as strings: pass `"160"`, `"1000"`, `"07019010"`, `"02100"` as strings so leading zeros survive.

`BuyerType` is a party union, not a validated variant — one generated class covering the invoice seller, buyer, and ship-to parties.
Populate the fields the specific party needs and leave the others unset; no per-party validation happens client-side.

## What to expect from PostNord

A CN22 without a registration number (EORI, VOEC, or IOSS) is rejected — the same `SACUS-BR-24062502` rule as booking-time carriage, so carry `EORIorPersonalIdNumber` (or `voec`/`ioss`) on every Original.
The digital endpoint's success response is the bare `bookingResponseCN` object (booking id plus per-id status), not a wrapped envelope; the connector's parser reads both shapes.
The PDF variant returns a wrapped envelope plus the rendered, pre-filled declaration in `labelPrintout`, which the connector attaches as a `ShippingDocument`.
A declaration for an item whose EDI booking was never sent is refused ("EDI must have been sent earlier").
