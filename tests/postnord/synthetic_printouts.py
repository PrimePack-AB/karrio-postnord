"""Synthetic label printouts for the booking-path tests.

Each printout carries only the section markers the connector itself
declares in ``karrio.providers.postnord.stamping.DOCUMENT_SECTIONS`` plus
a line naming it synthetic: no carrier layout, artwork, barcode or
customer data. The classifier and the booking path read section markers
only, so these stand in for the captured printouts, which stay outside
the repository (``local_fixtures``). The stamping-capable CN23 printouts
add the stamping keyword, the signature caption, at a chosen position, and
the ZPL one the signature box beside it.
"""

import base64
import typing

A4_PT = (595.2756, 841.8898)
SYNTHETIC = "Synthetic karrio-postnord test printout"

CN22_PAGE = ("CUSTOMS DECLARATION", "CN22")
CN23_PAGE = ("Customs Declaration", "CN23")
LETTER_LABEL = ("Brev utrikes", "Parcel ID")
TRACKED_LETTER_LABEL = ("PostNord Tracked Letter", "Item-ID")
INTERNATIONAL_PARCEL_LABEL = ("International Parcel", "Item-ID")


def _pdf_string(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})"


# A text run placed at its baseline origin, in bottom-up page points.
TextRun = typing.Tuple[str, float, float]


def _content(
    lines: typing.Sequence[str], runs: typing.Sequence[TextRun] = ()
) -> bytes:
    shows = "".join(
        f"1 0 0 1 72 {760 - 24 * index} Tm {_pdf_string(line)} Tj\n"
        for index, line in enumerate((SYNTHETIC, *lines))
    ) + "".join(
        f"1 0 0 1 {x:.4f} {y:.4f} Tm {_pdf_string(text)} Tj\n" for text, x, y in runs
    )
    return f"BT\n/F1 12 Tf\n{shows}ET\n".encode("latin-1")


def pdf_bytes(
    *pages: typing.Sequence[str],
    runs: typing.Optional[typing.Mapping[int, typing.Sequence[TextRun]]] = None,
) -> bytes:
    """A PDF with one A4 page per entry, each showing its lines as text.

    ``runs`` adds text runs at given positions, keyed by one-based page.
    """
    font = 3
    first_page = 4
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        # Under the font's default StandardEncoding byte 0x27 is a right
        # single quotation mark, so "Sender's" would not extract as typed.
        font: (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        ),
    }
    kids = []
    for index, lines in enumerate(pages):
        page, content = first_page + 2 * index, first_page + 2 * index + 1
        kids.append(f"{page} 0 R")
        stream = _content(lines, (runs or {}).get(index + 1, ()))
        objects[page] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {A4_PT[0]} {A4_PT[1]}] "
            f"/Resources << /Font << /F1 {font} 0 R >> >> "
            f"/Contents {content} 0 R >>"
        ).encode("ascii")
        objects[content] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"endstream"
        )
    objects[2] = (
        f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    ).encode("ascii")

    output = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(output)
        output += f"{number} 0 obj\n".encode("ascii") + objects[number] + b"\nendobj\n"
    xref = len(output)
    size = max(objects) + 1
    output += f"xref\n0 {size}\n0000000000 65535 f \n".encode("ascii")
    for number in range(1, size):
        output += f"{offsets[number]:010d} 00000 n \n".encode("ascii")
    output += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode("ascii")
    return bytes(output)


def pdf_b64(
    *pages: typing.Sequence[str],
    runs: typing.Optional[typing.Mapping[int, typing.Sequence[TextRun]]] = None,
) -> str:
    return base64.b64encode(pdf_bytes(*pages, runs=runs)).decode("utf-8")


def zpl_format(marker: str, text: str) -> str:
    return f"^XA\n^FX {marker}^FS\n^FO50,50\n^A0N,30,30\n^FD{text}^FS\n^XZ"


def zpl_format_with_sections(*sections: typing.Tuple[str, str]) -> str:
    fields = "".join(
        f"^FX {marker}^FS\n^FO50,{50 + 300 * index}\n^A0N,30,30\n^FD{text}^FS\n"
        for index, (marker, text) in enumerate(sections)
    )
    return f"^XA\n{fields}^XZ"


# Export letter, one A4 page composing the label and the CN22.
COMBINED_LABEL_PDF = pdf_b64(LETTER_LABEL + CN22_PAGE)
# Export letter, the tracked letter label on page 1 and the CN22 on page 2.
TWO_PAGE_LABEL_PDF = pdf_b64(TRACKED_LETTER_LABEL, CN22_PAGE)
# International Parcel composed with a CN22 (pre-CN23) and with a CN23.
INTERNATIONAL_PARCEL_CN22_PDF = pdf_b64(INTERNATIONAL_PARCEL_LABEL, CN22_PAGE)
INTERNATIONAL_PARCEL_CN23_PDF = pdf_b64(INTERNATIONAL_PARCEL_LABEL, CN23_PAGE)

# Export letter, one ZPL format carrying both sections.
COMBINED_LABEL_ZPL = zpl_format_with_sections(
    ("SE_INTERNATIONAL_LETTER_LABEL", SYNTHETIC),
    ("CUSTOMS_CN22_ROTATED", "Synthetic CN22 section"),
)
# The CN22 alone, one ZPL format.
LONE_CN22_ZPL = zpl_format("CUSTOMS_CN22_ROTATED", "Synthetic CN22 section")
# International Parcel, a label format followed by an upright CN22 format.
INTERNATIONAL_PARCEL_LABEL_ZPL = zpl_format(
    "NORDIC_SHIPPING_LABEL", SYNTHETIC
) + zpl_format("CUSTOMS_CN22_V2", "Synthetic CN22 section")

# The CN23 signature caption, the stamping seeds' keyword.
CN23_SIGNATURE_KEYWORD = "Sender's signature"

# International Parcel composed with a CN23 whose page 2 carries the
# signature caption as one text run with its baseline origin 60 mm from the
# page's left edge and 200 mm from its top.
CN23_KEYWORD_ORIGIN_MM = (60.0, 200.0)
INTERNATIONAL_PARCEL_CN23_SIGNABLE_PDF = pdf_b64(
    INTERNATIONAL_PARCEL_LABEL,
    CN23_PAGE,
    runs={
        2: [
            (
                CN23_SIGNATURE_KEYWORD,
                CN23_KEYWORD_ORIGIN_MM[0] * 72 / 25.4,
                A4_PT[1] - CN23_KEYWORD_ORIGIN_MM[1] * 72 / 25.4,
            )
        ]
    },
)

# International Parcel in ZPL: a label format, then a CN23 format opened by
# its marker comment between the formats and closed by an end comment after
# the last ^XZ. Each format repeats ^XA after its ^LL1520 header and sets no
# ^PW; the CN23 format carries the signature caption, upright at ^FO263,1445,
# beside a 385 x 30-dot signature box at ^FO448,1440, at 203 dpi.
INTERNATIONAL_PARCEL_CN23_ZPL = (
    "^XA\n^LL1520\n^XA\n"
    "^FX NORDIC_SHIPPING_LABEL^FS\n"
    f"^FWN\n^FO50,50\n^A0N,30,30\n^FD{SYNTHETIC}^FS\n"
    "^XZ\n"
    "^FX CN23_CUSTOMS_DECLARATION^FS\n"
    "^XA\n^LL1520\n^XA\n"
    "^FWN\n^FO50,50\n^A0N,30,30\n^FDSynthetic CN23 section^FS\n"
    f"^FO263,1445\n^A0N,20,20\n^FD{CN23_SIGNATURE_KEYWORD}^FS\n"
    "^FO448,1440\n^GB385,30,1^FS\n"
    "^XZ\n"
    "^FX CN23_CUSTOMS_DECLARATION_END^FS\n"
)
