"""PostNord label + CN23 printouts: the captures' markers and seeds.

The PDF fixtures are the local test-mode capture of the CN23-composition
probe (2026-10-19, docs/notes/sandbox/cn23-composition-sandbox-probe.md
P1), a 91 (International Parcel) SE-to-AL booking whose two-page A4 PDF
printout composes the parcel label on page 1 and the CN23 customs
declaration on page 2 (printoutComposition {cn23: 1, label: 1}), and a
second capture of the same layout. It seeds the PDF CN23 markers and the
PDF stamp geometry. The ZPL fixture composes the parcel label format with a
CN23 format and seeds the ZPL CN23 marker and stamp geometry.
"""

import re
import base64
import unittest

import karrio.lib as lib
import karrio.references as references
import karrio.core.utils.stamping as stamping
import karrio.providers.postnord.stamping as postnord_stamping

from postnord import local_fixtures
from postnord.test_label_cn22_stamping import (
    PDF_FIXTURES,
    _document,
    _overlays,
    _page_mm,
    _page_text,
    _pdf_pages,
    _reads_left_to_right,
    _within,
)
from postnord.test_cn22_stamping import _signature_png_b64

P1_FIXTURE = "sandbox/p1-cn23-gateway.printout01.pdf"
CN23_PDF_FIXTURE = "postnord_label_cn23_international_parcel.pdf"
CN23_ZPL_FIXTURE = "postnord_label_cn23_international_parcel.zpl"
P5_LABEL_FIXTURE = "sandbox/p5-no-customs-with-application-raw.printout01.pdf"

CN23_KEYWORD = "Sender's signature"
PDF_CN23_TEXT = ("Customs Declaration", "CN23")
PDF_CERTIFICATION_TEXT = "I certify that the particulars given"

# The keyword run's baseline origin on page 2 of the capture, in
# millimetres from the page top-left (the pypdf text matrix origin).
KEYWORD_ORIGIN_MM = (85.418, 236.211)

# The measured signature strip on page 2, as independent literals: page
# x 109.9-148.0 mm, y 232.2-242.0 mm, right of the caption ink (which ends
# at x 108.63), clear of the faint "/" glyph printed at x 149.9, inside the
# certification cell's rules (divider x 84.33, right rule x 155.62, bottom
# rule y 243.42) and below the certification text's last line.
STRIP_MM = ((109.9, 148.0), (232.2, 242.0))

PAGE_HEIGHT_PT = 841.8898

ZPL_CN23_MARKER = "^FX CN23_CUSTOMS_DECLARATION^FS"
ZPL_CN23_END_MARKER = "^FX CN23_CUSTOMS_DECLARATION_END^FS"

# The ZPL capture's CN23 sign area, in dots, as independent literals: the
# caption field "Sender's signature" at ^FO263,1445, the signature box
# ^FO448,1440 ^GB385,30,1 (x 448-832, y 1440-1469), the certification
# text above it ending by y 1415, and the format's ^LL1520. The stamp is
# 376 x 64 dots at ^FO452,1423, centred on the box's middle row 1455.
ZPL_CAPTION_ORIGIN = (263, 1445)
ZPL_SIGN_BOX = ((448, 832), (1440, 1469))
ZPL_STAMP = (452, 1423, 376, 64)
ZPL_CERTIFICATION_BOTTOM = 1415
ZPL_LABEL_LENGTH = 1520

_CN22_SEED_KEYS = {
    "cn22/PDF/A4",
    "cn22/ZPL/*",
    "label_cn22/PDF/A4",
    "label_cn22/ZPL/*",
}


def _pt(mm: float) -> float:
    return mm * 72.0 / 25.4


def _strip_region():
    """The measured strip in bottom-up page points."""
    (x_lo, x_hi), (y_lo, y_hi) = STRIP_MM
    return _pt(x_lo), _pt(x_hi), PAGE_HEIGHT_PT - _pt(y_hi), PAGE_HEIGHT_PT - _pt(y_lo)


class TestPostnordCn23Registry(unittest.TestCase):
    def test_plugin_metadata_declares_the_cn23_seed(self):
        seeds = references.collect_providers_data()["postnord"].stamp_seeds

        self.assertEqual(
            set(seeds),
            _CN22_SEED_KEYS | {"label_cn23/PDF/A4", "label_cn23/ZPL/*"},
        )
        self.assertIs(seeds["label_cn23/PDF/A4"], postnord_stamping.LABEL_CN23_SEED)
        self.assertIs(seeds["label_cn23/ZPL/*"], postnord_stamping.LABEL_CN23_SEED)

    def test_the_a4_cn23_seed_does_not_leak_to_letter(self):
        self.assertIsNone(stamping._default_registry("postnord/label_cn23/PDF/LETTER"))

    def test_sections_declare_the_cn23_markers(self):
        self.assertEqual(
            postnord_stamping.DOCUMENT_SECTIONS["PDF"]["cn23"], PDF_CN23_TEXT
        )
        self.assertEqual(
            postnord_stamping.DOCUMENT_SECTIONS["ZPL"]["cn23"], ZPL_CN23_MARKER
        )
        self.assertNotIn(ZPL_CN23_MARKER, ZPL_CN23_END_MARKER)


class TestP1Cn23Capture(unittest.TestCase):
    @local_fixtures.required
    def test_p1_fixture_is_a_parcel_label_page_then_a_cn23_page(self):
        document = _document(P1_FIXTURE, "PDF")
        pages = _pdf_pages(document.base64)

        self.assertEqual(len(pages), 2)
        self.assertEqual(_page_mm(pages[0]), (210.0, 297.0))
        self.assertEqual(_page_mm(pages[1]), (210.0, 297.0))
        self.assertIn("International Parcel", _page_text(document.base64, 1))
        self.assertIn("Item-ID", _page_text(document.base64, 1))
        for marker in PDF_CN23_TEXT + (PDF_CERTIFICATION_TEXT, CN23_KEYWORD):
            self.assertNotIn(marker, _page_text(document.base64, 1))
            self.assertIn(marker, _page_text(document.base64, 2))

    @local_fixtures.required
    def test_p1_fixture_classifies_as_a_label_with_a_cn23(self):
        # The SDK classifier knows cn23 as a declaration kind, so the
        # capture resolves to the combined label_cn23 type on page 2.
        result = lib.classify_customs_composition(
            _document(P1_FIXTURE, "PDF"), carrier="postnord"
        )

        self.assertEqual(
            result,
            lib.CustomsClassification(
                composition=lib.CustomsComposition.label_with_declaration,
                kinds=("cn23", "label"),
                doc_type="label_cn23",
                page=2,
            ),
        )

    @local_fixtures.required
    def test_cn23_markers_occur_in_no_cn22_or_bare_label_capture(self):
        for name in (
            P5_LABEL_FIXTURE,
            "postnord_label_cn22_international_parcel.pdf",
            *PDF_FIXTURES,
        ):
            with self.subTest(fixture=name):
                result = lib.classify_customs_composition(
                    _document(name, "PDF"), carrier="postnord"
                )

                self.assertNotIn("cn23", result.kinds)

    @local_fixtures.required
    def test_p1_carries_no_cn22_section(self):
        result = lib.classify_customs_composition(
            _document(P1_FIXTURE, "PDF"), carrier="postnord"
        )

        self.assertNotIn("cn22", result.kinds)


def _zpl_document(name: str):
    return _document(name, "ZPL")


def _zpl_text(document) -> str:
    return base64.b64decode(document.base64).decode("utf-8")


def _stamp_fields(stamped: str):
    return [
        (int(x), int(y), int(total), int(bpr), data)
        for x, y, total, bpr, data in re.findall(
            r"\^FO(\d+),(\d+)\^GFA,(\d+),\d+,(\d+),([0-9A-F]+)\^FS", stamped
        )
    ]


def _ink(field):
    """The label dots a hex ^GFA field prints black."""
    x, y, total, bpr, data = field
    raster = bytes.fromhex(data)
    return [
        (x + column, y + row)
        for row in range(total // bpr)
        for column in range(bpr * 8)
        if raster[row * bpr + column // 8] & (0x80 >> (column % 8))
    ]


class TestCn23Captures(unittest.TestCase):
    @local_fixtures.required
    def test_pdf_capture_shares_the_p1_layout(self):
        document = _document(CN23_PDF_FIXTURE, "PDF")
        pages = _pdf_pages(document.base64)

        self.assertEqual(len(pages), 2)
        self.assertEqual(_page_mm(pages[1]), (210.0, 297.0))
        self.assertEqual(
            lib.classify_customs_composition(document, carrier="postnord"),
            lib.CustomsClassification(
                composition=lib.CustomsComposition.label_with_declaration,
                kinds=("cn23", "label"),
                doc_type="label_cn23",
                page=2,
            ),
        )

        stamped = lib.stamp_document(
            document,
            image=_signature_png_b64(),
            date="2026-10-23",
            carrier="postnord",
            doc_type="label_cn23",
        )
        overlays = _overlays(stamped.base64, 2)

        self.assertEqual(_overlays(stamped.base64, 1), [])
        self.assertEqual(len(overlays), 2)
        for matrix, bounds in overlays:
            self.assertTrue(_reads_left_to_right(matrix))
            _within(self, bounds, _strip_region())

    @local_fixtures.required
    def test_zpl_capture_is_a_label_format_then_a_cn23_format(self):
        stream = _zpl_text(_zpl_document(CN23_ZPL_FIXTURE))
        label, cn23, trailer = stream.split("^XZ")

        self.assertIn("^FX NORDIC_SHIPPING_LABEL^FS", label)
        self.assertNotIn(ZPL_CN23_MARKER, label)
        self.assertTrue(cn23.lstrip().startswith(ZPL_CN23_MARKER))
        self.assertIn("^FO%d,%d\n^FD%s^FS" % (*ZPL_CAPTION_ORIGIN, CN23_KEYWORD), cn23)
        self.assertIn("^FO448,1440\n^GB385,30,1,^FS", cn23)
        self.assertIn("^LL1520", cn23)
        self.assertNotIn("^PW", stream)
        self.assertEqual(trailer.strip(), ZPL_CN23_END_MARKER)

    @local_fixtures.required
    def test_zpl_capture_classifies_as_a_label_with_a_cn23(self):
        self.assertEqual(
            lib.classify_customs_composition(
                _zpl_document(CN23_ZPL_FIXTURE), carrier="postnord"
            ),
            lib.CustomsClassification(
                composition=lib.CustomsComposition.label_with_declaration,
                kinds=("cn23", "label"),
                doc_type="label_cn23",
                page=None,
            ),
        )

    @local_fixtures.required
    def test_zpl_cn23_marker_occurs_in_no_cn22_capture(self):
        for name in (
            "postnord_cn22.zpl",
            "postnord_label_cn22_booking.zpl",
            "postnord_label_cn22_printid.zpl",
            "postnord_label_cn22_international_parcel.zpl",
        ):
            with self.subTest(fixture=name):
                self.assertNotIn(ZPL_CN23_MARKER, _zpl_text(_zpl_document(name)))

    @local_fixtures.required
    def test_seeded_zpl_stamp_lands_in_the_cn23_sign_area(self):
        document = _zpl_document(CN23_ZPL_FIXTURE)
        original = _zpl_text(document)

        stamped = _zpl_text(
            lib.stamp_document(
                document,
                image=_signature_png_b64(),
                date="2026-10-23",
                carrier="postnord",
                doc_type="label_cn23",
            )
        )
        fields = _stamp_fields(stamped)

        self.assertEqual(len(fields), 1)
        field = fields[0]
        x, y, width, height = ZPL_STAMP
        self.assertEqual((field[0], field[1]), (x, y))
        self.assertEqual((field[3] * 8, field[2] // field[3]), (width, height))
        # Spliced before the CN23 format's ^XZ, the stream otherwise intact.
        spliced = re.search(r"\^FO\d+,\d+\^GFA,[^\^]*\^FS", stamped)
        self.assertEqual(stamped[: spliced.start()] + stamped[spliced.end():], original)
        self.assertEqual(stamped[: spliced.start()].count("^XZ"), 1)
        self.assertEqual(stamped[spliced.end():].lstrip().split("\n")[0], "^XZ")

        (box_left, box_right), (box_top, box_bottom) = ZPL_SIGN_BOX
        ink = _ink(field)
        date_ink = [dot for dot in ink if dot[0] < x + width // 2]
        signature_ink = [dot for dot in ink if dot[0] >= x + width // 2]
        self.assertTrue(date_ink)
        self.assertTrue(signature_ink)
        for dot_x, dot_y in ink:
            self.assertGreater(dot_x, box_left)
            self.assertLess(dot_x, box_right)
            self.assertGreater(dot_y, ZPL_CERTIFICATION_BOTTOM)
            self.assertLess(dot_y, ZPL_LABEL_LENGTH)
        # The date stays inside the box; the signature is centred on it.
        for _, dot_y in date_ink:
            self.assertGreater(dot_y, box_top)
            self.assertLess(dot_y, box_bottom)
        signature_rows = [dot_y for _, dot_y in signature_ink]
        self.assertLessEqual(
            abs(min(signature_rows) + max(signature_rows) - (box_top + box_bottom)), 2
        )


class TestLabelCn23Stamp(unittest.TestCase):
    def test_cn23_seed_resolves_to_the_measured_strip(self):
        seed = postnord_stamping.LABEL_CN23_SEED

        self.assertEqual(seed.keyword, CN23_KEYWORD)
        self.assertEqual(seed.revision, 2)
        # The oracle literals come from the measurement, never from the
        # seed object, so a seed change without a re-measurement breaks here.
        self.assertAlmostEqual(
            seed.pdf_keyword_placement.x,
            STRIP_MM[0][0] - KEYWORD_ORIGIN_MM[0],
            places=2,
        )
        self.assertAlmostEqual(
            seed.pdf_keyword_placement.y,
            STRIP_MM[1][0] - KEYWORD_ORIGIN_MM[1],
            places=2,
        )
        self.assertAlmostEqual(
            seed.pdf_keyword_placement.width, STRIP_MM[0][1] - STRIP_MM[0][0], places=2
        )
        self.assertAlmostEqual(
            seed.pdf_keyword_placement.height, STRIP_MM[1][1] - STRIP_MM[1][0], places=2
        )
        self.assertEqual(seed.pdf_keyword_placement.rotation, 0)
        registry = stamping._default_registry("postnord/label_cn23/PDF/A4")
        self.assertEqual(registry.page, 2)
        self.assertAlmostEqual(registry.x, STRIP_MM[0][0], places=1)
        self.assertAlmostEqual(registry.y, STRIP_MM[1][0], places=1)
        self.assertAlmostEqual(registry.width, STRIP_MM[0][1] - STRIP_MM[0][0], places=2)
        self.assertAlmostEqual(
            registry.height, STRIP_MM[1][1] - STRIP_MM[1][0], places=2
        )
        self.assertEqual(registry.rotation, 0)

    def test_zpl_cn23_seed_resolves_to_the_chosen_strip(self):
        # Converted back to dots at 203 dpi, the millimetre geometry is the
        # strip's literal dot offsets from the caption field and its extent.
        geometry = postnord_stamping.LABEL_CN23_SEED.zpl_keyword_frame_placement
        x, y, width, height = ZPL_STAMP

        self.assertEqual(geometry.dpi, 203)
        self.assertEqual(geometry.rotation, 0)
        self.assertEqual(
            tuple(
                round(value * 203 / 25.4)
                for value in (geometry.x, geometry.y, geometry.width, geometry.height)
            ),
            (x - ZPL_CAPTION_ORIGIN[0], y - ZPL_CAPTION_ORIGIN[1], width, height),
        )
        self.assertEqual(width % 8, 0)
        (box_left, box_right), (box_top, box_bottom) = ZPL_SIGN_BOX
        self.assertGreater(x, box_left)
        self.assertLess(x + width, box_right)
        self.assertGreater(y, ZPL_CERTIFICATION_BOTTOM)
        self.assertLessEqual(y + height, ZPL_LABEL_LENGTH)
        self.assertEqual(2 * y + height, box_top + box_bottom + 1)

    @local_fixtures.required
    def test_seeded_stamp_resolves_by_keyword_into_the_free_area(self):
        document = _document(P1_FIXTURE, "PDF")

        stamped = lib.stamp_document(
            document,
            image=_signature_png_b64(),
            date="2026-10-19",
            carrier="postnord",
            doc_type="label_cn23",
        )
        overlays = _overlays(stamped.base64, 2)

        self.assertEqual(len(_pdf_pages(stamped.base64)), 2)
        self.assertEqual(len(overlays), 2)
        for matrix, bounds in overlays:
            self.assertTrue(_reads_left_to_right(matrix))
            _within(self, bounds, _strip_region())
        # The date strip and the signature together span the measured strip.
        self.assertAlmostEqual(min(bounds[0] for _, bounds in overlays), _pt(STRIP_MM[0][0]), places=2)
        self.assertAlmostEqual(max(bounds[1] for _, bounds in overlays), _pt(STRIP_MM[0][1]), places=2)

    @local_fixtures.required
    def test_stamp_leaves_the_label_page_untouched(self):
        document = _document(P1_FIXTURE, "PDF")
        original_label = _pdf_pages(document.base64)[0]["/Contents"].get_object()

        stamped = lib.stamp_document(
            document,
            image=_signature_png_b64(),
            carrier="postnord",
            doc_type="label_cn23",
        )
        stamped_label = _pdf_pages(stamped.base64)[0]["/Contents"].get_object()

        self.assertEqual(_overlays(stamped.base64, 1), [])
        self.assertEqual(stamped_label.get_data(), original_label.get_data())
        self.assertEqual(_page_text(stamped.base64, 2), _page_text(document.base64, 2))


if __name__ == "__main__":
    unittest.main()
