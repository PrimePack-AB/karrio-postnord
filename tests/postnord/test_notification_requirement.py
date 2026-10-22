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
import karrio.references as references

from .fixture import _settings, gateway, gateway_with_default_notification
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
            "options.email_notification, or the connection's postnord_default_notification",
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

    def test_default_books_the_first_usable_channel_with_a_warning(self):
        shipment, messages, mock = _book(
            gateway_with_default_notification(["sms", "email"]), _payload()
        )
        self.assertIsNotNone(shipment)
        booked = lib.to_dict(mock.call_args.kwargs["data"])["shipment"][0]
        self.assertEqual(booked["service"]["additionalServiceCode"], ["A3"])
        warning = next(m for m in messages if m.code == "postnord_notification_defaulted")
        self.assertEqual(warning.level, "warning")
        self.assertEqual(
            warning.message,
            "No consignee notification was requested for postnord_mypack_collect; "
            "booked options.sms_notification (A3) from "
            "postnord_default_notification",
        )

    def test_default_channel_order_follows_consignee_contacts(self):
        cases = [
            (["sms"], {}, ["A3"]),
            (["email"], {}, ["A4"]),
            (["letter"], {}, ["A2"]),
            (["sms", "email"], {}, ["A3"]),
            (["sms", "email"], {"phone_number": None}, ["A4"]),
            (["email", "sms"], {}, ["A4"]),
            (["email", "sms"], {"email": None}, ["A3"]),
            # Letter as the last fallback needs no consignee contact.
            (["sms", "email", "letter"], {"phone_number": None, "email": None}, ["A2"]),
            (["letter", "sms"], {}, ["A2"]),
        ]
        for channels, recipient, expected in cases:
            with self.subTest(channels=channels, recipient=recipient):
                codes, ctx = _codes(
                    gateway_with_default_notification(channels),
                    _payload(**recipient),
                )
                self.assertEqual(codes, expected)
                self.assertEqual(ctx.get("notification_defaulted"), expected[0])

    def test_single_channel_string_is_a_one_item_list(self):
        for channel, expected in [("sms", ["A3"]), ("email", ["A4"]), ("letter", ["A2"])]:
            with self.subTest(source="config", channel=channel):
                codes, ctx = _codes(gateway_with_default_notification(channel), _payload())
                self.assertEqual(codes, expected)
                self.assertIsNone(ctx.get("notification_error"))
            with self.subTest(source="request", channel=channel):
                codes, ctx = _codes(
                    gateway, _payload({"postnord_default_notification": channel})
                )
                self.assertEqual(codes, expected)
                self.assertIsNone(ctx.get("notification_error"))

    def test_duplicate_channels_collapse_keeping_first_occurrence(self):
        codes, ctx = _codes(
            gateway_with_default_notification(["email", "sms", "email"]),
            _payload(email=None),
        )
        self.assertEqual(codes, ["A3"])
        codes, ctx = _codes(
            gateway_with_default_notification(["email", "sms", "email"]), _payload()
        )
        self.assertEqual(codes, ["A4"])

    def test_released_presets_are_accepted_as_channel_orders(self):
        cases = [
            ("sms_then_email", {}, ["A3"]),
            ("sms_then_email", {"phone_number": None}, ["A4"]),
            ("email_then_sms", {}, ["A4"]),
            ("email_then_sms", {"email": None}, ["A3"]),
            (["email_then_sms", "letter"], {"phone_number": None, "email": None}, ["A2"]),
            (["sms", "email_then_sms"], {"phone_number": None}, ["A4"]),
            (["letter", "sms_then_email"], {}, ["A2"]),
        ]
        for channels, recipient, expected in cases:
            with self.subTest(source="config", channels=channels, recipient=recipient):
                codes, ctx = _codes(
                    gateway_with_default_notification(channels), _payload(**recipient)
                )
                self.assertEqual(codes, expected)
                self.assertIsNone(ctx.get("notification_error"))
            with self.subTest(source="request", channels=channels, recipient=recipient):
                codes, ctx = _codes(
                    gateway,
                    _payload({"postnord_default_notification": channels}, **recipient),
                )
                self.assertEqual(codes, expected)
                self.assertIsNone(ctx.get("notification_error"))

    def test_released_presets_expand_in_place_before_duplicates_collapse(self):
        cases = [
            (["email", "sms_then_email"], {}, ["A4"]),
            (["email", "sms_then_email"], {"email": None}, ["A3"]),
            (["sms_then_email", "email_then_sms"], {"phone_number": None}, ["A4"]),
        ]
        for channels, recipient, expected in cases:
            with self.subTest(channels=channels, recipient=recipient):
                codes, _ = _codes(
                    gateway_with_default_notification(channels), _payload(**recipient)
                )
                self.assertEqual(codes, expected)

    def test_empty_or_null_default_is_unset(self):
        for channels in [[], None, "", "  ", [""], ["", " "]]:
            with self.subTest(source="config", channels=channels):
                codes, ctx = _codes(gateway_with_default_notification(channels), _payload())
                self.assertEqual(codes, [])
                self.assertTrue(
                    ctx["notification_error"].startswith(
                        "postnord_mypack_collect requires a consignee notification"
                    )
                )
            with self.subTest(source="request", channels=channels):
                codes, ctx = _codes(
                    gateway_with_default_notification(["sms"]),
                    _payload({"postnord_default_notification": channels}),
                )
                self.assertEqual(codes, ["A3"])
                self.assertIsNone(ctx.get("notification_error"))

    def test_blank_entries_are_ignored(self):
        for channels in [["", "sms"], [" ", "sms", ""]]:
            with self.subTest(source="config", channels=channels):
                codes, ctx = _codes(gateway_with_default_notification(channels), _payload())
                self.assertEqual(codes, ["A3"])
                self.assertIsNone(ctx.get("notification_error"))
            with self.subTest(source="request", channels=channels):
                codes, ctx = _codes(
                    gateway, _payload({"postnord_default_notification": channels})
                )
                self.assertEqual(codes, ["A3"])
                self.assertIsNone(ctx.get("notification_error"))

    def test_default_without_a_usable_channel_is_rejected(self):
        germany = dict(country_code="DE", postal_code="10115", city="Berlin", state_code=None)
        cases = [
            (["sms"], _payload(phone_number=None)),
            (["sms", "email"], _payload(phone_number=None, email=None)),
            # An explicit opt-out is never overridden by the default.
            (["sms"], _payload({"sms_notification": False})),
            # Letter is not available outside the Nordics.
            (["letter"], _payload(**germany)),
            (
                ["sms", "email", "letter"],
                _payload(phone_number=None, email=None, **germany),
            ),
        ]
        for channels, payload in cases:
            with self.subTest(channels=channels):
                codes, ctx = _codes(gateway_with_default_notification(channels), payload)
                self.assertEqual(codes, [])
                self.assertIsNotNone(ctx.get("notification_error"))
                self.assertIsNone(ctx.get("notification_defaulted"))

    def test_request_option_overrides_the_connection_default(self):
        cases = [
            (gateway, ["email", "sms"], ["A4"]),
            (gateway_with_default_notification(["sms"]), ["email"], ["A4"]),
            (gateway_with_default_notification(["sms", "email"]), ["email", "sms"], ["A4"]),
            (gateway_with_default_notification(["sms"]), "email", ["A4"]),
            (gateway_with_default_notification(["sms"]), None, ["A3"]),
        ]
        for request_gateway, channels, expected in cases:
            with self.subTest(channels=channels):
                codes, ctx = _codes(
                    request_gateway, _payload({"postnord_default_notification": channels})
                )
                self.assertEqual(codes, expected)
                self.assertIsNone(ctx.get("notification_error"))

    def test_unknown_request_channel_is_rejected(self):
        cases = [
            ("pigeon", "'pigeon'"),
            (["sms", "pigeon"], "'pigeon'"),
            ("sms_or_email", "'sms_or_email'"),
            (3, "3"),
            ({"sms": True}, "{'sms': True}"),
        ]
        for value, shown in cases:
            with self.subTest(value=value):
                shipment, messages, mock = _book(
                    gateway_with_default_notification(["sms"]),
                    _payload({"postnord_default_notification": value}),
                )
                mock.assert_not_called()
                self.assertIsNone(shipment)
                self.assertEqual([m.code for m in messages], ["NOTIFICATION_REQUIRED"])
                self.assertEqual(
                    messages[0].message,
                    f"options.postnord_default_notification {shown} is not one of "
                    "sms, email, letter",
                )

    def test_unknown_connection_channel_names_its_source(self):
        for value, shown in [
            ("pigeon", "'pigeon'"),
            (["email", "pigeon"], "'pigeon'"),
            (3, "3"),
        ]:
            with self.subTest(value=value):
                _, ctx = _codes(gateway_with_default_notification(value), _payload())
                self.assertEqual(
                    ctx["notification_error"],
                    f"the connection's postnord_default_notification {shown} is not "
                    "one of sms, email, letter",
                )

    def test_default_notification_is_published_as_a_channel_list(self):
        config = references.collect_references()["connection_configs"]["postnord"]
        self.assertEqual(config["postnord_default_notification"]["type"], "list")
        self.assertEqual(
            config["postnord_default_notification"]["enum"], ["sms", "email", "letter"]
        )

    def test_explicit_request_is_not_extended_by_the_default(self):
        codes, ctx = _codes(
            gateway_with_default_notification(["sms"]),
            _payload({"email_notification": True}),
        )
        self.assertEqual(codes, ["A4"])
        self.assertIsNone(ctx.get("notification_defaulted"))


if __name__ == "__main__":
    unittest.main()
