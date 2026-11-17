"""PostNord shared customs guard tests (line limit, HS tariff format)."""

import unittest
from unittest.mock import patch

import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models
import karrio.schemas.postnord.customs_declaration_request as postnord_req
import karrio.providers.postnord.customs as customs

from .fixture import gateway
from .test_shipment import (
    CustomsInvoiceShipmentPayload,
    CustomsShipmentPayload,
    InternationalParcelCN23Payload,
)


HS_FORMAT_ERROR = (
    "HS tariff number must be at least six digits with no spaces or separators"
)


def _invoice_payload(lines: int) -> dict:
    """The customs-invoice payload at ``lines`` commodity rows."""
    commodity = CustomsInvoiceShipmentPayload["customs"]["commodities"][0]
    return {
        **CustomsInvoiceShipmentPayload,
        "customs": {
            **CustomsInvoiceShipmentPayload["customs"],
            "commodities": [dict(commodity) for _ in range(lines)],
        },
    }


def _with_hs_code(payload: dict, hs_code: str) -> dict:
    """A payload whose first commodity carries ``hs_code``."""
    commodities = payload["customs"]["commodities"]
    return {
        **payload,
        "customs": {
            **payload["customs"],
            "commodities": [{**commodities[0], "hs_code": hs_code}] + commodities[1:],
        },
    }


def _proxy_declaration(hs_code: str) -> postnord_req.CustomsDeclarationRequestType:
    """A one-line CN22 declaration for the proxy path at ``hs_code``."""
    return postnord_req.CustomsDeclarationRequestType(
        messageDate="2026-06-24T10:00:00",
        messageFunction="Customsdeclaration",
        language="EN",
        updateIndicator="Original",
        testIndicator=True,
        ids=[postnord_req.IDType(id="00373500454541020957", idType="ITEMID")],
        customsDeclarationCN22=postnord_req.CustomsDeclarationCN22Type(
            countryOfOrigin="SE",
            EORIorPersonalIdNumber="SE5561234711",
            detailedDescription=[
                postnord_req.CustomsDeclarationCN22DetailedDescriptionType(
                    content="Item 1", hsTariffNumber=hs_code, rowNo=1
                )
            ],
        ),
    )


class TestPostNordCustomsInvoiceLineLimit(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_invoice_lines_at_limit(self):
        # 13 lines is the inclusive boundary and is sent in full: the
        # booking invoice branch sits under the same shared guard as the
        # CN22/CN23 builders and the declaration proxy.
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**_invoice_payload(13))
        )
        invoice = lib.to_dict(request.serialize())["shipment"][0]["customsInvoice"]
        self.assertEqual(len(invoice["detailedDescription"]), 13)

    def test_invoice_lines_over_limit(self):
        # 14 lines reject the booking before submission: a field error
        # naming the 13-line limit, and no HTTP call.
        with patch("karrio.mappers.postnord.proxy.lib.request") as mock:
            shipment, messages = (
                karrio.Shipment.create(models.ShipmentRequest(**_invoice_payload(14)))
                .from_(gateway)
                .parse()
            )
            mock.assert_not_called()
        self.assertIsNone(shipment)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].code, "SHIPPING_SDK_FIELD_ERROR")
        self.assertEqual(
            messages[0].details["customs.commodities"],
            "customs.commodities exceeds the 13-line customs declaration limit",
        )


if __name__ == "__main__":
    unittest.main()
