# karrio-postnord

## Commands
- Full suite (offline, from repo root only — another directory can resolve a different checkout's provider code first): `.venv/bin/python -m unittest discover -f -s tests` (repair: `.venv/bin/pip install -r requirements-dev.txt && .venv/bin/pip install -e .`)
- Environment note: a shell profiled from the karrio monorepo exports PYTHONPATH containing every fork connector, so `pip show karrio-postnord` can report a phantom 2026.6 from the fork's on-disk egg-info; harmless — imports and the suite resolve to this repo (verified with and without PYTHONPATH). Use `env -u PYTHONPATH .venv/bin/pip ...` when pip metadata must be trusted
- Single module, discover form with a pattern: `.venv/bin/python -m unittest discover -v -f -s tests -p "test_<module>.py"`. The dotted form `python -m unittest tests.postnord.test_rate` does NOT work here: `tests/__init__.py` imports top-level `postnord.*`, which resolves only when discovery runs from `tests`
- Pyright: `.venv/bin/pyright` from repo root — informational only, see baseline below
- Regenerate `karrio/schemas/postnord` after editing `schemas/*.json`: `ROOT=../karrio ./generate` (the generator rides the karrio monorepo checkout's `bin/cli`; never edit generated modules by hand)
- Docs site preview: `DOCS_DIR=$PWD/docs SITE_BASE=/karrio-postnord REPO_URL=https://github.com/PrimePack-AB/karrio-postnord bun run --cwd ../starlight-docs-harness dev` — renders ./docs minus docs/notes/ at http://localhost:4321/karrio-postnord/; publishing is automatic on docs pushes to main via docs-pages

## Fork SDK floor
- The connector is fork-coupled: it uses the document-stamping `PluginMetadata` fields that exist only in the Joaqim/karrio fork's SDK, so upstream karrio cannot import it. `dependencies = ["karrio"]` is plain because no pip-solvable fork ref exists; dev/test/CI run against `-e ../karrio/modules/sdk` (CI pins `FORK_REF` in .github/workflows/tests.yml)
- A git+https SDK install cannot replace the checkout: pip recursively fetches the monorepo's private submodules that modules/sdk does not need

## Pyright baseline
- 1064 errors as of 2026-10-13, pre-existing and inherited from the fork tree (dominated by the generated schemas); CI runs the unittest suite only. Cleanup is a separate task — do not gate feature work on it, and do not add new errors

## Evidence and redaction rules
- Credential VALUES never appear in notes, docs, commits, or output: no `POSTNORD_LIVE_*` or apikey values anywhere (env variable NAMES in prose are fine). Repo-root `.env` holds sandbox-only credentials and is gitignored, with tracked `.env.example` documenting its variable names; live keys remain only in the fork, and `.env` is never printed
- Carve-outs inherited from the seed, accepted at extraction (2026-10-13 review): the live customer number inside the byte-identical `.zpl` label fixtures, the live application id in test files (declared only, never sent — `karrio/providers/postnord/utils.py`), and live-verification artifact ids (printId, bookingId) in docs/notes/sandbox/ are not credentials and stay; the 32-char apikeys are absent from every tracked file
- Captures and probe artifacts are referenced by path or sha only, never embedded
- The sandbox/live evidence suite is deferred: no committed evidence fixtures yet, so published docs pages (anything outside docs/notes/) make no sandbox/live claims — they rest on the API specs and the README. When the suite lands, probes must be env-gated (opt-in env var, like the DHL repo's `DHL_FREIGHT_SWEDEN_SANDBOX` pattern), and every sandbox claim in published docs must cite a committed redacted fixture
- PostNord has no cancel endpoint: test bookings and pickups stay booked; probe deliberately, never retry a rejected step

## Citation rules
- guide.developer.postnord.com is a JavaScript single-page app and its PDFs return the portal shell to plain fetching: cite by page path and access date (e.g. "Shipment / Booking / Booking APIs v3 / Book Pickups, accessed 2026-10-13"), never re-vendor its PDFs
- The vendored specs in vendor/ are a 2026-09 snapshot; they can drift from the live API. When PostNord publishes a new spec version, re-vendor deliberately and note the change — schema regeneration and spec-cited behavior in notes should be reconciled against it

## Code map
- karrio/providers/postnord/units.py — service catalog (32 basic service codes), `DEFAULT_SERVICES` rate-sheet seed, `SERVICE_AVAILABILITY` + `is_service_available` (offer_* letter gates, Z12 issuer rule, fail-closed), `LETTER_SERVICES`, `customs_structure` (CN22/CN23/invoice split), `in_eu_vat_area` (Monaco in; Åland/Canary/Ceuta/Melilla/Büsingen/Heligoland/Mount Athos/Livigno/Campione out; NI via GB-BT prefix), `TrackingStatus` (T&T v7 mapping), notification option enums
- karrio/providers/postnord/shipment/create.py — booking build: customs builders (`_customs_declaration`, `_customs_invoice`), fail-fast customs checks, printout normalization (base64 vs raw ZPL), composed-label verification via stamping.py
- karrio/providers/postnord/stamping.py — `DOCUMENT_SECTIONS` markers and seed geometries for the SDK customs classifier
- karrio/providers/postnord/customs.py — post-booking declaration proxy (digital + PDF variant)
- karrio/providers/postnord/pickup/create.py — pickup split: by item id (`/v3/pickups/ids`, domestic SE/DK/FI) vs pickup booking (`/v3/pickups`, service 0/CR, usage code ADS)
- karrio/providers/postnord/tracking.py — T&T v7 findByIdentifier, link-only degradation on 403
- karrio/providers/postnord/service_points.py, error.py (403 → authorization message), rate.py, utils.py
- karrio/mappers/postnord/mapper.py and karrio/schemas/postnord/* — generated, never edit

## Docs site
- Architecture, link classes, and deferred maintenance: docs/development/architecture/docs-site.md
- Site behavior (mounting, link rewriting, rendering) lives in ../starlight-docs-harness; consume a new harness tag by editing the SHA pin (`# vN.N` comment) in .github/workflows/docs-pages.yml
- Failed builds keep the last deployment serving; do not add required reviewers to the github-pages environment — deploys would pend silently instead of failing
- docs/notes/ holds the ported working notes (fork provenance in each header); it is excluded from the site, and its README.md is the index

## Current State
- 2026-10-13: extracted from the fork's develop union 65468d813 as a standalone plugin (single-root import; the fork retains provenance); version 2026.10
- 2026-10-13: offer_* letter gates restored (34 tracked letter, UX export letter) — fail-closed, UX needs issuer Z12; default rate catalog omits both (deliberate reversal of the fork's cf7ad467a drop)
- 2026-10-13: International Parcel (91) books CN23 unconditionally; the 91 composed-label stamping seeds rest on CN22-era captures and 91 documents pass through unverified pending a CN23 capture
- 2026-10-13: docs/notes ported from the fork (integration/ + sandbox/, index in docs/notes/README.md); Starlight pages distilled without sandbox claims (no committed fixtures yet); docs-pages workflow pins harness v1.3 (6a9f84b)
- Open: cancel blocked pending PostNord's v3 REST reference manual; NVIT per-line customs gaps (see docs/notes/integration/nvit-customs-facts.md); tracking-degrades link-only when the key lacks the T&T product
