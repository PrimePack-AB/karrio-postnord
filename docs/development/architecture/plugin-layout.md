---
title: "Plugin layout"
---

## Registration

The connector registers through the `karrio.plugins` entry point group under the id `postnord` (`[project.entry-points."karrio.plugins"]` in `pyproject.toml`), so installing the package makes the carrier available to every karrio SDK runtime and uninstalling it removes the carrier.
The `METADATA` object in `karrio/plugins/postnord/__init__.py` binds the mapper, proxy, settings, service and option units, and connection configs that the entry point exposes.
Karrio derives the advertised capabilities from the proxy's public methods: `create_shipment` gives shipping, `get_rates` rating, `get_tracking` tracking, `schedule_pickup` pickups.
The connector-local lookups and declarations — `find_service_points`, `create_customs_declaration`, `create_customs_declaration_pdf` — register no capability and are reached directly on the proxy.

A karrio server builds its reference models at boot, so a server deployment restarts the API after installing or upgrading the plugin.
A deployment can also expose the package through the `KARRIO_PLUGINS` directory mount instead of installing it.

## Fork-SDK floor

This connector is fork-coupled: it uses the document-stamping `PluginMetadata` fields that exist only in the [Joaqim/karrio](https://github.com/Joaqim/karrio) fork's SDK, so a runtime on upstream karrio cannot import it.
The package declares a plain `karrio` dependency because no pip-solvable fork reference exists; the karrio the plugin runs against must be a fork checkout providing the stamping SDK surface: `PluginMetadata.stamp_seeds` and `PluginMetadata.document_sections` together with `karrio.lib.StampSeed`, `StampPlacement`, `AnyOf`, `CustomsComposition`, and `classify_customs_composition`.
CI tests against the fork's `develop` branch and checks these names by import in `.github/workflows/tests.yml` before running the suite; `develop` is regenerated, so its commit shas are not durable and the requirement is stated by capability rather than by commit.
Development installs the SDK editable from a sibling checkout (`requirements-dev.txt`).

The stamping surface backs the composed-label verification (see [Labels](../../concepts/labels.md)): the SDK customs classifier and the connector's `stamping.py` section markers and seeds.

## Namespace packages and pyright

At runtime `karrio` is a `pkgutil.extend_path` namespace shared by the SDK and this repository, which pyright cannot follow: the SDK's regular `karrio`, `karrio.providers`, `karrio.mappers`, `karrio.schemas`, and `karrio.plugins` packages would shadow this repository's directories.
The empty `__init__.pyi` files in those five directories make them regular packages for pyright, so imports of both the SDK and the connector resolve.
They have no runtime effect and are excluded from the wheel by `[tool.setuptools.exclude-package-data]`, so an installed connector never shadows the SDK's `karrio/__init__.py`.

## Tree

| Path | Contents |
|------|----------|
| `karrio/mappers/postnord/` | generated `mapper.py`, `proxy.py` (HTTP client), `settings.py` |
| `karrio/providers/postnord/` | connector logic: `units.py` (catalog, gates, customs enums), `rate.py`, `shipment/create.py` (booking, customs builders, fail-fast checks), `shipment/cancel.py`, `pickup/`, `tracking.py`, `customs.py` (declaration proxy), `service_points.py`, `stamping.py`, `error.py`, `utils.py` |
| `karrio/schemas/postnord/` | generated request/response types (never edit; regenerate via `./generate`) |
| `schemas/` | the JSON schema sources the generator reads |
| `tests/postnord/` | the unittest suite and fixtures |
