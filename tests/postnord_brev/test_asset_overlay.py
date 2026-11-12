"""Franking asset overlay geometry tests (PDF conversion placement).

The overlay must place the asset inside the template's slot (x=64 y=6
w=32 h=18 mm, preserveAspectRatio xMaxYMin meet) regardless of the
asset's natural aspect: right-aligned to 96 mm, top-aligned to 6 mm,
fitted by "meet".
"""

import base64
import unittest

from karrio.providers.postnord_brev.label import _asset_overlay

# 100x180 mm in points, as svglib sizes the converted drawing.
PAGE_W, PAGE_H = 283.4646, 510.2362
MM = PAGE_H / 180.0  # == PAGE_W / 100.0
SLOT = (64.0, 6.0, 32.0, 18.0, "xMaxYMin meet")

SLOT_RIGHT = PAGE_W - (100.0 - 96.0) * MM  # x=64+32 = 96 mm
SLOT_TOP = PAGE_H - 6.0 * MM


def _href(width: int, height: int) -> str:
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' "
        f"height='{height}' viewBox='0 0 {width} {height}'>"
        f"<rect width='{width}' height='{height}'/></svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _fitted_box(width: int, height: int):
    group = _asset_overlay(_href(width, height), PAGE_W, PAGE_H, SLOT)
    transform = group.transform
    # svglib rescales unitless px dimensions to points (x0.75), so the
    # drawing's natural size is read from the wrapped drawing, not from the
    # source SVG's declared width/height.
    natural = group.contents[0]
    return (
        transform[4],
        transform[5],
        natural.width * transform[0],
        natural.height * transform[3],
    )


class TestAssetOverlayGeometry(unittest.TestCase):
    def test_square_asset_fills_slot_height_at_top_right(self):
        x, y, w, h = _fitted_box(100, 100)
        # Height-constrained to the 18 mm slot height, flush with the slot's
        # top and right edges.
        self.assertAlmostEqual(h, 18.0 * MM, places=2)
        self.assertAlmostEqual(x + w, SLOT_RIGHT, places=2)
        self.assertAlmostEqual(y + h, SLOT_TOP, places=2)

    def test_wide_asset_anchors_to_slot_top(self):
        x, y, w, h = _fitted_box(200, 100)
        # Width-constrained to the 32 mm slot width; the fitted top edge must
        # hug the slot top (yMin), not drop to the slot bottom.
        self.assertAlmostEqual(w, 32.0 * MM, places=2)
        self.assertAlmostEqual(x + w, SLOT_RIGHT, places=2)
        self.assertAlmostEqual(y + h, SLOT_TOP, places=2)

    def test_tall_asset_anchors_to_slot_right(self):
        x, y, w, h = _fitted_box(100, 200)
        # Height-constrained; the fitted right edge must hug the slot's
        # right edge (xMax).
        self.assertAlmostEqual(h, 18.0 * MM, places=2)
        self.assertAlmostEqual(x + w, SLOT_RIGHT, places=2)
        self.assertAlmostEqual(y + h, SLOT_TOP, places=2)

    def test_extreme_aspect_keeps_unscaled_translation(self):
        # Regression: reportlab composes Group.scale followed by
        # Group.translate so the translation itself is scaled
        # (p -> s * (p + t)); the overlay sets one explicit matrix so a
        # small fit scale cannot shrink the placement origin.
        x, y, w, h = _fitted_box(500, 100)
        self.assertAlmostEqual(x + w, SLOT_RIGHT, places=2)
        self.assertAlmostEqual(y + h, SLOT_TOP, places=2)
