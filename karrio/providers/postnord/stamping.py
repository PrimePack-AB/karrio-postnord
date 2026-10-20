"""PostNord document-stamping seeds, declared through the plugin metadata."""

import karrio.lib as lib

# The CN22 "Date and Sender's signature" strip. On the A4 PDF it spans page
# x 53.34-60.96 mm and y 91.44-140.55 mm, encoded as a pre-rotation
# 49.11 x 7.62 mm extent turned 90 degrees clockwise so the stamp reads along
# the form's sideways (^FWR) field stream. On the ZPL form the same strip is an
# offset from the keyword field's ^FO20,35 origin and resolves to ^FO7,303, a
# 61 x 392-dot raster whose bottom edge sits on the form box's bottom rule.
# The two encodings were cross-checked by mapping the PDF form XObject onto
# the ZPL label frame. Revision 3 supersedes an earlier centre-pivot
# measurement whose algebraic conversion swapped the rendered axes.
CN22_SEED = lib.StampSeed(
    placement=lib.StampPlacement(
        x=53.34, y=91.44, width=49.11, height=7.62, rotation=90
    ),
    revision=3,
    keyword="Date and Sender's signature",
    keyword_placement=lib.StampPlacement(
        x=-1.673, y=33.529, width=49.1, height=7.6, rotation=90, dpi=203
    ),
)

# The combined label + CN22 printout carries the CN22 keyword once, either in
# the rotated (^FWR) letter CN22 sharing the label's ZPL format or, for the
# International Parcel (91), in an upright (^FWN) CN22 format of its own.
# Both ZPL layouts anchor on the keyword in its reading frame, from where the
# text starts on its glyph-top edge: the strip starts 33.529 mm along the text
# and 3.4245 mm before that edge, and extends 49.1 x 7.6 mm along the text. On
# the rotated form that is the lone CN22's ^FO7,303 strip; on the upright V2
# form it resolves to ^FO293,758, clear of the keyword text (whose ink ends at
# x 229 in a Labelary render), 12 dots below the certification text's ink and
# 15 dots above the box's bottom rule, within the format's ^LL840.
# PostNord's PDF printout comes in two layouts: one A4 page with the
# CN22 turned beside the label (the by-id capture) and, in the booking
# captures, the label on page 1 and an upright CN22 on page 2. The PDF
# anchors on the keyword, in its reading frame: the strip starts 33.53 mm along
# the text from the keyword run's origin and 5.32 mm above its baseline, and
# extends 49.11 x 7.62 mm along the text. That is the signature strip measured
# on the single-page layout (label x 6.63-67.53, y 302.97-695.44 dots), edge
# aligned with the CN22 box's right and bottom rules. The upright form's box is
# wider and deeper, so there the same strip sits inside the free signature area
# (1.1 mm below the certification text, 2.2 mm above the bottom rule, 18.1 mm
# short of the right rule) rather than on its rules. ``placement`` keeps the
# single-page layout's coordinates. Revision 2 superseded the coordinate-only
# revision 1, which stamped the two-page layout's CN22 across its
# explanation, contents and tariff rows; revision 3 supersedes the label-axis
# ZPL offset of revision 2, which placed the upright CN22's stamp beyond its
# format's ^LL840.
LABEL_CN22_SEED = lib.StampSeed(
    placement=lib.StampPlacement(
        x=53.34, y=91.44, width=49.11, height=7.62, rotation=90
    ),
    revision=3,
    keyword=CN22_SEED.keyword,
    zpl_keyword_frame_placement=lib.StampPlacement(
        x=33.529, y=-3.4245, width=49.1, height=7.6, rotation=0, dpi=203
    ),
    pdf_keyword_placement=lib.StampPlacement(
        x=33.53, y=-5.32, width=49.11, height=7.62, rotation=0
    ),
)

# The CN23 signature strip, measured on the only CN23 capture in this
# project or the fork: the test-mode 2026-10-19 booking whose two-page A4
# PDF composes the International Parcel label on page 1 and the upright
# CN23 on page 2 (the local fixture sandbox/
# p1-cn23-gateway.printout01.pdf, sha256 0b5e7ae9ad4ad90c52554c824ca5a6bb
# 14bc78d64ac31314e4a586b625e65e66, printoutComposition {cn23: 1,
# label: 1}). The certification cell prints its caption as two stacked
# text runs ("Date," above "Sender's signature"), and the SDK locates a
# keyword within a single run, so the keyword is the "Sender's signature"
# run at page (85.418, 236.211) mm. In that run's reading frame the strip
# starts 24.48 mm along the text and 4.01 mm before its baseline (the
# caption's top edge) and extends 38.1 x 9.8 mm: on the page that is x
# 109.9-148.0 and y 232.2-242.0, right of the caption ink (which ends at
# x 108.63), clear of the faint "/" glyph printed at x 149.9, 7.6 mm short
# of the cell's right rule (x 155.62) and 1.42 mm above its bottom rule
# (y 243.42). ``placement`` keeps the capture's absolute page-2
# coordinates. Revision 1 is the first measurement; a PostNord form change
# supersedes it with a higher revision.
LABEL_CN23_SEED = lib.StampSeed(
    placement=lib.StampPlacement(
        x=109.9, y=232.2, width=38.1, height=9.8, page=2
    ),
    revision=1,
    keyword="Sender's signature",
    pdf_keyword_placement=lib.StampPlacement(
        x=24.48, y=-4.01, width=38.1, height=9.8, rotation=0
    ),
)

# A ZPL key resolves the keyword anchor; a PDF key resolves the keyword anchor
# when the seed carries PDF keyword geometry and the coordinate placement
# otherwise, so the lone CN22 PDF stays coordinate-anchored.
STAMP_SEEDS = {
    "cn22/PDF/A4": CN22_SEED,
    "cn22/ZPL/*": CN22_SEED,
    "label_cn22/PDF/A4": LABEL_CN22_SEED,
    "label_cn22/ZPL/*": LABEL_CN22_SEED,
    # PDF-only by evidence: the sole CN23 capture is this PDF printout, and
    # no ZPL CN23 exists to measure a ZPL keyword geometry against, so a
    # label_cn23 ZPL key would anchor stamps on unmeasured geometry.
    "label_cn23/PDF/A4": LABEL_CN23_SEED,
}

# PostNord composes the CN22 and the label into one printout. The export
# letter is a single ZPL format (one ^XZ), and in PDF either one A4 page or, in
# the sandbox booking capture, a label page followed by a CN22 page. The
# International Parcel (91) is two ZPL formats, a parcel label then an upright
# CN22, and in PDF a label page followed by a CN22 page. The sections are told
# apart by PostNord's own ^FX field comments in ZPL and by page text in PDF;
# each template's label markers occur in no CN22 section of any capture. The
# CN23 composes into the PDF the same way since the 2026-10-19 test-mode
# booking (page 2 of the capture above); a ZPL CN23 section has no capture,
# so the cn23 markers are PDF-only and a ZPL cn23 kind never matches.
DOCUMENT_SECTIONS = {
    "ZPL": {
        "cn22": lib.AnyOf(
            "^FX CUSTOMS_CN22_ROTATED^FS",
            "^FX CUSTOMS_CN22_V2^FS",
        ),
        "label": lib.AnyOf(
            "^FX SE_INTERNATIONAL_LETTER_LABEL^FS",
            "^FX NORDIC_SHIPPING_LABEL^FS",
        ),
    },
    "PDF": {
        "cn22": ("CUSTOMS DECLARATION", "CN22"),
        "cn23": ("Customs Declaration", "CN23"),
        "label": lib.AnyOf(
            ("Brev utrikes", "Parcel ID"),
            ("PostNord Tracked Letter", "Item-ID"),
            ("International Parcel", "Item-ID"),
        ),
    },
}
