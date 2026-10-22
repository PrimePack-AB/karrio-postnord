"""MyPack Collect (19) consignee notification requirement.

PostNord General Descriptions, service 19: one of Notification by Letter
(A2), SMS (A3) or E-mail (A4) must be booked, and A2 is not available to
countries outside the Nordics.
"""

import unittest
from unittest.mock import patch

import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

from .fixture import gateway, gateway_with_default_notification
from .test_shipment import ShipmentPayload, ShipmentResponse

COLLECT_PAYLOAD = {**ShipmentPayload, "service": "postnord_mypack_collect", "options": {}}


def _payload(options=None, **recipient):
    return models.ShipmentRequest(
        **{
            **COLLECT_PAYLOAD,
            "recipient": {
                key: value
                for key, value in {**COLLECT_PAYLOAD["recipient"], **recipient}.items()
                if value is not None
            },
            "options": options or {},
        }
    )


def _codes(request_gateway, payload):
    request = request_gateway.mapper.create_shipment_request(payload)
    shipment = lib.to_dict(request.serialize())["shipment"][0]
    return shipment["service"].get("additionalServiceCode") or [], request.ctx


def _book(request_gateway, payload):
    with patch("karrio.mappers.postnord.proxy.lib.request") as mock:
        mock.return_value = ShipmentResponse
        shipment, messages = (
            karrio.Shipment.create(payload).from_(request_gateway).parse()
        )
        return shipment, messages, mock


class TestNotificationRequirement(unittest.TestCase):
    def test_missing_notification_is_rejected_before_booking(self):
        shipment, messages, mock = _book(gateway, _payload())
        mock.assert_not_called()
        self.assertIsNone(shipment)
        self.assertEqual([m.code for m in messages], ["NOTIFICATION_REQUIRED"])
        self.assertEqual(
            messages[0].message,
            "postnord_mypack_collect requires a consignee notification: set "
            "options.postnord_notify_by_letter, options.sms_notification or "
            "options.email_notification, or the connection's default_notification",
        )

    def test_letter_does_not_satisfy_the_requirement_outside_the_nordics(self):
        payload = _payload(
            {"postnord_notify_by_letter": True},
            country_code="DE", postal_code="10115", city="Berlin", state_code=None,
        )
        shipment, messages, mock = _book(gateway, payload)
        mock.assert_not_called()
        self.assertEqual([m.code for m in messages], ["NOTIFICATION_REQUIRED"])
        self.assertNotIn("letter", messages[0].message)

    def test_explicit_notification_satisfies_the_requirement(self):
        for option, code in [
            ("sms_notification", "A3"),
            ("email_notification", "A4"),
            ("postnord_notify_by_letter", "A2"),
        ]:
            with self.subTest(option=option):
                codes, ctx = _codes(gateway, _payload({option: True}))
                self.assertEqual(codes, [code])
                self.assertIsNone(ctx.get("notification_error"))

    def test_other_services_are_not_gated(self):
        codes, ctx = _codes(gateway, models.ShipmentRequest(**{**ShipmentPayload, "options": {}}))
        self.assertEqual(codes, [])
        self.assertIsNone(ctx.get("notification_error"))

    def test_default_books_the_preferred_channel_with_a_warning(self):
        shipment, messages, mock = _book(
            gateway_with_default_notification["sms_then_email"], _payload()
        )
        self.assertIsNotNone(shipment)
        booked = lib.to_dict(mock.call_args.kwargs["data"])["shipment"][0]
        self.assertEqual(booked["service"]["additionalServiceCode"], ["A3"])
        warning = next(m for m in messages if m.code == "postnord_notification_defaulted")
        self.assertEqual(warning.level, "warning")
        self.assertEqual(
            warning.message,
            "No consignee notification was requested for postnord_mypack_collect; "
            "booked options.sms_notification (A3) from the connection's "
            "default_notification",
        )

    def test_default_preference_order_follows_consignee_contacts(self):
        cases = [
            ("sms", {}, ["A3"]),
            ("email", {}, ["A4"]),
            ("letter", {}, ["A2"]),
            ("sms_then_email", {}, ["A3"]),
            ("sms_then_email", {"phone_number": None}, ["A4"]),
            ("email_then_sms", {}, ["A4"]),
            ("email_then_sms", {"email": None}, ["A3"]),
        ]
        for preference, recipient, expected in cases:
            with self.subTest(preference=preference, recipient=recipient):
                codes, ctx = _codes(
                    gateway_with_default_notification[preference],
                    _payload(**recipient),
                )
                self.assertEqual(codes, expected)
                self.assertEqual(ctx.get("notification_defaulted"), expected[0])

    def test_default_without_a_usable_channel_is_rejected(self):
        cases = [
            ("sms", _payload(phone_number=None)),
            ("sms_then_email", _payload(phone_number=None, email=None)),
            # An explicit opt-out is never overridden by the default.
            ("sms", _payload({"sms_notification": False})),
            # Letter is not available outside the Nordics.
            ("letter", _payload(country_code="DE", postal_code="10115", city="Berlin", state_code=None)),
        ]
        for preference, payload in cases:
            with self.subTest(preference=preference):
                codes, ctx = _codes(gateway_with_default_notification[preference], payload)
                self.assertEqual(codes, [])
                self.assertIsNotNone(ctx.get("notification_error"))
                self.assertIsNone(ctx.get("notification_defaulted"))

    def test_explicit_request_is_not_extended_by_the_default(self):
        codes, ctx = _codes(
            gateway_with_default_notification["sms"],
            _payload({"email_notification": True}),
        )
        self.assertEqual(codes, ["A4"])
        self.assertIsNone(ctx.get("notification_defaulted"))


if __name__ == "__main__":
    unittest.main()
