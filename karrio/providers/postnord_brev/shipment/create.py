"""PostNord Brev local shipment creation.

No PostNord API is contacted: the flow guards the port payé letter contract
(Särskilda villkor 1:a-klassbrev inrikes, gäller fr o m 2025-01-01, §1.3 and
the format limits; see the design note), renders the SVG label locally, and
returns shipment details with the provider-forced ``SVG`` label type.
"""

import base64
import binascii
import re
import uuid

import karrio.lib as lib
import karrio.core.models as models

from karrio.providers.postnord_brev.label import render_label
from karrio.providers.postnord_brev.units import resolve_phone_number_policy

WEIGHT_UNIT_GRAMS = {"KG": 1000.0, "G": 1.0, "LB": 453.592, "OZ": 28.3495}
DIMENSION_UNIT_MM = {"CM": 10.0, "M": 1000.0, "IN": 25.4, "MM": 1.0}
MAX_WEIGHT_GRAMS = 2000.0
MAX_LENGTH_PLUS_WIDTH_PLUS_HEIGHT_MM = 900.0

SERVICE_NAME = "PostNord Brev First Class (Port Payé)"
KLICHE_DOWNLOAD = "postnord.se/foretag/forberedelser/klicheer"

PNG_MAGIC = b"\x89PNG"
SVG_MAGICS = (b"<svg", b"<?xml")


def shipment_request(payload, settings):
    """Pass the unified payload through: there is no wire format."""
    return lib.Serializable(payload)


def create_shipment(request, settings):
    """Guard, render, and assemble the local label response."""
    payload = request.serialize()
    _guard(payload, settings)

    parcel = payload.parcels[0]
    # Not a PostNord id: the uuid-derived fallback mirrors the generic
    # carrier's minting scheme and satisfies ShipmentDetails' identifier.
    tracking_number = parcel.reference_number or f"{int(uuid.uuid4().hex[:10], 16) % 10**10:010d}"
    customer_number = (payload.metadata or {}).get(
        "postnord_port_paye_customer_number"
    ) or settings.customer_number

    svg = render_label(
        payload,
        customer_number,
        int(round(_weight_grams(parcel))),
        _franking_asset_href(settings.franking_asset),
        shipper_contact=_shipper_contact(payload, settings),
    )

    details = models.ShipmentDetails(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        label_type="SVG",
        tracking_number=tracking_number,
        shipment_identifier=tracking_number,
        meta=dict(service_name=SERVICE_NAME),
        docs=models.Documents(
            label=base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        ),
    )
    return lib.Deserializable(details)


def parse_shipment_response(response, settings):
    return response.deserialize(), []


def _weight_grams(parcel) -> float:
    factor = WEIGHT_UNIT_GRAMS.get((parcel.weight_unit or "KG").upper(), 1000.0)
    return float(parcel.weight or 0) * factor


def _shipper_contact(payload, settings):
    """Sender contact line: email always; phone per the policy, mirroring the
    postnord carrier's postnord_phone_number_policy semantics."""
    shipper = payload.shipper
    policy = resolve_phone_number_policy(payload, settings)
    parts = []
    if shipper.email:
        parts.append(shipper.email)
    phone = re.sub(r"[\s-]", "", shipper.phone_number or "")
    if phone and (policy == "always" or not shipper.email):
        parts.append(phone)
    return " · ".join(parts) or None


def _franking_asset_href(asset: str) -> str:
    """Accept a bare base64 string or a full data URI; return a data URI."""
    asset = (asset or "").strip()
    if asset.startswith("data:"):
        return asset
    try:
        decoded = base64.b64decode(asset, validate=True)
    except (binascii.Error, ValueError):
        decoded = b""
    if decoded.startswith(PNG_MAGIC):
        return "data:image/png;base64," + asset
    if any(decoded.startswith(magic) for magic in SVG_MAGICS):
        return "data:image/svg+xml;base64," + asset
    raise lib.exceptions.FieldError(
        {
            "franking_asset": (
                "must be a base64 SVG or PNG kliché (download from "
                + KLICHE_DOWNLOAD
                + ")"
            )
        }
    )


def _guard(payload, settings) -> None:
    errors = {}

    parcels = payload.parcels or []
    if len(parcels) != 1:
        errors["parcels"] = "a brev letter is one mailpiece: exactly one parcel is required"

    parcel = parcels[0] if parcels else None

    if (payload.shipper.country_code or "").upper() != "SE":
        errors["shipper.country_code"] = (
            "postnord_brev is a Swedish domestic service: the shipper country must be SE"
        )
    if (payload.recipient.country_code or "").upper() != "SE":
        errors["recipient.country_code"] = (
            "postnord_brev is a Swedish domestic service: the recipient country must be SE"
        )

    if parcel is not None:
        weight = _weight_grams(parcel)
        if weight <= 0:
            errors["parcels.weight"] = (
                "a declared weight is required: the letter's Vikt prints on the label"
            )
        elif weight > MAX_WEIGHT_GRAMS:
            errors["parcels.weight"] = "a 1:a-klassbrev may weigh at most 2 kg"

        if all([parcel.length, parcel.width, parcel.height]):
            mm = DIMENSION_UNIT_MM.get((parcel.dimension_unit or "CM").upper(), 10.0)
            total_mm = (
                float(parcel.length)
                + float(parcel.width)
                + float(parcel.height)
            ) * mm
            if total_mm > MAX_LENGTH_PLUS_WIDTH_PLUS_HEIGHT_MM:
                errors["parcels.dimension"] = (
                    "a 1:a-klassbrev may measure at most L+B+T 900 mm"
                )

    if not (
        (payload.metadata or {}).get("postnord_port_paye_customer_number")
        or settings.customer_number
    ):
        errors["customer_number"] = (
            "the port payé customer number is required: it prints as Kundnummer on every label"
        )

    if not (settings.franking_asset or "").strip():
        errors["franking_asset"] = (
            "the franking asset (port payé kliché, base64 SVG or PNG) is required on the connection"
        )

    if payload.customs is not None:
        errors["customs"] = (
            "customs declarations are not applicable to Swedish domestic letters"
        )

    if errors:
        raise lib.exceptions.FieldError(errors)
