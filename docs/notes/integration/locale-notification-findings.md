---
title: "PostNord locale and notification findings"
created: 2026-09-28
---

# PostNord locale and notification findings

*Findings on the booking and tracking locale parameters and the notification additional services.*
*Ported from the fork (Joaqim/karrio, branch docs-openspec): `docs/notes/postnord/locale-notification-findings.md`, created 2026-09-28, last changed 2026-09-28. Vendored-spec line numbers refer to the vendor snapshot in `vendor/`.*

Provenance: extracted from `PRDs/POSTNORD_LOCALE_CONTINUITY.md` on branch `backup-develop-2026-09-24` (last commit `8d98d4b1d`, verification log dated 2026-09-03).
Code references were verified against `develop` at `ecb449c43` on 2026-09-28.

## Open question Q1b: does the Track & Trace locale reach carrier notifications?

The PRD left Q1b open: whether the Track & Trace `locale` query parameter affects only the API response text or also the content of notifications PostNord sends to the end customer.
The only evidence the PRD recorded is the vendored Track & Trace specification, which describes the parameter as "Default is en. Allowed values are en, sv, no, da and fi" (`vendor/track-and-trace-v7-findbyidentifier.swagger.json`); the PRD read this as the display language of the response.
The specification says nothing about notifications, and the PRD's developer-portal check on 2026-09-03 could not fetch further documentation because the portal is a JavaScript shell.
The PRD noted the consequence if the answer is yes: tracking-time locale would then be customer-facing beyond display, which raises the stakes of the poller's locale handling.
No later evidence answering Q1b was found in the backup PRD or in `develop`.

The booking side is documented differently.
The booking `locale` query parameter on all six booking endpoints is described as "The SMS and Email is written in the defined language [sv | da | no | fi | en]" (`vendor/booking.swagger.json`, with the same definition repeated on each booking operation).
The connector's notification options (A2, A3, A4, A9, B8) document that notification language follows this booking `locale` (see the README's shipment options), which addressed the PRD's separate question Q1c about notification-triggering service codes but not Q1b.

## Decision D4: `notifyParty` is not a notification trigger

The PRD placed `notifyParty` out of scope.
The booking specification defines it as the "Party named in the shipping documents as the party to whom a notice of arrival must also be sent", which is shipping-document paperwork semantics rather than a request for PostNord to send SMS or e-mail.
Carrier-sent notifications are requested through additional service codes, not through `notifyParty`.

## Default booking locale: PostNord `sv`, Karrio `en`

PostNord documents `sv` as the default booking locale (booking.swagger.json, `"default": "sv"`).
The PRD's decision Q3/D3 chose `en` instead for consistency with the Track & Trace default, accepting the divergence.
The booking locale resolves as request `options.language`, then connection config `language`, then the recipient country when `locale_by_recipient` is enabled, then `"en"` (`karrio/providers/postnord/shipment/create.py`).
The resolved value is sent lowercase as the query `locale` and uppercased as the body `language` element.
The connection config option also declares `"en"` as its default, and tracking falls back to `"en"` independently (`karrio/providers/postnord/tracking.py`).
Because karrio always sends a locale, PostNord's `sv` default never applies, so a Swedish-market connection that wants Swedish SMS or e-mail must set the config `language` to `sv` or enable `locale_by_recipient`.
