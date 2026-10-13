---
title: "Rating"
---

PostNord publishes no live money-rate API, so the connector rates statically: the connection's service levels (or a server-side rate sheet) provide the catalog, and rating performs no carrier call by default.
The `DEFAULT_SERVICES` seed in `karrio/providers/postnord/units.py` lists the parcel, freight, international, and gated-letter service levels with catalog-derived country zones; the `rate=0.0` placeholders are overridden by the merchant's negotiated prices at runtime.

## Static rating

Each service level carries a currency, transit days, and one or more zones (country-code lists, or unrestricted for the international letter products).
A rate request resolves the services whose zone covers the recipient country and returns them with the connection's prices.
An explicit `services` filter takes karrio service codes, not PostNord basic service codes.

The gated letter services follow the [product availability rules](products.md#gated-letter-services): 34 and UX are withheld unless their `offer_*` toggle is on, and UX additionally requires the Z12 issuer.

## Transit-time enrichment

The Transit Time API can enrich static rates with live estimates.

| Connection config | Default | Effect |
|-------------------|---------|--------|
| `enable_transit_times` | `false` | Call `GET /rest/transport/v2/transittime/addresstoaddress` per rate request and rewrite `transit_days` and the estimated-delivery metadata from PostNord's answer; services PostNord reports unsupported are dropped |

The enrichment is opt-in because it requires a key subscribed to the Transit Time product (PostNord authorizes API products per key) and because it adds a carrier call to a path that otherwise performs none.
When enabled but unavailable — an unauthorized key, a network failure — rating degrades to the static transit days with a warning message rather than failing.

## No rate call, by design

The default no-carrier-call property keeps rating usable without any API key authorization beyond booking, keeps it fast, and removes a failure mode from the hot path.
Any feature that would add a rating-time carrier call must preserve that default behind an opt-in, as the transit-time enrichment does.
