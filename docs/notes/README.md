---
title: "Working notes"
---

These notes are ephemeral working material, excluded from the published documentation.
Each entry gives the note's purpose, its status, the date it was created, and the date of the last commit that changed it.
An active note is maintained against current evidence; a historical note records a closed loop or an unimplemented design, kept for provenance.

All notes were ported from the Joaqim/karrio fork (branch `docs-openspec`) into this repository on 2026-10-13, which is the last-changed date for every row.
Each note's header carries its fork origin path and the fork-side creation and last-change dates.
Where ported content has since been superseded by connector changes, the note carries a dated "Ported-note update" paragraph rather than a silent edit.
`integration/` holds design, mapping, and fact notes; `sandbox/` holds probe and verification records against PostNord hosts.

| Note | Purpose | Status | Created | Last changed |
|------|---------|--------|---------|--------------|
| [integration/customs-at-booking.md](integration/customs-at-booking.md) | How unified `customs` data becomes the booking's customs structure: branch selection, EU VAT area, invoice field sources, fail-fast errors | active | 2026-09-25 | 2026-10-13 |
| [integration/customs-declaration-proxy.md](integration/customs-declaration-proxy.md) | Guide: submitting a post-booking customs declaration through the connector's declaration proxy | active | 2026-09-28 | 2026-10-13 |
| [integration/customs-declaration-sdk-guide.md](integration/customs-declaration-sdk-guide.md) | How a karrio caller supplies the unified fields that produce a booking-time CN22 | active | 2026-09-28 | 2026-10-13 |
| [integration/locale-notification-findings.md](integration/locale-notification-findings.md) | Booking vs tracking locale semantics, notification additional services, and the `en` default divergence | active | 2026-09-28 | 2026-10-13 |
| [integration/nvit-customs-facts.md](integration/nvit-customs-facts.md) | Norwegian goods-in-transit (NVIT) requirements and the declaration branches' capability against them | active | 2026-09-28 | 2026-10-13 |
| [integration/swagger-ingestion-findings.md](integration/swagger-ingestion-findings.md) | Synthesis of the API-spec ingestion pass: dead ends (cancel), the service-code catalog, and discovered capabilities | active | 2026-06-24 | 2026-10-13 |
| [integration/conformance-ralph-report.md](integration/conformance-ralph-report.md) | Closed measure→fix→commit loop that drove the connector to upstream conformance (4 defects to 0) | historical | 2026-06-24 | 2026-10-13 |
| [integration/credential-verification-design.md](integration/credential-verification-design.md) | Unimplemented design for per-product credential verification probes | historical | 2026-09-28 | 2026-10-13 |
| [sandbox/booking-printout-composition-verification.md](sandbox/booking-printout-composition-verification.md) | Live and sandbox printout captures behind the composed-label (CN22-in-label) stamping design | active | 2026-09-28 | 2026-10-13 |
| [sandbox/customs-declaration-live-verification.md](sandbox/customs-declaration-live-verification.md) | Live verification of booking-time CN22 carriage, the id taxonomy, post-booking declarations, and standalone retrieval | active | 2026-09-21 | 2026-10-13 |
| [sandbox/customs-invoice-live-verification.md](sandbox/customs-invoice-live-verification.md) | Sandbox gate and production probe for the customs-invoice branch (registration-rule outcome, composed invoice) | active | 2026-09-25 | 2026-10-13 |
| [sandbox/pickup-sandbox-probes.md](sandbox/pickup-sandbox-probes.md) | Sandbox probes P1–P2c that shaped the pickup booking request (usage code, service code 0, no consignee) | active | 2026-10-13 | 2026-10-13 |
| [sandbox/zpl-label-encoding.md](sandbox/zpl-label-encoding.md) | Live capture contradicting the swagger's base64-only ZPL encoding, and the connector's normalization | active | 2026-09-03 | 2026-10-13 |
