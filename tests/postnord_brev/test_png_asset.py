"""PNG franking asset tests: the raster path of the PDF conversion.

The PNG asset is drawn as an image on the label page, so these tests
read the page's images back rather than trusting a non-empty PDF.
"""

import base64
import io
import unittest

import pypdf
import karrio.core.models as models
import karrio.sdk as karrio

from karrio.providers.postnord_brev.label import (
    check_franking_asset,
    render_label,
    svg_to_pdf,
)
from .fixture import SyntheticFrankingSvg, gateway_with_asset, synthetic_png
from .test_label_render import ShipmentPayload


def _page_images(pdf: bytes):
    return pypdf.PdfReader(io.BytesIO(pdf)).pages[0].images


def _label_pdf(asset: str) -> bytes:
    href = "data:image/png;base64," + asset
    shipment = models.ShipmentRequest(**ShipmentPayload)
    svg = render_label(shipment, "20000000", 1000, href)
    return svg_to_pdf(svg, href)


class TestPngAssetLabelRender(unittest.TestCase):
    def test_png_asset_is_drawn_on_the_page(self):
        images = _page_images(_label_pdf(synthetic_png("L", (69, 39))))
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].image.size, (69, 39))

    def test_png_modes_render(self):
        for mode, color in [
            ("1", 0),
            ("L", 0),
            ("LA", (0, 255)),
            ("P", 0),
            ("RGB", (0, 0, 0)),
            ("RGBA", (0, 0, 0, 255)),
            ("I;16", 0),
        ]:
            with self.subTest(mode=mode):
                images = _page_images(_label_pdf(synthetic_png(mode, (8, 6), color)))
                self.assertEqual(len(images), 1)

    def test_transparent_png_pixels_print_white(self):
        # Inline PDF images carry no alpha, so transparent pixels must be
        # flattened onto white rather than printing their RGB channels.
        asset = synthetic_png("RGBA", (8, 6), (0, 0, 0, 0))
        image = _page_images(_label_pdf(asset))[0].image.convert("L")
        self.assertEqual(image.getextrema(), (255, 255))

    def test_sixteen_bit_png_keeps_its_tones(self):
        # A 16-bit mid-grey must not clip to white on the way to 8 bits.
        asset = synthetic_png("I;16", (8, 6), 32768)
        image = _page_images(_label_pdf(asset))[0].image.convert("L")
        low, high = image.getextrema()
        self.assertTrue(100 < low <= high < 160, (low, high))

    def test_undecodable_png_raises_instead_of_an_empty_slot(self):
        truncated = base64.b64decode(synthetic_png("L", (69, 39)))[:40]
        with self.assertRaises(ValueError):
            _label_pdf(base64.b64encode(truncated).decode())


class TestCheckFrankingAsset(unittest.TestCase):
    def test_accepts_drawable_png_and_svg(self):
        check_franking_asset(base64.b64decode(synthetic_png("RGBA", (8, 6))))
        check_franking_asset(SyntheticFrankingSvg.encode())

    def test_refuses_what_the_label_cannot_draw(self):
        png = base64.b64decode(synthetic_png("L", (69, 39)))
        for name, asset in [
            ("truncated png", png[:40]),
            ("png magic then garbage", b"\x89PNG\r\n\x1a\nfakepng"),
            ("not an image", b"not an image"),
            ("jpeg", b"\xff\xd8\xff\xe0" + b"\x00" * 16),
            ("malformed svg", b"<svg xmlns='http://www.w3.org/2000/svg'><rect"),
            ("zero-size svg", b"<svg xmlns='http://www.w3.org/2000/svg' width='0' height='0'/>"),
        ]:
            with self.subTest(name), self.assertRaises(ValueError):
                check_franking_asset(asset)

    def test_refuses_a_decompression_bomb(self):
        # 20000 x 20000 one-bit pixels compress to a few kilobytes but exceed
        # Pillow's decompression bomb limit, which raises its own error type.
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("1", (20000, 20000)).save(buffer, "PNG")
        with self.assertRaises(ValueError):
            check_franking_asset(buffer.getvalue())


class TestPngAssetShipment(unittest.TestCase):
    def test_png_asset_books_a_pdf_label(self):
        gw = gateway_with_asset(synthetic_png("L", (69, 39)))
        details, messages = (
            karrio.Shipment.create(models.ShipmentRequest(**dict(ShipmentPayload)))
            .from_(gw)
            .parse()
        )
        self.assertEqual(messages, [])
        self.assertEqual(details.label_type, "PDF")
        pdf = base64.b64decode(details.docs.label)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(len(_page_images(pdf)), 1)
