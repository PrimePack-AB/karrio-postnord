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
from PIL import Image, UnidentifiedImageError
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Group, Image as RLImage
from reportlab.pdfbase.pdfmetrics import stringWidth
from svglib.svglib import svg2rlg

_TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
    keep_trailing_newline=True,
)

_SVG_NS = "http://www.w3.org/2000/svg"
_PNG_MAGIC = b"\x89PNG"
_SVG_MAGICS = (b"<svg", b"<?xml")
_X_ANCHORS = {"xMin": 0.0, "xMid": 0.5, "xMax": 1.0}
# The overlay's base position is top-aligned in the slot; the anchor
# multiplies the vertical slack pushing the content DOWN, so yMin (align to
# the slot top) is 0 and yMax (align to the slot bottom) is 1.
_Y_ANCHORS = {"yMin": 0.0, "yMid": 0.5, "yMax": 1.0}

# The shipper contact line starts at x=5 in the sender column and must end
# before the Kundnummer column at x=38, keeping a 1 mm gap. Widths are
# measured in Helvetica, the face svglib draws the PDF in; the SVG's
# preferred condensed faces are narrower, so a fit in Helvetica fits both.
CONTACT_FONT = "Helvetica"
CONTACT_MAX_WIDTH = 32.0
CONTACT_FONT_SIZE = 2.24
CONTACT_MIN_FONT_SIZE = 1.8
_ELLIPSIS = "\u2026"


def render_label(
    shipment,
    customer_number: str,
    weight_grams: int,
    franking_asset_href: str,
    ship_date: Optional[str] = None,
    shipper_contact: Optional[str] = None,
    engine_line: Optional[str] = None,
    tagline: Optional[str] = None,
) -> str:
    """Render the brev label SVG for an already-guarded shipment payload."""
    contact_text, contact_size = (
        fit_contact_line(shipper_contact) if shipper_contact else (None, None)
    )
    return _env.get_template("label.svg.j2").render(
        shipment=shipment,
        customer_number=customer_number,
        weight_grams=weight_grams,
        franking_asset_href=franking_asset_href,
        ship_date=ship_date or datetime.date.today().isoformat(),
        shipper_contact=contact_text,
        shipper_contact_size=contact_size,
        engine_line=engine_line,
        tagline=tagline,
    )


def fit_contact_line(text: str) -> Tuple[str, float]:
    """Fit the contact line to its column: shrink the font down to
    ``CONTACT_MIN_FONT_SIZE``, then ellipsize what still does not fit."""
    width = stringWidth(text, CONTACT_FONT, CONTACT_FONT_SIZE)
    if width <= CONTACT_MAX_WIDTH:
        return text, CONTACT_FONT_SIZE
    size = round(CONTACT_FONT_SIZE * CONTACT_MAX_WIDTH / width, 2)
    if size >= CONTACT_MIN_FONT_SIZE and stringWidth(text, CONTACT_FONT, size) <= CONTACT_MAX_WIDTH:
        return text, size
    size = CONTACT_MIN_FONT_SIZE
    kept = text
    while kept and stringWidth(kept + _ELLIPSIS, CONTACT_FONT, size) > CONTACT_MAX_WIDTH:
        kept = kept[:-1]
    return kept + _ELLIPSIS, size


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
        image = png_image(asset)
        pw, ph = (float(v) for v in image.size)
        # renderPDF draws an Image node only from a PIL image or a file
        # path; any other source (e.g. an ImageReader) raises TypeError.
        content = Group(RLImage(0, 0, pw, ph, image))
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
    # One explicit matrix, not scale() followed by translate(): reportlab
    # composes those calls so the translation itself is scaled
    # (p -> s * (p + t)), which lands the asset at a fraction of its
    # intended origin.
    content.transform = (
        fitted_w / natural_w,
        0.0,
        0.0,
        fitted_h / natural_h,
        origin_x,
        origin_y,
    )
    return content


def _decode_asset(href: str) -> Optional[bytes]:
    payload = href.split(",", 1)[1] if href.startswith("data:") else href
    try:
        return base64.b64decode(payload.strip(), validate=True)
    except (binascii.Error, ValueError):
        return None


def png_image(asset: bytes) -> Image.Image:
    """Decode a PNG asset into a PIL image the PDF renderer can draw.

    renderPDF draws it as an inline image, which carries no alpha channel,
    so transparency is flattened onto white; 16-bit and 32-bit grey are
    scaled to 8 bits rather than clipped, and any other mode becomes RGB.
    Raises ValueError when the bytes are not a decodable PNG.
    """
    if not asset.startswith(_PNG_MAGIC):
        raise ValueError("the asset is not a PNG")
    try:
        image = Image.open(io.BytesIO(asset))
        image.load()
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        SyntaxError,
    ) as error:
        raise ValueError(f"the PNG asset does not decode: {error}") from error
    if image.mode in ("1", "L", "RGB"):
        return image
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        flattened = Image.new("RGB", rgba.size, "white")
        flattened.paste(rgba, mask=rgba.getchannel("A"))
        return flattened
    if image.mode.startswith("I"):
        # PNG grey is at most 16 bits, whichever I mode Pillow opens it as.
        return image.convert("I").point(lambda v: v * (255 / 65535)).convert("L")
    return image.convert("RGB")


def check_franking_asset(asset: bytes) -> None:
    """Raise ValueError unless the PDF conversion can draw this asset.

    Accepts exactly what the label renders: a PNG that ``png_image``
    decodes, or an SVG (starting ``<svg`` or ``<?xml``, as the purchase
    guard sniffs it) that svglib parses into a drawing of positive size.
    Lets a consumer refuse an asset when it is configured instead of at
    booking.
    """
    if asset.startswith(_PNG_MAGIC):
        png_image(asset)
        return
    if not asset.startswith(_SVG_MAGICS):
        raise ValueError("the asset is neither a PNG nor an SVG")
    drawing = _asset_drawing(asset)
    if drawing is None or not (drawing.width > 0 and drawing.height > 0):
        raise ValueError("the SVG asset does not parse into a drawable image")


def _asset_drawing(asset: Optional[bytes]):
    """Vector path: parse an SVG asset into a reportlab drawing."""
    if asset is None or not asset.lstrip().startswith(_SVG_MAGICS):
        return None
    try:
        return svg2rlg(io.BytesIO(asset))
    except Exception:
        return None


def _parse_aspect(aspect: str) -> Tuple[float, float]:
    """Anchors in (x, y) order from a preserveAspectRatio meet rule.

    The SVG tokens capitalize the Y axis (xMaxYMin meet), so the match is
    case-insensitive; an unparsable rule centers on both axes.
    """
    rule = aspect.lower()
    x_anchor = next((v for k, v in _X_ANCHORS.items() if k.lower() in rule), 0.5)
    y_anchor = next((v for k, v in _Y_ANCHORS.items() if k.lower() in rule), 0.5)
    return x_anchor, y_anchor
