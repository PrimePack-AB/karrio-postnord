"""PostNord Brev label rendering.

Renders the Swedish-fixed 100x180 mm SVG label from the packaged jinja2
template. The franking asset is inlined as a base64 data URI so the label
document is self-contained and prints offline.
"""

import datetime
import pathlib
from typing import Optional

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
    ship_date: Optional[str] = None,
    shipper_contact: Optional[str] = None,
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
