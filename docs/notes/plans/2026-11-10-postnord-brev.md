---
title: "PostNord Brev (Port Payé): implementation plan"
created: 2026-11-10
---

Implementation plan for the `postnord_brev` carrier, originating in this repository on 2026-11-10.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second, no-API carrier (`postnord_brev`) to this plugin that locally generates the Swedish port payé First Class letter label as SVG.

**Architecture:** A self-contained provider (approach B of the design note): a minimal mapper/proxy pair whose rating rides the universal rating mixin and whose `create_shipment` guards the letter contract, renders a packaged jinja2 template, and returns `ShipmentDetails` with `label_type="SVG"`. No PostNord API is contacted anywhere.

**Tech stack:** Python 3.11+, karrio SDK (fork, unchanged pin), jinja2 (new explicit dependency), unittest.

**Spec:** `docs/notes/integration/postnord-brev-port-paye-design.md` — the plan argues from the spec; executors read both.

## Global constraints

- Repo root is `/home/joaqim/projects/karrio-postnord`; run everything from there.
- Test suite: `.venv/bin/python -m unittest discover -f -s tests` (offline; must end `OK`).
- Pyright baseline is 420 pre-existing errors (`.venv/bin/pyright`); add no new ones.
- Customer-number placeholder in all fixtures: `20000000`. Never real PostNord artwork in any tracked file — the synthetic test asset only.
- The karrio-ref pin (`snapshot-2026.10.23.2`) is untouched; jinja2 is a plain pip dependency.
- After editing `pyproject.toml` entry points, reinstall so discovery sees them: `env -u PYTHONPATH .venv/bin/pip install -e . --no-deps` (the `-u PYTHONPATH` avoids the phantom fork metadata; see CLAUDE.md).
- Delete files with `rip`, never `rm` (PreToolUse hook denies `rm`).
- Documentation prose: one sentence per line, Chicago sentence-case headings, no emojis.
- Label text is hard-coded Swedish; weight always renders in grams.
- Never edit generated modules under `karrio/schemas/` (this carrier adds none).

---

### Task 1: Registrable carrier with static SE rating

**Files:**
- Create: `karrio/providers/postnord_brev/__init__.py` (empty)
- Create: `karrio/providers/postnord_brev/utils.py`
- Create: `karrio/providers/postnord_brev/units.py`
- Create: `karrio/mappers/postnord_brev/__init__.py`
- Create: `karrio/mappers/postnord_brev/settings.py`
- Create: `karrio/mappers/postnord_brev/mapper.py`
- Create: `karrio/mappers/postnord_brev/proxy.py`
- Create: `karrio/plugins/postnord_brev/__init__.py`
- Modify: `pyproject.toml` (entry point only)
- Test: `tests/postnord_brev/__init__.py` (empty), `tests/postnord_brev/fixture.py`, `tests/postnord_brev/test_registration.py`

**Interfaces:**
- Consumes: `karrio.universal.mappers.rating_proxy.RatingMixinProxy` and `RatingMixinSettings`; `karrio.universal.providers.rating.rate_request`/`parse_rate_response` (same imports the fork's `generic` mapper uses).
- Produces: `units.ShippingService.postnord_brev_first_class`, `units.DEFAULT_SERVICES` (one `models.ServiceLevel`), `units.PhoneNumberPolicy`, `units.ConnectionConfig.postnord_phone_number_policy`, `units.resolve_phone_number_policy(payload, settings)`, `Settings` with fields `customer_number`, `franking_asset`, `services`; fixtures `gateway`, `gateway_without(**drop)`, `gateway_with_phone_policy(policy)` used by later tasks' tests.

- [ ] **Step 1: Write the failing tests**

`tests/postnord_brev/fixture.py`:

```python
"""PostNord Brev carrier tests fixtures."""

import base64

import karrio.sdk as karrio


# A tiny synthetic franking asset: real PostNord artwork never enters the
# repository (cite-don't-commit; see the design note).
SyntheticFrankingSvg = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'>"
    "<rect width='10' height='10'/></svg>"
)
SyntheticFrankingAsset = base64.b64encode(SyntheticFrankingSvg.encode()).decode()

_settings = dict(
    id="123456789",
    test_mode=True,
    carrier_id="postnord_brev",
    customer_number="20000000",
    franking_asset=SyntheticFrankingAsset,
)

gateway = karrio.gateway["postnord_brev"].create(dict(_settings))


def gateway_without(**drop):
    """Gateway with top-level settings fields removed, for guard tests."""
    return karrio.gateway["postnord_brev"].create(
        {k: v for k, v in _settings.items() if k not in drop}
    )


def gateway_with_phone_policy(policy):
    """Gateway whose connection config sets postnord_phone_number_policy."""
    return karrio.gateway["postnord_brev"].create(
        dict(_settings, config=dict(postnord_phone_number_policy=policy))
    )
```

`tests/postnord_brev/test_registration.py`:

```python
"""PostNord Brev carrier registration and static rating tests."""

import unittest
from unittest.mock import patch

import karrio.sdk as karrio
import karrio.core.models as models

from .fixture import gateway


RatePayload = dict(
    shipper=dict(
        company_name="A corp.",
        address_line1="125 Church St",
        postal_code="11455",
        city="Stockholm",
        country_code="SE",
    ),
    recipient=dict(
        company_name="B corp.",
        person_name="Jane Doe",
        address_line1="5840 Oak St",
        postal_code="41121",
        city="Göteborg",
        country_code="SE",
    ),
    parcels=[dict(weight=1.0, weight_unit="KG")],
    services=["postnord_brev_first_class"],
)


class TestPostNordBrevRegistration(unittest.TestCase):
    def test_carrier_registers(self):
        self.assertIn("postnord_brev", karrio.gateway.references)
        metadata = karrio.gateway.references["postnord_brev"]
        self.assertEqual(metadata.label, "PostNord Brev (Port Payé)")

    def test_se_lane_offers_the_single_service_without_http(self):
        with patch("karrio.mappers.postnord_brev.proxy.lib.request") as mock:
            rates, messages = (
                karrio.Rating.fetch(models.RateRequest(**RatePayload))
                .from_(gateway)
                .parse()
            )
            mock.assert_not_called()
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates[0].service_code, "postnord_brev_first_class")

    def test_non_se_lane_offers_nothing(self):
        payload = {**RatePayload, "recipient": {**RatePayload["recipient"], "country_code": "NO"}}
        rates, _ = karrio.Rating.fetch(models.RateRequest(**payload)).from_(gateway).parse()
        self.assertEqual(rates, [])
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest discover -v -f -s tests -p "test_registration.py"` from repo root.
Expected: FAIL/ERROR — `postnord_brev` missing from `karrio.gateway.references` (KeyError on gateway creation in the fixture import).

- [ ] **Step 3: Create the carrier packages**

`karrio/providers/postnord_brev/utils.py`:

```python
import karrio.lib as lib
import karrio.core as core


class Settings(core.Settings):
    """PostNord Brev (port payé) connection settings.

    The carrier never contacts PostNord: letters are franked by the sender's
    port payé agreement, so the inputs are the agreement customer number and
    the franking asset rendered onto the label.
    """

    customer_number: str = None
    franking_asset: str = None

    @property
    def carrier_name(self):
        return "postnord_brev"

    @property
    def connection_config(self) -> lib.units.Options:
        from karrio.providers.postnord_brev.units import ConnectionConfig

        return lib.to_connection_config(
            self.config or {},
            option_type=ConnectionConfig,
        )
```

`karrio/providers/postnord_brev/units.py`:

```python
import typing

import karrio.core.models as models
import karrio.lib as lib


class ShippingService(lib.StrEnum):
    """Brev services. The member value is the karrio service code; there is no
    PostNord basicServiceCode because the carrier never calls a PostNord API."""

    postnord_brev_first_class = "postnord_brev_first_class"


class ShippingOption(lib.Enum):
    pass


class PhoneNumberPolicy(lib.StrEnum):
    """Shipper-contact policy on the label, mirroring the postnord carrier's
    postnord_phone_number_policy semantics; unknown values fail safe to
    ``always``."""

    always = "always"
    omit_when_email_suffices = "omit_when_email_suffices"


class ConnectionConfig(lib.Enum):
    postnord_phone_number_policy = lib.OptionEnum(
        "postnord_phone_number_policy", PhoneNumberPolicy
    )


def resolve_phone_number_policy(payload, settings) -> str:
    """Shipper-contact policy: the shipment option wins over the connection
    config; unknown values fail safe to ``always``."""
    option = (payload.options or {}).get("postnord_phone_number_policy")
    config = settings.connection_config.postnord_phone_number_policy.state
    raw = option or config or "always"
    value = str(getattr(raw, "value", raw))
    return value if value in ("always", "omit_when_email_suffices") else "always"


# One letter product in v1: domestic First Class under port payé. The SE-only
# zone is the first layer of the domestic gate: non-SE lanes resolve no rate.
# Prices arrive per-merchant through Karrio's server-side RateSheet, exactly
# as for the postnord carrier; 0.0 is the seed placeholder.
DEFAULT_SERVICES: typing.List[models.ServiceLevel] = [
    models.ServiceLevel(
        service_name="PostNord Brev First Class (Port Payé)",
        service_code="postnord_brev_first_class",
        carrier_service_code=None,
        currency="SEK",
        transit_days=2,
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    )
]
```

`karrio/mappers/postnord_brev/settings.py`:

```python
"""Karrio PostNord Brev client settings."""

import typing

import attr
import jstruct
import karrio.core.models as models
import karrio.providers.postnord_brev.units as provider_units
import karrio.providers.postnord_brev.utils as provider_utils
import karrio.universal.mappers.rating_proxy as rating_proxy


@attr.s(auto_attribs=True)
class Settings(provider_utils.Settings, rating_proxy.RatingMixinSettings):
    """PostNord Brev (port payé) connection settings."""

    customer_number: str = None
    franking_asset: str = None

    # generic properties
    id: str = None
    test_mode: bool = False
    carrier_id: str = "postnord_brev"
    account_country_code: str = "SE"
    metadata: dict = {}
    config: dict = {}

    services: typing.List[models.ServiceLevel] = jstruct.JList[
        models.ServiceLevel, False, dict(default=provider_units.DEFAULT_SERVICES)
    ]  # type: ignore

    @property
    def shipping_services(self) -> typing.List[models.ServiceLevel]:
        services = (
            self.services
            if any(self.services or [])
            else provider_units.DEFAULT_SERVICES
        )
        return services
```

`karrio/mappers/postnord_brev/mapper.py`:

```python
from typing import List, Tuple

from karrio.api.mapper import Mapper as BaseMapper
from karrio.core.models import RateDetails, RateRequest, Message
from karrio.core.utils.serializable import Deserializable, Serializable
from karrio.universal.providers.rating import parse_rate_response, rate_request

from karrio.mappers.postnord_brev.settings import Settings


class Mapper(BaseMapper):
    settings: Settings

    def create_rate_request(self, payload: RateRequest) -> Serializable:
        return rate_request(payload, self.settings)

    def parse_rate_response(
        self, response: Deserializable
    ) -> Tuple[List[RateDetails], List[Message]]:
        return parse_rate_response(response, self.settings)
```

`karrio/mappers/postnord_brev/proxy.py`:

```python
"""Karrio PostNord Brev client proxy."""

import karrio.api.proxy as proxy
import karrio.lib as lib
import karrio.mappers.postnord_brev.settings as provider_settings
from karrio.universal.mappers.rating_proxy import RatingMixinProxy


class Proxy(proxy.Proxy):
    settings: provider_settings.Settings

    def get_rates(self, request: lib.Serializable) -> lib.Deserializable:
        """Static rating only: the brev carrier has no PostNord API to call."""
        return RatingMixinProxy.get_rates(self, request)
```

`karrio/mappers/postnord_brev/__init__.py`:

```python
from karrio.mappers.postnord_brev.mapper import Mapper
from karrio.mappers.postnord_brev.proxy import Proxy
from karrio.mappers.postnord_brev.settings import Settings
```

`karrio/plugins/postnord_brev/__init__.py`:

```python
from karrio.core.metadata import PluginMetadata

from karrio.mappers.postnord_brev.mapper import Mapper
from karrio.mappers.postnord_brev.proxy import Proxy
from karrio.mappers.postnord_brev.settings import Settings
import karrio.providers.postnord_brev.units as units


# Discovered and registered through the karrio.plugins entry point in
# pyproject.toml, beside the postnord plugin.
METADATA = PluginMetadata(
    id="postnord_brev",
    label="PostNord Brev (Port Payé)",
    description=(
        "PostNord domestic First Class letters under a port payé agreement: "
        "local SVG label generation, no PostNord API"
    ),
    # Integrations
    Mapper=Mapper,
    Proxy=Proxy,
    Settings=Settings,
    # Data Units
    is_hub=False,
    services=units.ShippingService,
    options=units.ShippingOption,
    service_levels=units.DEFAULT_SERVICES,
    website="https://www.postnord.se",
)
```

`pyproject.toml` entry-points section becomes:

```toml
[project.entry-points."karrio.plugins"]
postnord = "karrio.plugins.postnord:METADATA"
postnord_brev = "karrio.plugins.postnord_brev:METADATA"
```

- [ ] **Step 4: Reinstall for entry-point discovery and run the tests**

Run: `env -u PYTHONPATH .venv/bin/pip install -e . --no-deps && .venv/bin/python -m unittest discover -v -f -s tests -p "test_registration.py"`.
Expected: 3 tests PASS.

- [ ] **Step 5: Run the full suite and pyright**

Run: `.venv/bin/python -m unittest discover -f -s tests` then `.venv/bin/pyright 2>&1 | tail -1`.
Expected: `OK` (365 + 3 tests); pyright still reports 420 errors.

- [ ] **Step 6: Commit**

```bash
git add karrio/providers/postnord_brev karrio/mappers/postnord_brev karrio/plugins/postnord_brev tests/postnord_brev pyproject.toml
git commit -m "feat: scaffold the postnord_brev carrier with static SE rating"
```

---

### Task 2: Label template and renderer

**Files:**
- Create: `karrio/providers/postnord_brev/templates/label.svg.j2`
- Create: `karrio/providers/postnord_brev/label.py`
- Modify: `pyproject.toml` (jinja2 dependency + package data)
- Test: `tests/postnord_brev/test_label_render.py`

**Interfaces:**
- Consumes: `tests/postnord_brev/fixture.py` (`SyntheticFrankingAsset`).
- Produces: `render_label(shipment, customer_number: str, weight_grams: int, franking_asset_href: str, ship_date: str = None, shipper_contact: str = None) -> str` — Task 3 calls it with an already-guarded `models.ShipmentRequest`, a complete `data:` URI, and a pre-joined contact string.

- [ ] **Step 1: Write the failing tests**

`tests/postnord_brev/test_label_render.py`:

```python
"""PostNord Brev label template rendering tests."""

import unittest

import karrio.core.models as models

from karrio.providers.postnord_brev.label import render_label
from .fixture import SyntheticFrankingAsset


ShipmentPayload = dict(
    shipper=dict(
        company_name="A corp.",
        address_line1="125 Church St",
        postal_code="11455",
        city="Stockholm",
        country_code="SE",
    ),
    recipient=dict(
        company_name="B corp.",
        person_name="Jane Doe",
        address_line1="5840 Oak St",
        address_line2="Lgh 1002",
        postal_code="41121",
        city="Göteborg",
        country_code="SE",
    ),
    parcels=[dict(weight=1.0, weight_unit="KG", reference_number="BREV-001")],
)


class TestBrevLabelRender(unittest.TestCase):
    def setUp(self):
        self.shipment = models.ShipmentRequest(**ShipmentPayload)
        self.href = "data:image/svg+xml;base64," + SyntheticFrankingAsset

    def render(self):
        return render_label(
            self.shipment, "20000000", 1000, self.href, ship_date="2026-11-10"
        )

    def test_renders_swedish_fixed_svg_canvas(self):
        svg = self.render()
        self.assertIn('viewBox="0 0 100 180"', svg)
        self.assertIn("@page { size: 100mm 180mm; margin: 0; }", svg)
        for label_text in ("Avsändare", "Kundnummer", "Vikt", "Datum"):
            self.assertIn(label_text, svg)

    def test_renders_customer_number_parties_weight_and_asset(self):
        svg = self.render()
        self.assertIn("20000000", svg)
        self.assertIn("A corp.", svg)
        self.assertIn("125 Church St", svg)
        self.assertIn("11455 STOCKHOLM", svg)
        self.assertIn("B corp.", svg)
        self.assertIn("Jane Doe", svg)
        self.assertIn("5840 Oak St, Lgh 1002", svg)
        self.assertIn("41121 GÖTEBORG", svg)
        self.assertIn("1000 g", svg)
        self.assertIn("2026-11-10", svg)
        self.assertIn(self.href, svg)

    def test_same_country_recipient_omits_country_line(self):
        svg = self.render()
        # SE == SE, so the recipient block is exactly four lines: company,
        # person, street (with line2), and postcode+city — no country line.
        self.assertEqual(svg.count('<text x="11"'), 4)

    def test_escapes_markup_in_party_input(self):
        payload = {
            **ShipmentPayload,
            "recipient": {
                **ShipmentPayload["recipient"],
                "person_name": "Jane <b>Doe</b>",
            },
        }
        svg = render_label(
            models.ShipmentRequest(**payload), "20000000", 1000, self.href
        )
        self.assertIn("Jane &lt;b&gt;Doe&lt;/b&gt;", svg)

    def test_shipper_contact_line_renders_when_given(self):
        payload = {
            **ShipmentPayload,
            "shipper": {
                **ShipmentPayload["shipper"],
                "email": "avsandare@example.se",
                "phone_number": "+46 70 123 45 67",
            },
        }
        svg = render_label(
            models.ShipmentRequest(**payload),
            "20000000",
            1000,
            self.href,
            shipper_contact="avsandare@example.se · +46701234567",
        )
        self.assertIn("avsandare@example.se · +46701234567", svg)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest discover -v -f -s tests -p "test_label_render.py"`.
Expected: ERROR — `ModuleNotFoundError: No module named 'karrio.providers.postnord_brev.label'`.

- [ ] **Step 3: Add jinja2 and package data to pyproject.toml**

The `[project]` dependencies become:

```toml
dependencies = [
    "karrio",
    "jinja2",
]
```

And add below `[tool.setuptools]`:

```toml
[tool.setuptools.package-data]
"karrio.providers.postnord_brev" = ["templates/*.j2"]
```

Then run `env -u PYTHONPATH .venv/bin/pip install -e . --no-deps && .venv/bin/pip install jinja2`.

- [ ] **Step 4: Write the template and renderer**

`karrio/providers/postnord_brev/templates/label.svg.j2` (the engine template's PART 1, ported: Swedish-fixed, weight and dates passed in, asset always present, phone block and engine-context variables removed):

```jinja2
<style type="text/css">
  @page { size: 100mm 180mm; margin: 0; }
</style>
{#- PostNord Brev (port payé) First Class label: Swedish-fixed, PART 1 only;
    the lower canvas stays clear for PostNord's sorting-code zone. Context:
    shipment, customer_number, weight_grams, franking_asset_href, ship_date,
    stamp. Ported from the engine template per the design note. -#}
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 180" width="100mm" height="180mm"
     preserveAspectRatio="xMinYMin"
     font-family="'Arial Narrow', 'Liberation Sans Narrow', 'Roboto Condensed', Arial, Helvetica, sans-serif"
     style="font-stretch: condensed;">
{%- set s = shipment.shipper -%}
{%- set r = shipment.recipient -%}
{%- set sender_lines = [
      s.company_name or s.person_name,
      ((s.address_line1 or '') ~ (' ' ~ s.street_number if s.street_number else '')) | trim,
      s.address_line2,
      ((s.postal_code or '') ~ ' ' ~ ((s.city or '') | upper)) | trim
    ] | select | list -%}
{%- set recipient_lines = [
      r.company_name,
      r.person_name,
      ((r.address_line1 or '') ~ (' ' ~ r.street_number if r.street_number else '') ~ (', ' ~ r.address_line2 if r.address_line2 else '')) | trim,
      ((r.postal_code or '') ~ ' ' ~ ((r.city or '') | upper)) | trim,
      (r.country_code if r.country_code and r.country_code != s.country_code else None)
    ] | select | list %}
  <g id="part-1" transform="translate(0 0)" fill="#000">

    <!-- Sender -->
    <text x="5" y="9.6" font-size="1.94">Avsändare</text>
    {% for line in sender_lines %}
    <text x="5" y="{{ 12.1 + loop.index0 * 2.45 }}" font-size="2.12" font-weight="bold">{{ line }}</text>
    {% endfor %}

    <!-- Shipper contact (email, phone per policy) -->
    {% if shipper_contact %}
    <text x="5" y="19.6" font-size="1.94">{{ shipper_contact }}</text>
    {% endif %}

    <!-- Franking asset (port payé kliché) as inline data URI: 32 x 18 mm, right-aligned -->
    <image href="{{ franking_asset_href }}" x="64" y="6" width="32" height="18" preserveAspectRatio="xMaxYMin meet"/>

    <!-- Customer number -->
    <text x="38" y="22.6" font-size="1.94">Kundnummer</text>
    <text x="38" y="25.2" font-size="2.82" font-weight="bold">{{ customer_number }}</text>

    <!-- Engine line -->
    <text x="94" y="27.3" font-size="1.76" font-weight="bold" text-anchor="end">PrimePack{% if stamp %} – {{ stamp }}{% endif %}</text>

    <!-- Address window corners -->
    <g fill="none" stroke="#000" stroke-width="1">
      <path d="M4.1 34 V28.5 H9.6"/>
      <path d="M88.6 28.5 H94.1 V34"/>
      <path d="M4.1 57.5 V63 H9.6"/>
      <path d="M88.6 63 H94.1 V57.5"/>
    </g>

    <!-- Vertical tagline (reads top to bottom) -->
    <text transform="translate(95.6 33) rotate(90)" font-size="1.76" font-weight="bold">Fix your Ship — Shipify AB</text>

    <!-- Recipient -->
    {% for line in recipient_lines %}
    <text x="11" y="{{ 42.4 + loop.index0 * 4.7 }}" font-size="4.23" font-weight="bold">{{ line }}</text>
    {% endfor %}

    <!-- Weight / date -->
    <text x="5" y="69.4" font-size="1.94">Vikt</text>
    <text x="5" y="71.8" font-size="2.3" font-weight="bold">{{ weight_grams }} g</text>
    <text x="95" y="69.4" font-size="1.94" text-anchor="end">Datum</text>
    <text x="95" y="71.8" font-size="2.3" font-weight="bold" text-anchor="end">{{ ship_date }}</text>
  </g>
</svg>
```

`karrio/providers/postnord_brev/label.py`:

```python
"""PostNord Brev label rendering.

Renders the Swedish-fixed 100x180 mm SVG label from the packaged jinja2
template. The franking asset is inlined as a base64 data URI so the label
document is self-contained and prints offline.
"""

import datetime
import pathlib

import jinja2

_TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
    keep_trailing_newline=True,
)


def render_label(
    shipment,
    customer_number: str,
    weight_grams: int,
    franking_asset_href: str,
    ship_date: str = None,
    shipper_contact: str = None,
) -> str:
    """Render the brev label SVG for an already-guarded shipment payload."""
    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
    return _env.get_template("label.svg.j2").render(
        shipment=shipment,
        customer_number=customer_number,
        weight_grams=weight_grams,
        franking_asset_href=franking_asset_href,
        ship_date=ship_date or datetime.date.today().isoformat(),
        shipper_contact=shipper_contact,
        stamp=stamp,
    )
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m unittest discover -v -f -s tests -p "test_label_render.py"`.
Expected: 4 tests PASS.

- [ ] **Step 6: Full suite, pyright, commit**

Run: `.venv/bin/python -m unittest discover -f -s tests` (OK) and `.venv/bin/pyright 2>&1 | tail -1` (420).

```bash
git add karrio/providers/postnord_brev tests/postnord_brev/test_label_render.py pyproject.toml
git commit -m "feat: add the postnord_brev svg label template and renderer"
```

---

### Task 3: Local shipment flow and guards

**Files:**
- Create: `karrio/providers/postnord_brev/shipment/__init__.py` (empty)
- Create: `karrio/providers/postnord_brev/shipment/create.py`
- Modify: `karrio/mappers/postnord_brev/mapper.py` (shipment methods)
- Modify: `karrio/mappers/postnord_brev/proxy.py` (create_shipment)
- Test: `tests/postnord_brev/test_shipment.py`

**Interfaces:**
- Consumes: `render_label` from Task 2 (signature above); fixture `gateway`, `gateway_without`.
- Produces: `shipment_request(payload, settings)`, `create_shipment(request, settings)`, `parse_shipment_response(response, settings)` in `karrio.providers.postnord_brev.shipment.create`; guard behavior surfaced as `FieldError` messages through the SDK.

- [ ] **Step 1: Write the failing tests**

`tests/postnord_brev/test_shipment.py`:

```python
"""PostNord Brev local shipment flow and guard tests."""

import base64
import re
import unittest
from unittest.mock import patch

import karrio.sdk as karrio
import karrio.core.models as models

from .fixture import gateway, gateway_without, gateway_with_phone_policy
from .test_label_render import ShipmentPayload


def _create(payload, gw=gateway):
    return karrio.Shipment.create(models.ShipmentRequest(**payload)).from_(gw)


def _errors(response):
    return {
        key
        for message in response.messages
        for key in (message.details or {}).keys()
    }


class TestBrevCreateShipment(unittest.TestCase):
    def test_generates_svg_label_without_http(self):
        with patch("karrio.mappers.postnord_brev.proxy.lib.request") as mock:
            response = _create(dict(ShipmentPayload))
            mock.assert_not_called()
        details = response.shipment
        self.assertEqual(details.label_type, "SVG")
        self.assertEqual(details.carrier_id, "postnord_brev")
        self.assertEqual(details.meta["service_name"], "PostNord Brev First Class (Port Payé)")
        svg = base64.b64decode(details.docs.label).decode()
        self.assertIn('viewBox="0 0 100 180"', svg)
        self.assertIn("20000000", svg)
        self.assertIn("data:image/svg+xml;base64,", svg)
        self.assertIn("1000 g", svg)

    def test_mints_identifier_from_reference_number(self):
        response = _create(dict(ShipmentPayload))
        self.assertEqual(response.shipment.tracking_number, "BREV-001")
        self.assertEqual(response.shipment.shipment_identifier, "BREV-001")

    def test_mints_numeric_identifier_without_reference(self):
        payload = {
            **ShipmentPayload,
            "parcels": [dict(weight=1.0, weight_unit="KG")],
        }
        response = _create(payload)
        self.assertRegex(response.shipment.tracking_number, r"^\d{1,10}$")

    def test_customer_number_metadata_overrides_connection(self):
        payload = {**ShipmentPayload, "metadata": {"postnord_port_paye_customer_number": "12345678"}}
        response = _create(payload)
        svg = base64.b64decode(response.shipment.docs.label).decode()
        self.assertIn("12345678", svg)


class TestBrevGuards(unittest.TestCase):
    def test_missing_customer_number_fails(self):
        response = _create(dict(ShipmentPayload), gateway_without(customer_number=None))
        self.assertIsNone(response.shipment)
        self.assertIn("customer_number", _errors(response))

    def test_non_se_recipient_fails(self):
        payload = {
            **ShipmentPayload,
            "recipient": {**ShipmentPayload["recipient"], "country_code": "NO"},
        }
        response = _create(payload)
        self.assertIn("recipient.country_code", _errors(response))

    def test_non_se_shipper_fails(self):
        payload = {
            **ShipmentPayload,
            "shipper": {**ShipmentPayload["shipper"], "country_code": "DK"},
        }
        response = _create(payload)
        self.assertIn("shipper.country_code", _errors(response))

    def test_multiple_parcels_fail(self):
        payload = {
            **ShipmentPayload,
            "parcels": [dict(weight=0.5, weight_unit="KG"), dict(weight=0.5, weight_unit="KG")],
        }
        response = _create(payload)
        self.assertIn("parcels", _errors(response))

    def test_missing_weight_fails(self):
        payload = {**ShipmentPayload, "parcels": [dict(weight_unit="KG")]}
        response = _create(payload)
        self.assertIn("parcels.weight", _errors(response))

    def test_overweight_fails(self):
        payload = {**ShipmentPayload, "parcels": [dict(weight=2.5, weight_unit="KG")]}
        response = _create(payload)
        self.assertIn("parcels.weight", _errors(response))

    def test_oversize_dimensions_fail(self):
        payload = {
            **ShipmentPayload,
            "parcels": [
                dict(
                    weight=0.5,
                    weight_unit="KG",
                    dimension=dict(length=50, width=40, height=30, unit="CM"),
                )
            ],
        }
        response = _create(payload)
        self.assertIn("parcels.dimension", _errors(response))

    def test_customs_declaration_fails(self):
        payload = {**ShipmentPayload, "customs": dict(content_description="letter goods")}
        response = _create(payload)
        self.assertIn("customs", _errors(response))

    def test_missing_franking_asset_fails(self):
        response = _create(dict(ShipmentPayload), gateway_without(franking_asset=None))
        self.assertIn("franking_asset", _errors(response))

    def test_unsniffable_franking_asset_fails(self):
        import base64 as b64
        bad = b64.b64encode(b"not an image").decode()
        from .fixture import _settings
        gw = karrio.gateway["postnord_brev"].create(dict(_settings, franking_asset=bad))
        response = _create(dict(ShipmentPayload), gw)
        self.assertIn("franking_asset", _errors(response))

    def test_png_franking_asset_renders_png_uri(self):
        import base64 as b64
        png = b64.b64encode(b"\x89PNG\r\n\x1a\nfakepng").decode()
        from .fixture import _settings
        gw = karrio.gateway["postnord_brev"].create(dict(_settings, franking_asset=png))
        response = _create(dict(ShipmentPayload), gw)
        svg = b64.b64decode(response.shipment.docs.label).decode()
        self.assertIn("data:image/png;base64,", svg)

    def test_data_uri_franking_asset_passes_through(self):
        from .fixture import SyntheticFrankingAsset
        from .fixture import _settings
        gw = karrio.gateway["postnord_brev"].create(
            dict(_settings, franking_asset="data:image/svg+xml;base64," + SyntheticFrankingAsset)
        )
        response = _create(dict(ShipmentPayload), gw)
        svg = base64.b64decode(response.shipment.docs.label).decode()
        self.assertIn("data:image/svg+xml;base64," + SyntheticFrankingAsset, svg)


class TestBrevShipperContact(unittest.TestCase):
    def _svg(self, payload, gw=gateway):
        response = _create(payload, gw)
        return base64.b64decode(response.shipment.docs.label).decode()

    def _contact_payload(self, **options):
        return {
            **ShipmentPayload,
            "shipper": {
                **ShipmentPayload["shipper"],
                "email": "avsandare@example.se",
                "phone_number": "+46 70 123 45 67",
            },
            "options": options,
        }

    def test_email_suffices_omits_phone(self):
        svg = self._svg(
            self._contact_payload(postnord_phone_number_policy="omit_when_email_suffices")
        )
        self.assertIn("avsandare@example.se", svg)
        self.assertNotIn("46701234567", svg)

    def test_always_policy_prints_phone_beside_email(self):
        svg = self._svg(self._contact_payload(postnord_phone_number_policy="always"))
        self.assertIn("avsandare@example.se · +46701234567", svg)

    def test_request_option_overrides_connection_config(self):
        payload = self._contact_payload(postnord_phone_number_policy="always")
        svg = self._svg(
            payload, gateway_with_phone_policy("omit_when_email_suffices")
        )
        self.assertIn("46701234567", svg)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest discover -v -f -s tests -p "test_shipment.py"`.
Expected: ERROR/FAIL — the mapper has no shipment methods (attribute error on `create_shipment_request`).

- [ ] **Step 3: Implement the provider flow**

`karrio/providers/postnord_brev/shipment/create.py`:

```python
"""PostNord Brev local shipment creation.

No PostNord API is contacted: the flow guards the port payé letter contract
(Särskilda villkor 1:a-klassbrev inrikes, gäller fr o m 2025-01-01, §1.3 and
the format limits; see the design note), renders the SVG label locally, and
returns shipment details with the provider-forced ``SVG`` label type.
"""

import base64
import binascii
import re
import uuid

import karrio.lib as lib
import karrio.core.models as models

from karrio.providers.postnord_brev.label import render_label
from karrio.providers.postnord_brev.units import resolve_phone_number_policy

WEIGHT_UNIT_GRAMS = {"KG": 1000.0, "G": 1.0, "LB": 453.592, "OZ": 28.3495}
DIMENSION_UNIT_MM = {"CM": 10.0, "M": 1000.0, "IN": 25.4, "MM": 1.0}
MAX_WEIGHT_GRAMS = 2000.0
MAX_LENGTH_PLUS_WIDTH_PLUS_HEIGHT_MM = 900.0

SERVICE_NAME = "PostNord Brev First Class (Port Payé)"
KLICHE_DOWNLOAD = "postnord.se/foretag/forberedelser/klicheer"

PNG_MAGIC = b"\x89PNG"
SVG_MAGICS = (b"<svg", b"<?xml")


def shipment_request(payload, settings):
    """Pass the unified payload through: there is no wire format."""
    return lib.Serializable(payload)


def create_shipment(request, settings):
    """Guard, render, and assemble the local label response."""
    payload = request.serialize()
    _guard(payload, settings)

    parcel = payload.parcels[0]
    tracking_number = parcel.reference_number or str(int(uuid.uuid4().hex[:10], 16))
    customer_number = (payload.metadata or {}).get(
        "postnord_port_paye_customer_number"
    ) or settings.customer_number

    svg = render_label(
        payload,
        customer_number,
        int(round(_weight_grams(parcel))),
        _franking_asset_href(settings.franking_asset),
        shipper_contact=_shipper_contact(payload, settings),
    )

    details = models.ShipmentDetails(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        label_type="SVG",
        tracking_number=tracking_number,
        shipment_identifier=tracking_number,
        meta=dict(service_name=SERVICE_NAME),
        docs=models.Documents(label=lib.to_base64(svg.encode("utf-8"))),
    )
    return lib.Deserializable(details)


def parse_shipment_response(response, settings):
    return response.deserialize(), []


def _weight_grams(parcel) -> float:
    factor = WEIGHT_UNIT_GRAMS.get((parcel.weight_unit or "KG").upper(), 1000.0)
    return float(parcel.weight or 0) * factor


def _shipper_contact(payload, settings):
    """Sender contact line: email always; phone per the policy, mirroring the
    postnord carrier's postnord_phone_number_policy semantics."""
    shipper = payload.shipper
    policy = resolve_phone_number_policy(payload, settings)
    parts = []
    if shipper.email:
        parts.append(shipper.email)
    phone = re.sub(r"[\s-]", "", shipper.phone_number or "")
    if phone and (policy == "always" or not shipper.email):
        parts.append(phone)
    return " · ".join(parts) or None


def _franking_asset_href(asset: str) -> str:
    """Accept a bare base64 string or a full data URI; return a data URI."""
    asset = (asset or "").strip()
    if asset.startswith("data:"):
        return asset
    try:
        decoded = base64.b64decode(asset, validate=True)
    except (binascii.Error, ValueError):
        decoded = b""
    if decoded.startswith(PNG_MAGIC):
        return "data:image/png;base64," + asset
    if any(decoded.startswith(magic) for magic in SVG_MAGICS):
        return "data:image/svg+xml;base64," + asset
    raise lib.exceptions.FieldError(
        {
            "franking_asset": (
                "must be a base64 SVG or PNG kliché (download from "
                + KLICHE_DOWNLOAD
                + ")"
            )
        }
    )


def _guard(payload, settings) -> None:
    errors = {}

    parcels = payload.parcels or []
    if len(parcels) != 1:
        errors["parcels"] = "a brev letter is one mailpiece: exactly one parcel is required"

    parcel = parcels[0] if parcels else None

    if (payload.shipper.country_code or "").upper() != "SE":
        errors["shipper.country_code"] = (
            "postnord_brev is a Swedish domestic service: the shipper country must be SE"
        )
    if (payload.recipient.country_code or "").upper() != "SE":
        errors["recipient.country_code"] = (
            "postnord_brev is a Swedish domestic service: the recipient country must be SE"
        )

    if parcel is not None:
        weight = _weight_grams(parcel)
        if weight <= 0:
            errors["parcels.weight"] = (
                "a declared weight is required: the letter's Vikt prints on the label"
            )
        elif weight > MAX_WEIGHT_GRAMS:
            errors["parcels.weight"] = "a 1:a-klassbrev may weigh at most 2 kg"

        dimension = parcel.dimension
        if dimension and all(
            [dimension.length, dimension.width, dimension.height]
        ):
            mm = DIMENSION_UNIT_MM.get((dimension.unit or "CM").upper(), 10.0)
            total_mm = (
                float(dimension.length)
                + float(dimension.width)
                + float(dimension.height)
            ) * mm
            if total_mm > MAX_LENGTH_PLUS_WIDTH_PLUS_HEIGHT_MM:
                errors["parcels.dimension"] = (
                    "a 1:a-klassbrev may measure at most L+B+T 900 mm"
                )

    if not (
        (payload.metadata or {}).get("postnord_port_paye_customer_number")
        or settings.customer_number
    ):
        errors["customer_number"] = (
            "the port payé customer number is required: it prints as Kundnummer on every label"
        )

    if not (settings.franking_asset or "").strip():
        errors["franking_asset"] = (
            "the franking asset (port payé kliché, base64 SVG or PNG) is required on the connection"
        )

    if payload.customs is not None:
        errors["customs"] = (
            "customs declarations are not applicable to Swedish domestic letters"
        )

    if errors:
        raise lib.exceptions.FieldError(errors)
```

Mapper additions (inside `class Mapper`, below the rate methods; add the new imports at top):

```python
from karrio.core.models import RateDetails, RateRequest, Message, ShipmentDetails, ShipmentRequest
from karrio.providers.postnord_brev import shipment as provider_shipment
```

```python
    def create_shipment_request(self, payload: ShipmentRequest) -> Serializable:
        return provider_shipment.shipment_request(payload, self.settings)

    def parse_shipment_response(
        self, response: Deserializable
    ) -> Tuple[ShipmentDetails, List[Message]]:
        return provider_shipment.parse_shipment_response(response, self.settings)
```

Proxy addition (below `get_rates`):

```python
    def create_shipment(self, request: lib.Serializable) -> lib.Deserializable:
        """Local label generation: no PostNord API is contacted."""
        return provider_shipment.create_shipment(request, self.settings)
```

with the new import at top:

```python
import karrio.providers.postnord_brev.shipment as provider_shipment
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m unittest discover -v -f -s tests -p "test_shipment.py"`.
Expected: all PASS. If `response.messages` shape differs (the fail-safe's `FieldError` conversion), assert against `str(message.message)` containing the field key as fallback and adjust `_errors` accordingly — the field keys themselves are the contract.

- [ ] **Step 5: Full suite, pyright, commit**

Run: `.venv/bin/python -m unittest discover -f -s tests` (OK) and `.venv/bin/pyright 2>&1 | tail -1` (420).

```bash
git add karrio/providers/postnord_brev karrio/mappers/postnord_brev tests/postnord_brev/test_shipment.py
git commit -m "feat: add the postnord_brev local shipment flow and guards"
```

---

### Task 4: Documentation, citations, and repo memory

**Files:**
- Create: `docs/concepts/brev.md`
- Modify: `README.md` (a short section linking the concepts page)
- Modify: `CLAUDE.md` (Code map lines + Current State entry)
- Modify: `docs/development/index.md` (citation-table additions)
- Modify: `docs/notes/integration/postnord-brev-port-paye-design.md` (status line)
- Modify: `docs/notes/README.md` (Last changed for the design note; row for this plan)

**Interfaces:**
- Consumes: the implemented carrier from Tasks 1-3.
- Produces: published documentation; no code.

- [ ] **Step 1: Download the citable documents into vendor/ and record digests**

```bash
curl -L -o vendor/docs/sarskilda-villkor-1a-klassbrev-inrikes.pdf \
  "https://www.postnord.se/siteassets/pdf/ovrigt/villkor/1klb.pdf" || true
```

If that URL 403s or 404s, take the document linked from `postnord.se/foretag/priser-och-villkor/tjanstevillkor-avtalskunder` (page path + access date citation instead), and likewise save `skicka-ratt-med-postnord-20260126.pdf` from `postnord.se/siteassets/pdf/ovrigt/skicka-ratt-med-postnord-20260126.pdf`. Then `sha256sum` each saved file and add table rows: local path `vendor/docs/...`, title, version "none stated", digest, with a sentence noting they were downloaded from the service-terms listing on 2026-11-10 and that live URL discovery is documented in the design note. Do not commit the files — `vendor/` is gitignored.

- [ ] **Step 2: Write docs/concepts/brev.md**

Mirror the frontmatter style of `docs/concepts/products.md` (`title:` frontmatter, `##` sections, one sentence per line). Content, in prose:

- What the carrier is: domestic First Class letters under the sender's port payé agreement, SE→SE, no PostNord API — framed like `docs/concepts/rating.md`'s "No rate call, by design" honesty (label generation is local, by design).
- Connection inputs: `customer_number` (required, prints as Kundnummer), `franking_asset` (required, base64 SVG or PNG kliché; where to download it: the label-blocks page, both language paths, accessed 2026-11-10).
- The purchase flow: fetch rates (local, SE-only zone) then buy; the label returns as SVG with provider-forced `label_type="SVG"`; request-side label types PDF/ZPL/PNG are not produced.
- Limits enforced at purchase: SE↔SE, one parcel, weight required ≤ 2 kg, L+B+T ≤ 900 mm when dimensions are given, customs rejected — each citing the Särskilda villkor title and date, not inline quotes.
- No tracking: "Spårbart: Nej" per the product page; the minted reference number is a shipment identifier, not a PostNord tracking id.
- The customer-number honesty note: the terms require kundnummer on the invoice basis; printing it on the label is this connector's policy.
- Kundnummer metadata override: `postnord_port_paye_customer_number`.

- [ ] **Step 3: README, CLAUDE.md, notes updates**

README: a short "PostNord Brev (Port Payé)" section after the main description — three or four sentences linking to the concepts page, stating the no-API design and the two required connection inputs.

CLAUDE.md Code map: add two lines (mirror the existing style, symbol-focused):
- `karrio/providers/postnord_brev/ — no-API brev carrier: units.py (single service, DEFAULT_SERVICES SE-only zone), shipment/create.py (guards, jinja2 render via label.py, provider-forced SVG), templates/label.svg.j2`
- `karrio/mappers/postnord_brev/, karrio/plugins/postnord_brev/ — minimal mapper (universal rating mixin), local-only proxy, METADATA`

CLAUDE.md Current State: add a dated entry (2026-11-10): the postnord_brev carrier landed — separate plugin, local SVG label, guards per the design note, franking asset consumer-supplied pending the kundintegration answers on reproduction fidelity and redistribution.

Design note status line: change "Status: design settled ... pending the owner's review" to note implementation landed on this branch and only the kundintegration open items remain.

`docs/notes/README.md`: update the design-note row's Last changed, and add a row for this plan (purpose "implementation plan for the postnord_brev carrier", status active).

- [ ] **Step 4: Verify and commit**

Run: `.venv/bin/python -m unittest discover -f -s tests` (OK). Optionally preview the site: `DOCS_DIR=$PWD/docs SITE_BASE=/karrio-postnord REPO_URL=https://github.com/PrimePack-AB/karrio-postnord bun run --cwd ../starlight-docs-harness dev` and confirm the new page renders.

```bash
git add docs README.md CLAUDE.md
git commit -m "docs: document the postnord_brev carrier"
```

---

## Self-review record

Spec coverage: every design-note section maps to a task — architecture and data flow (Tasks 1, 3), guards (Task 3), label contract (Task 2), testing (all tasks' test files), documentation/evidence/citations (Task 4), open items (kundintegration questions remain open by design; nothing in-plan).
Placeholder scan: none; every code step carries full code.
Type consistency: `render_label` signature matches between Task 2 definition and Task 3 call; `shipment_request`/`create_shipment`/`parse_shipment_response` names match between provider and mapper; fixture names (`gateway`, `gateway_without`, `SyntheticFrankingAsset`, `_settings`) are used consistently.
Known risks for executors: the `karrio.gateway.references` metadata attribute shape and the fail-safe `message.details` dict are asserted from research, not from this repo's existing tests — if either assertion fails, fix the test to the SDK's actual shape (the registration and field-key contracts are what must hold, not the accessor spelling), and note it in the commit.
