"""PostNord Brev label rendering.

Renders the Swedish-fixed 100x180 mm SVG label from the packaged jinja2
template. The franking asset is inlined as a base64 data URI so the label
document is self-contained and prints offline.

``svg_to_pdf`` converts that SVG to PDF with svglib/reportlab, which are
pure Python (no system cairo or fonts), so the conversion runs identically
in every deployment target. svglib cannot load data-URI images, so the
template's ``<image>`` node is removed before conversion and the asset is
drawn into its slot as native vector (SVG asset) or raster (PNG asset)
geometry; the slot rect and aspect rule are read from the template node,
keeping the template the single source of the label geometry.
"""

import base64
import binascii
import datetime
import io
import pathlib
from typing import Optional, Tuple

import jinja2
from lxml import etree
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Group, Image as RLImage
from reportlab.lib.utils import ImageReader
from svglib.svglib import svg2rlg

_TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
    keep_trailing_newline=True,
)

_SVG_NS = "http://www.w3.org/2000/svg"
_PNG_MAGIC = b"\x89PNG"
_X_ANCHORS = {"xMin": 0.0, "xMid": 0.5, "xMax": 1.0}
_Y_ANCHORS = {"yMin": 1.0, "yMid": 0.5, "yMax": 0.0}


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


def svg_to_pdf(svg: str, franking_asset_href: str) -> bytes:
    """Convert a rendered brev label SVG to a one-page PDF document."""
    root = etree.fromstring(svg.encode("utf-8"))
    slot = _strip_image_slot(root)
    drawing = svg2rlg(io.StringIO(etree.tostring(root).decode("utf-8")))
    if drawing is None:
        raise ValueError("the label template did not parse for PDF conversion")
    if slot is not None:
        drawing.add(_asset_overlay(franking_asset_href, drawing.width, drawing.height, slot))
    buffer = io.BytesIO()
    renderPDF.drawToFile(drawing, buffer)
    return buffer.getvalue()


def _strip_image_slot(root) -> Optional[Tuple[float, float, float, float, str]]:
    """Remove the template's franking ``<image>`` node; return its slot.

    The slot is (x, y, width, height) in viewBox units plus the node's
    preserveAspectRatio rule.
    """
    for node in root.iter(f"{{{_SVG_NS}}}image"):
        slot = (
            float(node.get("x", "0")),
            float(node.get("y", "0")),
            float(node.get("width", "0")),
            float(node.get("height", "0")),
            node.get("preserveAspectRatio", "xMidYMid meet"),
        )
        node.getparent().remove(node)
        return slot
    return None


def _asset_overlay(href: str, page_width: float, page_height: float, slot) -> Group:
    """Draw the franking asset into its slot as native PDF geometry."""
    x, y, width, height, aspect = slot
    scale = page_height / 180.0 if page_height else page_width / 100.0
    slot_w, slot_h = width * scale, height * scale
    asset = _decode_asset(href)
    drawing = _asset_drawing(asset)
    if drawing is not None:
        content = Group(drawing)
        natural_w, natural_h = drawing.width, drawing.height
    elif asset is not None and asset.startswith(_PNG_MAGIC):
        reader = ImageReader(io.BytesIO(asset))
        pw, ph = (float(v) for v in reader.getSize())
        content = Group(RLImage(0, 0, pw, ph, reader))
        natural_w, natural_h = pw, ph
    else:
        # The purchase guard already rejects undecodable assets; an asset
        # that yields no geometry renders an empty slot.
        return Group()
    fitted_w = min(slot_w, slot_h * natural_w / natural_h)
    fitted_h = min(slot_h, slot_w * natural_h / natural_w)
    x_anchor, y_anchor = _parse_aspect(aspect)
    origin_x = x * scale + (slot_w - fitted_w) * x_anchor
    origin_y = page_height - (y * scale + fitted_h) + (slot_h - fitted_h) * y_anchor
    content.scale(fitted_w / natural_w, fitted_h / natural_h)
    content.translate(origin_x, origin_y)
    return content


def _decode_asset(href: str) -> Optional[bytes]:
    payload = href.split(",", 1)[1] if href.startswith("data:") else href
    try:
        return base64.b64decode(payload.strip(), validate=True)
    except (binascii.Error, ValueError):
        return None


def _asset_drawing(asset: Optional[bytes]):
    """Vector path: parse an SVG asset into a reportlab drawing."""
    if asset is None or not asset.lstrip().startswith((b"<svg", b"<?xml")):
        return None
    try:
        return svg2rlg(io.BytesIO(asset))
    except Exception:
        return None


def _parse_aspect(aspect: str) -> Tuple[float, float]:
    """Anchors in (x, y) order from a preserveAspectRatio meet rule."""
    x_anchor = next((v for k, v in _X_ANCHORS.items() if k in aspect), 0.5)
    y_anchor = next((v for k, v in _Y_ANCHORS.items() if k in aspect), 0.5)
    return x_anchor, y_anchor
