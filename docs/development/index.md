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

## Releasing

Releases are in-development builds published as GitHub releases of this repository only; nothing is published to PyPI or any other index.
Versions follow CalVer `YYYY.M.N`, where `N` counts releases within the month starting at 1, and each release is tagged `vYYYY.M.N`.

`karrio-ref` under `[tool.primepack]` in `pyproject.toml` names the Joaqim/karrio fork ref a release is tested against.
It must name a fork snapshot tag (`snapshot-YYYY.MM.DD.N`), not `develop` or a commit sha, because `develop` is regenerated and force-pushed and its shas are not durable.
Update it in an ordinary commit before cutting a release that needs a newer fork snapshot.

To cut a release, run the release script from a clean checkout of `main`:

```bash
scripts/release.sh 2026.10.1
```

The script sets the `[project] version`, commits `chore(release): <version>`, creates the annotated tag `v<version>`, and prints the push command without running it.
Pushing the tag triggers `.github/workflows/release.yml`, which checks that the tag matches the `pyproject.toml` version (`scripts/check-release-tag.sh`), runs the SDK surface check and the test suite against the fork at `karrio-ref`, and creates the GitHub release with generated notes naming the required fork snapshot.

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
Cite it by page path and access date (for example "guide.developer.postnord.com, Shipment / Booking / Booking APIs v3 / Book Pickups, accessed 2026-10-13").

PostNord's API specifications and manuals are cited, not committed.
They carry no license permitting redistribution.
PostNord's [General Terms and Conditions for digital integration services](https://developer.postnord.com/pdf/General_Terms_and_Conditions_for_digital_integration_services_from20250613.pdf) (valid from 2025-06-13, retrieved 2026-10-20) state that intellectual property rights in the Services and in "other information and material on PostNord’s websites, are owned by PostNord or other companies within the PostNord Group (or rights holders represented by PostNord)", and grant no rights beyond those expressly stated.
Code, tests, and notes cite a specification by its title and `info.version`, and a manual by its title, using the table below.

### API specifications and manuals

The connector was developed against the documents in this table.
Their SHA-256 digests identify the exact copies used, so a newly downloaded copy can be compared before relying on a claim that cites it.
They were first committed to the Joaqim/karrio fork on 2026-06-24 (Track & Trace v7 FindByIdentifier on 2026-06-29), carried into this repository on 2026-10-13, and removed on 2026-10-20; they remain in this repository's public git history before that removal.

| Local path | Title | Version | SHA-256 |
|------------|-------|---------|---------|
| `vendor/booking.swagger.json` | Booking APIs (Swagger 2.0) | 3.5.29.1 | `e2e90f675741dbadf7b4a9e05bc8ff53eb5008dd65ca7a660e3f8670a41e9ab9` |
| `vendor/assign-items-to-loadcarriers.swagger.json` | Assign Items To LoadCarriers (OpenAPI 3.0.1) | 1.0.1.1 | `34d03a460e135c8c721e8faa90119a9c46c404097278dc17fee023f0e76f07cf` |
| `vendor/delivery-options.swagger.json` | Delivery Options (OpenAPI 3.0.1) | 3.4.3 | `c913d7f16f543c338658d20009c3209beea06ed0244a61afc7e7549542c6d3df` |
| `vendor/servicepoints-v5.swagger.json` | Service Points V5 (OpenAPI 3.0.0) | 5.0.14 | `9850c375dbb395322fa322446f403159e56fa5d300faeec13839090a9cd32462` |
| `vendor/track-and-trace-v7-findbyidentifier.swagger.json` | PostNord Track & Trace API v7 - FindByIdentifier - Public (OpenAPI 3.0.1) | 1.0.1 | `bcbddad79504b35014f51c44f3075e0b5884dc4c75374e973266a4ef17bbacad` |
| `vendor/track-and-trace-v7-findbyreference.swagger.json` | PostNord Track & Trace API v7 - FindByReference - Public (OpenAPI 3.0.1) | 1.0.0 | `cfe7dabc0347bf5b9fd3e13ee88d84c3fe6649332a0f5368b3d130a30d61a128` |
| `vendor/tracking-url.swagger.json` | Track Shipment URL (Swagger 2.0) | 1.0.2 | `1c07923b65177aaa54117a9eb815aeb7676e095d272404952e51b6afe1b9082f` |
| `vendor/transit-time-v1-v2.swagger.json` | Transit time calculation V1 and V2 (OpenAPI 3.0.1) | 2.0.3 | `cd629a5e1c1ba3d74fa1deb89e1301ea568d210e9432091652f91740c5b0a628` |
| `vendor/docs/general-descriptions.pdf` | General Descriptions (EDI shipping instructions message; 32 pages, PDF created 2020-06-12) | none stated | `719c525397c3b7a39515750891f9da68d19958d27c7217b6c67f87bef32e9443` |

The specifications are published on the PostNord developer portal, <https://developer.postnord.com/>, under APIs / Active APIs, where each API's card offers a "Raw Swagger" download.
The portal serves the current version, which can differ from the version in the table; the title and version are in the specification's `info` object.
Where the General Descriptions manual was downloaded from is not recorded.
The developer portal's EDI documentation store held later editions titled "General Description EDI" (v2022.5, v2023.1, v2023.5) when checked on 2026-10-20, none byte-identical to this copy; PostNord customer integration (kundintegration@postnord.com, the contact named in the Delivery Options specification) is the contact for a specific edition.

To keep local copies for development, save them under the local paths in the table.
`vendor/` is listed in `.gitignore`, so the files stay out of commits; check a copy with `sha256sum vendor/booking.swagger.json` against the table.
When PostNord publishes a new specification version, record its title, version, and digest here and reconcile the notes and code comments that cite the earlier version.
