"""PostNord label + CN23 printout: the sandbox capture's markers and seed.

The fixture is the local test-mode capture of the CN23-composition
probe (2026-10-19, docs/notes/sandbox/cn23-composition-sandbox-probe.md
P1): a 91 (International Parcel) SE-to-AL booking whose two-page A4 PDF
printout composes the parcel label on page 1 and the CN23 customs
declaration on page 2, with printoutComposition {cn23: 1, label: 1}. It
is the only CN23 capture in this project or the fork, so it seeds every
CN23 marker and all stamp geometry declared here. ZPL CN23 printouts are
uncaptured: no ZPL markers or seeds exist, and a ZPL label is never
content-verified.
"""

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

        self.assertEqual(set(seeds), _CN22_SEED_KEYS | {"label_cn23/PDF/A4"})
        self.assertIs(seeds["label_cn23/PDF/A4"], postnord_stamping.LABEL_CN23_SEED)

    def test_the_cn23_seed_is_pdf_only(self):
        # No ZPL CN23 printout has been captured, so no ZPL key exists to
        # resolve and the A4 seed does not relax to another paper variant.
        self.assertNotIn("cn23", postnord_stamping.DOCUMENT_SECTIONS["ZPL"])
        self.assertIsNone(stamping._default_registry("postnord/label_cn23/ZPL/*"))
        self.assertIsNone(stamping._default_registry("postnord/label_cn23/PDF/LETTER"))

    def test_sections_declare_the_pdf_cn23_markers(self):
        self.assertEqual(
            postnord_stamping.DOCUMENT_SECTIONS["PDF"]["cn23"], PDF_CN23_TEXT
        )


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
    def test_p1_fixture_classifies_with_both_kinds_and_no_composition(self):
        # The kinds carry the cn23 and label sections, while the SDK
        # classifier itself resolves no composition: its vocabulary is
        # closed to the CN22, so the booking path reads kinds, not
        # composition, for the CN23 content check.
        result = lib.classify_customs_composition(
            _document(P1_FIXTURE, "PDF"), carrier="postnord"
        )

        self.assertEqual(
            result,
            lib.CustomsClassification(
                composition=lib.CustomsComposition.none,
                kinds=("cn23", "label"),
                doc_type=None,
                page=None,
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


class TestLabelCn23Stamp(unittest.TestCase):
    def test_cn23_seed_resolves_to_the_measured_strip(self):
        seed = postnord_stamping.LABEL_CN23_SEED

        self.assertEqual(seed.keyword, CN23_KEYWORD)
        self.assertEqual(seed.revision, 1)
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
