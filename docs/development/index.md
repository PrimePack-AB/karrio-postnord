---
title: "Development"
---

This section is for working on the connector itself.
The README is the consumer guide; [Plugin layout](architecture/plugin-layout.md) describes how the package registers with karrio and why it is coupled to the karrio fork, and [Documentation site](architecture/docs-site.md) describes how `docs/` is built and published.
Working notes, including the verification records, are indexed in [docs/notes](../notes/README.md).

## Setup

Clone this repository next to a checkout of the [Joaqim/karrio](https://github.com/Joaqim/karrio) fork, create a virtual environment, and install the fork SDK together with the connector:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # -e ../karrio/modules/sdk, fork-coupled
.venv/bin/pip install -e .
```

`requirements-dev.txt` installs the SDK editable from `../karrio/modules/sdk`.
That checkout must be the fork on a ref providing the document-stamping SDK surface that CI checks by import, such as `develop` (last verified at a7355a5c8 on 2026-10-19), because upstream karrio cannot import this plugin (see [Plugin layout](architecture/plugin-layout.md)).
A `git+https` install of the SDK cannot replace the checkout: pip recursively fetches the monorepo's private submodules that `modules/sdk` does not need.

## Tests

Run the suite from the repository root; running it from another directory can resolve a different checkout's provider code first:

```bash
.venv/bin/python -m unittest discover -f -s tests
```

A single test module uses the discover form with a pattern, not a dotted module path — the two label stamping modules import the top-level `postnord` package, which only resolves when discovery runs from `tests`:

```bash
.venv/bin/python -m unittest discover -v -f -s tests -p "test_rate.py"
```

CI (`.github/workflows/tests.yml`) runs the same suite against the fork's `develop` branch, after checking that its SDK provides the document-stamping surface.

## Type checking

`pyright` runs from the repository root with `pyrightconfig.json` (SDK from `../karrio/modules/sdk`, venv `.venv`, Python 3.12).
The tree carries a large pre-existing error baseline inherited from the fork — on the order of a thousand errors, dominated by the generated schemas — so pyright is currently informational, not a gate; CI runs the unittest suite only.
Reducing the baseline is tracked as separate maintenance, not part of feature work.

## Schema generation

The `karrio/schemas/postnord` modules are generated; edit the JSON sources in `schemas/` and regenerate by pointing `ROOT` at the karrio monorepo checkout (the generator rides the monorepo's `bin/cli`):

```bash
ROOT=../karrio ./generate
```

Never edit the generated modules by hand.

## Citing PostNord documentation

The developer guide at <https://guide.developer.postnord.com/> is a JavaScript single-page application, and the PDFs it links return the portal shell to plain fetching.
Cite it by page path and access date (for example "guide.developer.postnord.com, Shipment / Booking / Booking APIs v3 / Book Pickups, accessed 2026-10-13"), and never re-vendor its PDFs.
The vendored API specifications under `vendor/` are a snapshot (2026-09); when PostNord publishes a new spec version, re-vendor deliberately and note the change.
