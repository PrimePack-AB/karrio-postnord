"""Synthetic label printouts for the booking-path tests.

Each printout carries only the section markers the connector itself
declares in ``karrio.providers.postnord.stamping.DOCUMENT_SECTIONS`` plus
a line naming it synthetic: no carrier layout, artwork, barcode or
customer data. The classifier and the booking path read section markers
only, so these stand in for the captured printouts, which stay outside
the repository (``local_fixtures``).
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


def _content(lines: typing.Sequence[str]) -> bytes:
    shows = "".join(
        f"1 0 0 1 72 {760 - 24 * index} Tm {_pdf_string(line)} Tj\n"
        for index, line in enumerate((SYNTHETIC, *lines))
    )
    return f"BT\n/F1 12 Tf\n{shows}ET\n".encode("latin-1")


def pdf_bytes(*pages: typing.Sequence[str]) -> bytes:
    """A PDF with one A4 page per entry, each showing its lines as text."""
    font = 3
    first_page = 4
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        font: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids = []
    for index, lines in enumerate(pages):
        page, content = first_page + 2 * index, first_page + 2 * index + 1
        kids.append(f"{page} 0 R")
        stream = _content(lines)
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


def pdf_b64(*pages: typing.Sequence[str]) -> str:
    return base64.b64encode(pdf_bytes(*pages)).decode("utf-8")


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
