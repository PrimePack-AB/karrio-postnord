---
title: "Products"
---

The connector's product catalog is the PostNord basic service code vocabulary: 32 distinct codes spanning parcel products, letter services, registered mail, and freight.
No PostNord API defines a closed enum for `basicServiceCode` — the booking specification types it as a free-form string — so the catalog was reconciled from a service-code export supplied by PostNord, which remains the authority for names, issuer zones, per-service additional-service compatibility, and country deliverability.

## Families

| Family | Codes (examples) | Notes |
|--------|------------------|-------|
| Parcel products | 17 MyPack Home, 18 Parcel, 19 MyPack Collect, 20 Return Pickup, 24 Return, 30 MyPack Home Small, 11 Home Small | the rated core of the catalog; per-service notification rules apply (see the README's shipment options) |
| International Parcel | 91 Postpaket Utrikes | books a CN23 customs declaration unconditionally (see [Customs](customs.md)) |
| Freight | 52 Pallet | rated, Nordic zone |
| Letters and registered mail | 04, 34, 86, LX, UX, RR, RK, RL, RE, RQ, VV, AF | postal products; customs data rides the CN22 branch |

A service the connector does not list is treated as a parcel product everywhere the connector branches by family.

## Gated letter services

Tracked Letter (34) and Export Letter (UX) are rateable catalog services but are withheld from rate results until the connection opts in.
Both gates are fail-closed: a missing or unreadable toggle leaves the service unavailable.

| Service | Connection config toggle | Additional requirement |
|---------|--------------------------|------------------------|
| Tracked Letter (34) | `offer_tracked_letter` (default `false`) | — |
| Export Letter (UX) | `offer_export_letter` (default `false`) | connection `issuer_code` must be `Z12` |

The other letter and registered-mail products (04, 86, LX, RR, RK, RL, RE, RQ) are offered ungated, with PostNord's booking API as their gate.
The gating rules live in `SERVICE_AVAILABILITY` in `karrio/providers/postnord/units.py` and are enforced by `is_service_available` at rating time.

## Issuer codes

The connection's `issuer_code` names the booking issuer zone: `Z12` Sweden, `Z11` Denmark, `Z13` Norway, `Z14` Finland.
It selects the label language defaults with the booking locale and gates Export Letter to Sweden.
Re-declaration semantics also depend on it: PostNord supports Update and Deletion indicators only for the Swedish issuer Z12 (see the [declaration guide](../guides/customs-declaration-proxy.md)).

## Booking additional services

PostNord's additional-service codes ride the unified shipment options: notification channels (A2 letter, A3 SMS, A4 e-mail, A9 voice, B8 driver), the service-point delivery party (A7), and the entry-code free text (ZDC).
The connector maps these to karrio options and never sends an unmapped additional service by itself; the README's shipment-options table is the complete mapping.
