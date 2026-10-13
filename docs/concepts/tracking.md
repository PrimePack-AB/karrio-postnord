---
title: "Tracking"
---

Tracking uses PostNord Track & Trace v7 `findByIdentifier`, keyed on the PostNord item id — the same value the connector returns as the shipment's `tracking_number`.
The response carries per-item event history, and the connector normalizes it onto karrio's tracking model: events with time, code, description, and location; `signed_by` from the acceptor or signature; and a normalized status.

## Status mapping

Each item carries an `ItemStatus`; the connector maps the thirteen documented values onto karrio statuses in `TrackingStatus` (`karrio/providers/postnord/units.py`), with unmapped or `OTHER` values falling back to `in_transit`.

| karrio status | PostNord `ItemStatus` |
|---------------|-----------------------|
| `delivered` | `DELIVERED` |
| `in_transit` | `EN_ROUTE`, `INFORMED`, `CREATED`, `OTHER` |
| `ready_for_pickup` | `AVAILABLE_FOR_DELIVERY`, `AVAILABLE_FOR_DELIVERY_PAR_LOC` |
| `delivery_delayed` | `DELAYED`, `EXPECTED_DELAY` |
| `delivery_failed` | `DELIVERY_IMPOSSIBLE`, `DELIVERY_REFUSED` |
| `return_to_sender` | `RETURNED` |
| `on_hold` | `STOPPED` |

## Per-product authorization

PostNord authorizes API products per key, so a key may book shipments but lack the Track & Trace product.
When the key is not authorized for tracking, the call returns `403 "Invalid API Key"` and the connector degrades to link-only tracking: the public tracking URL plus a single generic status, no events.
The gateway error parsing turns the 403 envelope into an explicit authorization message, so the degradation is visible in messages rather than silent.

The same per-product model applies to the Transit Time API used by the rating enrichment (see [Rating](rating.md#transit-time-enrichment)).

## Locale

Tracking falls back to `en` independently of the booking locale.
The Track & Trace `locale` parameter selects the response text's language (`en`, `sv`, `no`, `da`, `fi`); whether it reaches carrier-sent notifications is not documented by PostNord.
The booking-side locale — which does drive SMS and e-mail language — is a separate setting; see the README's shipment options.
