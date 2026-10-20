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
- [Documentation site](development/architecture/docs-site.md)

## License and affiliation

The connector is copyright 2026 PrimePack AB and distributed under the GNU Lesser General Public License v3.0; see [LICENSE](https://github.com/PrimePack-AB/karrio-postnord/blob/main/LICENSE).
PrimePack AB is not affiliated with, endorsed by, or sponsored by PostNord or any of its subsidiaries, and does not own karrio or have any affiliation with Karrio Inc.
PostNord and karrio are names or trademarks of their respective owners, used only to identify the carrier and the SDK the connector works with.
The PostNord API specifications are not included; the [development guide](development/index.md#api-specifications-and-manuals) cites them and says where to obtain them.
