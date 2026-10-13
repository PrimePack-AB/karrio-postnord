---
title: "karrio PostNord"
template: splash
hero:
  tagline: A karrio carrier plugin that books PostNord letters, parcels, and pallets, with customs declarations in the same call.
  actions:
    - text: Products
      link: /karrio-postnord/concepts/products/
    - text: Customs
      link: /karrio-postnord/concepts/customs/
    - text: Development
      link: /karrio-postnord/development/
      variant: secondary
    - text: README on GitHub
      link: https://github.com/PrimePack-AB/karrio-postnord#readme
      variant: minimal
---

## What the connector does

The connector registers with karrio as the `postnord` carrier and books shipments through the PostNord Booking API, printing each label in the same call.
It rates from the connection's service levels (with an opt-in live transit-time enrichment), schedules pickups, tracks items through Track & Trace v7, looks up service points, and embeds the customs structure a service requires — CN22, CN23, or commercial invoice — into every international booking.
The README is the consumer guide to installing, connecting, and booking; this site holds the reference pages behind it.

The connector is fork-coupled: it uses document-stamping SDK fields that exist only in the [Joaqim/karrio](https://github.com/Joaqim/karrio) fork, so a runtime on upstream karrio cannot import it (see [Plugin layout](development/architecture/plugin-layout.md)).

## Concepts

The concept pages explain the connector's service catalog, its rating model, the customs structure selection, label formats, and tracking.

- [Products](concepts/products.md)
- [Rating](concepts/rating.md)
- [Customs](concepts/customs.md)
- [Labels](concepts/labels.md)
- [Tracking](concepts/tracking.md)

## Guides

The guides cover connector-local flows that the unified karrio API does not surface.

- [Post-booking customs declaration](guides/customs-declaration-proxy.md)

## Development

The development pages are for working on the connector itself: setup, tests, and the package layout.

- [Development](development/index.md)
- [Plugin layout](development/architecture/plugin-layout.md)
