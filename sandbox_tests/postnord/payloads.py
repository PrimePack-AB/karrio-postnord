"""Sandbox probe payloads: the karrio request shapes and the raw EDI bodies.

The gateway segments mirror the customs fixtures of
``tests/postnord/test_shipment.py`` (the CN23 and customs-invoice shapes the
connector's own tests pin), retargeted from Norway to a generic Tirana
address; the raw segment builds the minimal ``ediInstruction`` by hand, the
way the connector serializes it, minus the customs branch our fail-fast
guards would demand.
"""

import datetime
import re
import typing

from . import harness

SHIPPER = {
    "address_line1": "Sandhamnsgatan 61",
    "city": "Stockholm",
    "postal_code": "11528",
    "country_code": "SE",
    "state_code": "Stockholm",
    "person_name": "John Sender",
    "company_name": "ACME Sender AB",
    "phone_number": "+46701234567",
    "email": "sender@example.com",
}

# Generic invented consignee: no real person or business.
ALBANIA = {
    "address_line1": "Rruga e Dibres 100",
    "city": "Tirana",
    "postal_code": "1001",
    "country_code": "AL",
    "person_name": "Test Receiver",
    "company_name": "Receiver SHPK",
    "phone_number": "+35541234567",
    "email": "receiver@example.com",
}

PARCEL = {
    "weight": 1.0,
    "width": 20.0,
    "height": 10.0,
    "length": 30.0,
    "weight_unit": "KG",
    "dimension_unit": "CM",
}

# Seller VAT of the customs-invoice fixture in tests/postnord/test_shipment.py.
SHIPPER_VAT_NO = "SE556123471101"


def cn23_payload(eori: str, reference: str) -> dict:
    """International Parcel (91) to Albania with the CN23 customs block.

    The connector maps this onto the shipment entry's
    ``customsDeclarationCN23`` branch: the customs shape of the CN22 letter
    fixtures, with ``postalCharges`` booked as a zero amount in the
    totalValue currency.
    """
    return dict(
        shipper=SHIPPER,
        recipient=ALBANIA,
        parcels=[PARCEL],
        service="postnord_postpaket_utrikes",
        reference=reference,
        customs={
            "content_type": "merchandise",
            "options": {"eori_number": eori},
            "commodities": [
                {
                    "title": "Wool socks",
                    "quantity": 2,
                    "weight": 0.25,
                    "weight_unit": "KG",
                    "value_amount": 25.0,
                    "value_currency": "SEK",
                    "hs_code": "6115950000",
                    "origin_country": "SE",
                },
                {
                    "title": "Baseball cap",
                    "quantity": 1,
                    "weight": 0.4,
                    "weight_unit": "KG",
                    "value_amount": 15.0,
                    "value_currency": "SEK",
                    "hs_code": "6505003000",
                    "origin_country": "SE",
                },
            ],
        },
    )


def invoice_payload(eori: str, reference: str) -> dict:
    """Parcel (18) to Albania with a commercial customs invoice.

    Mirrors the SE-to-NO customs-invoice test payload: the seller VAT
    number, an invoice number and date, and two invoice lines select the
    ``customsInvoice`` branch the connector books for parcel products.
    """
    return dict(
        shipper={**SHIPPER, "federal_tax_id": SHIPPER_VAT_NO},
        recipient=ALBANIA,
        parcels=[PARCEL],
        service="postnord_parcel",
        reference=reference,
        customs={
            "content_type": "merchandise",
            "commercial_invoice": True,
            "invoice": f"INV-{reference}",
            "invoice_date": datetime.date.today().isoformat(),
            "options": {"eori_number": eori},
            "commodities": [
                {
                    "title": "Wool socks",
                    "quantity": 2,
                    "weight": 0.2,
                    "weight_unit": "KG",
                    "value_amount": 150.0,
                    "value_currency": "SEK",
                    "hs_code": "6115950000",
                    "origin_country": "SE",
                },
                {
                    "description": "Knitted cap",
                    "quantity": 1,
                    "weight": 0.1,
                    "weight_unit": "KG",
                    "value_amount": 200.0,
                    "value_currency": "SEK",
                    "hs_code": "6505003000",
                    "origin_country": "SE",
                },
            ],
        },
    )


def _party(
    address: dict,
    *,
    issuer_code: str,
    party_id: typing.Optional[str] = None,
) -> dict:
    party = {
        "nameIdentification": {
            "name": address["person_name"],
            "companyName": address["company_name"],
        },
        "address": {
            "streets": [address["address_line1"]],
            "postalCode": address["postal_code"],
            "city": address["city"],
            "countryCode": address["country_code"],
        },
        "contact": {
            "contactName": address["person_name"],
            "emailAddress": address["email"],
            "phoneNo": address["phone_number"],
            "smsNo": address["phone_number"],
        },
    }
    return dict(
        issuerCode=issuer_code,
        **(
            {"partyIdentification": {"partyId": party_id, "partyIdType": "160"}}
            if party_id
            else {}
        ),
        party=party,
    )


def application_object(environ: typing.Mapping[str, str]) -> typing.Optional[dict]:
    """The top-level ``application`` object with the configured id, or None.

    The id comes from ``POSTNORD_LIVE_APPLICATION_ID`` (the name the user
    chose for the real id; the value is kept only in ``.env``), falling
    back to ``POSTNORD_APPLICATION_ID``. The booking API takes
    ``applicationId`` as an integer (Booking APIs 3.5.29.1) and
    rejects anything but a 4-digit value (SACUS-BR-24100901, observed on
    the p3-91 customs-less booking), so a present-but-malformed id refuses
    rather than books. ``name`` stays the required client-integration name
    the connector's own bookings send.
    """
    raw = environ.get("POSTNORD_LIVE_APPLICATION_ID") or environ.get(
        "POSTNORD_APPLICATION_ID"
    )
    if raw is None or raw.strip() == "":
        return None
    if re.fullmatch(r"\d{4}", raw.strip()) is None:
        raise harness.SandboxConfigError(
            f"{raw!r} is not a 4-digit application id; PostNord rejects "
            "anything else (SACUS-BR-24100901)"
        )
    return {"name": "Karrio", "applicationId": int(raw.strip())}


def raw_booking_body(
    basic_service_code: str,
    customer_number: str,
    application: typing.Optional[dict] = None,
) -> dict:
    """The minimal ``ediInstruction`` for a booking without any customs branch.

    Shaped the way the connector serializes a booking (parties, goods item,
    envelope with ``testIndicator`` true) but built by hand, so the
    connector's customs fail-fast guards cannot interfere: the question is
    what PostNord itself answers for basicServiceCode 18 and 91 when the
    customs object is simply absent. ``application`` is injected top-level
    when given, mirroring the object the connector's mapper serializes.
    """
    return {
        "messageDate": datetime.datetime.now().isoformat(timespec="seconds"),
        "testIndicator": True,
        "updateIndicator": "Original",
        **({"application": application} if application else {}),
        "shipment": [
            {
                "shipmentIdentification": {
                    "shipmentId": f"P3-NOCUSTOMS-{basic_service_code}"
                },
                "service": {"basicServiceCode": basic_service_code},
                "parties": {
                    "consignor": _party(
                        SHIPPER, issuer_code="Z12", party_id=customer_number
                    ),
                    "consignee": _party(ALBANIA, issuer_code="Z12"),
                },
                "goodsItem": [
                    {
                        "packageTypeCode": "BX",
                        "numberOfPackageTypeCodeItems": {"value": 1},
                        "items": [
                            {
                                "itemIdentification": {"itemId": "0"},
                                "grossWeight": {"value": PARCEL["weight"], "unit": "KGM"},
                                "dimensions": {
                                    "height": {"value": PARCEL["height"], "unit": "CMT"},
                                    "width": {"value": PARCEL["width"], "unit": "CMT"},
                                    "length": {"value": PARCEL["length"], "unit": "CMT"},
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }
