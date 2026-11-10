"""postnord_phone_number_policy: connection config and per-shipment option."""

import typing
import unittest

import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models
import karrio.references as references
import karrio.providers.postnord.units as provider_units

from .fixture import _settings, gateway, gateway_with_phone_number_policy
from .test_pickup import PickupPayload
from .test_shipment import CustomsInvoiceShipmentPayload, ShipmentPayload

OMIT_GATEWAY = gateway_with_phone_number_policy("omit_when_email_suffices")
SHIPPER_PHONE = ShipmentPayload["shipper"]["phone_number"]
RECIPIENT_PHONE = ShipmentPayload["recipient"]["phone_number"]

# MyPack Home (17) requires consignee SMS or e-mail contact data only, so no
# product rule keeps a phone; C7 is PostNord's mandatory add-on for 17.
HOME_PAYLOAD = {
    **ShipmentPayload,
    "service": "postnord_mypack_home",
    "options": {"postnord_flexchange": True},
}
COLLECT_PAYLOAD = {**ShipmentPayload, "service": "postnord_mypack_collect", "options": {}}

ALWAYS = provider_units.PhoneNumberPolicy.always
OMIT = provider_units.PhoneNumberPolicy.omit_when_email_suffices
REQUIRED_ONLY = provider_units.PhoneNumberPolicy.omit_unless_required
REQUIRED_ONLY_GATEWAY = gateway_with_phone_number_policy("omit_unless_required")
NO_EMAIL = {"email": None}


class TestPhoneNumberPolicyResolution(unittest.TestCase):
    def test_policy_is_published_as_a_connection_config_enum(self):
        config = references.collect_references()["connection_configs"]["postnord"]
        self.assertEqual(config["postnord_phone_number_policy"]["type"], "string")
        self.assertEqual(
            config["postnord_phone_number_policy"]["enum"],
            ["always", "omit_when_email_suffices", "omit_unless_required"],
        )

    def test_connection_config_reaches_the_settings(self):
        settings = gateway_with_phone_number_policy("omit_when_email_suffices").settings
        self.assertEqual(
            settings.connection_config.postnord_phone_number_policy.state,
            "omit_when_email_suffices",
        )

    def test_request_option_overrides_the_connection_config(self):
        cases = [
            ("unset", None, None, ALWAYS),
            ("config_omit", None, "omit_when_email_suffices", OMIT),
            ("config_always", None, "always", ALWAYS),
            ("request_omit", "omit_when_email_suffices", None, OMIT),
            ("request_always_over_omit", "always", "omit_when_email_suffices", ALWAYS),
            ("request_omit_over_always", "omit_when_email_suffices", "always", OMIT),
            ("blank_request_falls_back", "", "omit_when_email_suffices", OMIT),
            ("unknown_request_keeps_phones", "never", "omit_when_email_suffices", ALWAYS),
            ("unknown_config_keeps_phones", None, "never", ALWAYS),
            ("non_string_request_keeps_phones", 3, "omit_when_email_suffices", ALWAYS),
            ("config_required_only", None, "omit_unless_required", REQUIRED_ONLY),
            ("request_required_only", "omit_unless_required", "always", REQUIRED_ONLY),
            ("request_omit_over_required_only", "omit_when_email_suffices", "omit_unless_required", OMIT),
        ]
        for name, requested, configured, expected in cases:
            with self.subTest(case=name):
                self.assertIs(
                    provider_units.phone_number_policy(requested, configured), expected
                )

    def test_product_phone_parties_follow_the_general_descriptions(self):
        role = provider_units.PartyRole
        self.assertEqual(
            provider_units.PRODUCT_PHONE_PARTIES,
            {
                "18": frozenset({role.consignee}),
                "20": frozenset({role.consignor, role.consignee}),
                "24": frozenset({role.consignor, role.consignee}),
            },
        )

    def test_phone_dependent_services_are_the_phone_channels(self):
        self.assertEqual(
            provider_units.CONSIGNEE_PHONE_SERVICES,
            frozenset(
                {
                    provider_units.ShippingOption.postnord_notify_by_sms.value.code,
                    provider_units.ShippingOption.postnord_notify_by_phone.value.code,
                    provider_units.ShippingOption.postnord_driver_notification.value.code,
                }
            ),
        )
        self.assertEqual(provider_units.CONSIGNEE_PHONE_SERVICES, {"A3", "A9", "B8"})



def _booking(request_gateway, payload=None, options=None, shipper=None, recipient=None):
    payload = payload or HOME_PAYLOAD
    request = request_gateway.mapper.create_shipment_request(
        models.ShipmentRequest(
            **{
                **payload,
                "shipper": _without_none({**payload["shipper"], **(shipper or {})}),
                "recipient": _without_none({**payload["recipient"], **(recipient or {})}),
                "options": {**payload.get("options", {}), **(options or {})},
            }
        )
    )
    return _serialized(request)["shipment"][0], request.ctx


def _serialized(request) -> dict:
    return typing.cast(dict, lib.to_dict(request.serialize()))


def _without_none(address):
    return {key: value for key, value in address.items() if value is not None}


def _contact(shipment, role):
    return shipment["parties"][role]["party"]["contact"]


def _phones(contact):
    return {key: contact.get(key) for key in ("phoneNo", "smsNo")}


def _kept(phone):
    return {"phoneNo": phone, "smsNo": phone}


OMITTED = {"phoneNo": None, "smsNo": None}


class TestPhoneNumberPolicyBooking(unittest.TestCase):
    def test_default_policy_sends_phones_alongside_email(self):
        shipment, _ = _booking(gateway)
        self.assertEqual(_phones(_contact(shipment, "consignee")), _kept(RECIPIENT_PHONE))
        self.assertEqual(_phones(_contact(shipment, "consignor")), _kept(SHIPPER_PHONE))
        self.assertEqual(
            _contact(shipment, "consignee")["emailAddress"], "receiver@example.com"
        )

    def test_consignee_phone_is_omitted_when_email_suffices(self):
        shipment, _ = _booking(OMIT_GATEWAY)
        contact = _contact(shipment, "consignee")
        self.assertEqual(_phones(contact), OMITTED)
        self.assertEqual(contact["emailAddress"], "receiver@example.com")
        self.assertEqual(contact["contactName"], "Jane Receiver")

    def test_phone_dependent_services_keep_the_consignee_phone(self):
        for option, code in [
            ("sms_notification", "A3"),
            ("postnord_notify_by_sms", "A3"),
            ("postnord_notify_by_phone", "A9"),
            ("postnord_driver_notification", "B8"),
        ]:
            with self.subTest(option=option):
                shipment, _ = _booking(OMIT_GATEWAY, options={option: True})
                self.assertIn(code, shipment["service"]["additionalServiceCode"])
                self.assertEqual(
                    _phones(_contact(shipment, "consignee")), _kept(RECIPIENT_PHONE)
                )

    def test_other_services_do_not_keep_the_consignee_phone(self):
        for option in ["email_notification", "postnord_notify_by_letter", "insurance"]:
            with self.subTest(option=option):
                value = 500.0 if option == "insurance" else True
                shipment, _ = _booking(OMIT_GATEWAY, options={option: value})
                self.assertEqual(_phones(_contact(shipment, "consignee")), OMITTED)

    def test_explicitly_declined_phone_service_does_not_keep_the_phone(self):
        shipment, _ = _booking(OMIT_GATEWAY, options={"sms_notification": False})
        self.assertEqual(_phones(_contact(shipment, "consignee")), OMITTED)

    def test_defaulted_sms_notification_keeps_the_consignee_phone(self):
        collect = COLLECT_PAYLOAD
        cases = [
            (["sms"], "A3", _kept(RECIPIENT_PHONE)),
            (["email", "sms"], "A4", OMITTED),
        ]
        for channels, defaulted, expected in cases:
            with self.subTest(channels=channels):
                request_gateway = karrio.gateway["postnord"].create(
                    dict(
                        _settings,
                        config=dict(
                            postnord_phone_number_policy="omit_when_email_suffices",
                            postnord_default_notification=channels,
                        ),
                    )
                )
                shipment, ctx = _booking(request_gateway, payload=collect)
                self.assertEqual(ctx.get("notification_defaulted"), defaulted)
                self.assertEqual(shipment["service"]["additionalServiceCode"], [defaulted])
                self.assertEqual(_phones(_contact(shipment, "consignee")), expected)

    def test_requested_default_sms_notification_keeps_the_consignee_phone(self):
        collect = COLLECT_PAYLOAD
        shipment, ctx = _booking(
            OMIT_GATEWAY,
            payload=collect,
            options={"postnord_default_notification": ["sms"]},
        )
        self.assertEqual(ctx.get("notification_defaulted"), "A3")
        self.assertEqual(_phones(_contact(shipment, "consignee")), _kept(RECIPIENT_PHONE))

    def test_party_without_email_keeps_its_phone(self):
        shipment, _ = _booking(
            OMIT_GATEWAY, shipper={"email": None}, recipient={"email": None}
        )
        self.assertEqual(_phones(_contact(shipment, "consignee")), _kept(RECIPIENT_PHONE))
        self.assertEqual(_phones(_contact(shipment, "consignor")), _kept(SHIPPER_PHONE))

    def test_shipper_phone_is_omitted_when_email_suffices(self):
        for options in [{}, {"sms_notification": True}, {"postnord_driver_notification": True}]:
            with self.subTest(options=options):
                shipment, _ = _booking(OMIT_GATEWAY, options=options)
                contact = _contact(shipment, "consignor")
                self.assertEqual(_phones(contact), OMITTED)
                self.assertEqual(contact["emailAddress"], "sender@example.com")

    def test_product_required_phones_are_kept(self):
        cases = [
            ("postnord_parcel", OMITTED, _kept(RECIPIENT_PHONE)),
            ("postnord_return_pickup", _kept(SHIPPER_PHONE), _kept(RECIPIENT_PHONE)),
            ("postnord_return", _kept(SHIPPER_PHONE), _kept(RECIPIENT_PHONE)),
        ]
        for service, consignor, consignee in cases:
            with self.subTest(service=service):
                shipment, _ = _booking(
                    OMIT_GATEWAY, payload={**ShipmentPayload, "service": service, "options": {}}
                )
                self.assertEqual(_phones(_contact(shipment, "consignor")), consignor)
                self.assertEqual(_phones(_contact(shipment, "consignee")), consignee)

    def test_customs_invoice_contacts_keep_their_phones(self):
        shipment, ctx = _booking(OMIT_GATEWAY, payload=CustomsInvoiceShipmentPayload)
        invoice = shipment["customsInvoice"]
        self.assertEqual(
            invoice["seller"]["contacts"]["phoneNo"],
            CustomsInvoiceShipmentPayload["shipper"]["phone_number"],
        )
        self.assertEqual(
            invoice["buyer"]["contacts"]["phoneNo"],
            CustomsInvoiceShipmentPayload["recipient"]["phone_number"],
        )
        self.assertEqual(_phones(_contact(shipment, "consignor")), OMITTED)
        self.assertEqual(
            _phones(_contact(shipment, "consignee")),
            _kept(CustomsInvoiceShipmentPayload["recipient"]["phone_number"]),
        )

    def test_request_option_overrides_the_connection_policy(self):
        cases = [
            (OMIT_GATEWAY, "always", _kept(RECIPIENT_PHONE)),
            (gateway_with_phone_number_policy("always"), "omit_when_email_suffices", OMITTED),
            (gateway, "omit_when_email_suffices", OMITTED),
            (OMIT_GATEWAY, None, OMITTED),
        ]
        for request_gateway, requested, expected in cases:
            with self.subTest(requested=requested):
                options = (
                    {} if requested is None else {"postnord_phone_number_policy": requested}
                )
                shipment, _ = _booking(request_gateway, options=options)
                self.assertEqual(_phones(_contact(shipment, "consignee")), expected)

    def test_policy_option_is_not_an_additional_service(self):
        shipment, _ = _booking(
            gateway, options={"postnord_phone_number_policy": "omit_when_email_suffices"}
        )
        self.assertEqual(shipment["service"]["additionalServiceCode"], ["C7"])


class TestOmitUnlessRequiredBooking(unittest.TestCase):
    def test_phones_are_omitted_with_or_without_email(self):
        for name, address in [("with_email", {}), ("without_email", NO_EMAIL)]:
            with self.subTest(case=name):
                shipment, _ = _booking(
                    REQUIRED_ONLY_GATEWAY, shipper=address, recipient=address
                )
                self.assertEqual(_phones(_contact(shipment, "consignee")), OMITTED)
                self.assertEqual(_phones(_contact(shipment, "consignor")), OMITTED)
                self.assertEqual(
                    _contact(shipment, "consignee")["contactName"], "Jane Receiver"
                )

    def test_phone_dependent_services_keep_the_consignee_phone(self):
        for option, code in [
            ("sms_notification", "A3"),
            ("postnord_notify_by_sms", "A3"),
            ("postnord_notify_by_phone", "A9"),
            ("postnord_driver_notification", "B8"),
        ]:
            for name, address in [("with_email", {}), ("without_email", NO_EMAIL)]:
                with self.subTest(option=option, case=name):
                    shipment, _ = _booking(
                        REQUIRED_ONLY_GATEWAY,
                        options={option: True},
                        shipper=address,
                        recipient=address,
                    )
                    self.assertIn(code, shipment["service"]["additionalServiceCode"])
                    self.assertEqual(
                        _phones(_contact(shipment, "consignee")), _kept(RECIPIENT_PHONE)
                    )
                    self.assertEqual(_phones(_contact(shipment, "consignor")), OMITTED)

    def test_other_services_do_not_keep_the_consignee_phone(self):
        for option in ["email_notification", "postnord_notify_by_letter", "insurance"]:
            with self.subTest(option=option):
                value = 500.0 if option == "insurance" else True
                shipment, _ = _booking(
                    REQUIRED_ONLY_GATEWAY, options={option: value}, recipient=NO_EMAIL
                )
                self.assertEqual(_phones(_contact(shipment, "consignee")), OMITTED)

    def test_product_required_phones_are_kept(self):
        cases = [
            ("postnord_parcel", OMITTED, _kept(RECIPIENT_PHONE)),
            ("postnord_return_pickup", _kept(SHIPPER_PHONE), _kept(RECIPIENT_PHONE)),
            ("postnord_return", _kept(SHIPPER_PHONE), _kept(RECIPIENT_PHONE)),
        ]
        for service, consignor, consignee in cases:
            for name, address in [("with_email", {}), ("without_email", NO_EMAIL)]:
                with self.subTest(service=service, case=name):
                    shipment, _ = _booking(
                        REQUIRED_ONLY_GATEWAY,
                        payload={**ShipmentPayload, "service": service, "options": {}},
                        shipper=address,
                        recipient=address,
                    )
                    self.assertEqual(_phones(_contact(shipment, "consignor")), consignor)
                    self.assertEqual(_phones(_contact(shipment, "consignee")), consignee)

    def test_defaulted_notification_decides_the_consignee_phone(self):
        cases = [
            ("sms", ["sms"], {}, "A3", _kept(RECIPIENT_PHONE)),
            ("email_first", ["email", "sms"], {}, "A4", OMITTED),
            ("sms_without_email", ["email", "sms"], NO_EMAIL, "A3", _kept(RECIPIENT_PHONE)),
            ("letter", ["letter"], NO_EMAIL, "A2", OMITTED),
        ]
        for name, channels, recipient, defaulted, expected in cases:
            with self.subTest(case=name):
                request_gateway = karrio.gateway["postnord"].create(
                    dict(
                        _settings,
                        config=dict(
                            postnord_phone_number_policy="omit_unless_required",
                            postnord_default_notification=channels,
                        ),
                    )
                )
                shipment, ctx = _booking(
                    request_gateway, payload=COLLECT_PAYLOAD, recipient=recipient
                )
                self.assertEqual(ctx.get("notification_defaulted"), defaulted)
                self.assertEqual(shipment["service"]["additionalServiceCode"], [defaulted])
                self.assertEqual(_phones(_contact(shipment, "consignee")), expected)

    def test_customs_invoice_contacts_keep_their_phones(self):
        payload = CustomsInvoiceShipmentPayload
        shipment, _ = _booking(
            REQUIRED_ONLY_GATEWAY, payload=payload, shipper=NO_EMAIL, recipient=NO_EMAIL
        )
        invoice = shipment["customsInvoice"]
        self.assertEqual(
            invoice["seller"]["contacts"]["phoneNo"], payload["shipper"]["phone_number"]
        )
        self.assertEqual(
            invoice["buyer"]["contacts"]["phoneNo"], payload["recipient"]["phone_number"]
        )
        self.assertEqual(_phones(_contact(shipment, "consignor")), OMITTED)

    def test_request_option_selects_the_policy(self):
        cases = [
            (gateway, "omit_unless_required", NO_EMAIL, OMITTED),
            (REQUIRED_ONLY_GATEWAY, "always", NO_EMAIL, _kept(RECIPIENT_PHONE)),
            (REQUIRED_ONLY_GATEWAY, "omit_when_email_suffices", NO_EMAIL, _kept(RECIPIENT_PHONE)),
            (REQUIRED_ONLY_GATEWAY, None, NO_EMAIL, OMITTED),
        ]
        for request_gateway, requested, recipient, expected in cases:
            with self.subTest(requested=requested):
                options = (
                    {} if requested is None else {"postnord_phone_number_policy": requested}
                )
                shipment, _ = _booking(
                    request_gateway, options=options, recipient=recipient
                )
                self.assertEqual(_phones(_contact(shipment, "consignee")), expected)

    def test_pickup_party_keeps_its_phone(self):
        address = {**PickupPayload["address"], "email": None}
        request = REQUIRED_ONLY_GATEWAY.mapper.create_pickup_request(
            models.PickupRequest(**{**PickupPayload, "address": _without_none(address)})
        )
        contact = _serialized(request)["shipment"][0]["parties"]["consignor"][
            "party"
        ]["contact"]
        self.assertEqual(_phones(contact), _kept(PickupPayload["address"]["phone_number"]))


class TestPhoneNumberPolicyPickup(unittest.TestCase):
    def test_pickup_party_keeps_its_phone(self):
        request = OMIT_GATEWAY.mapper.create_pickup_request(
            models.PickupRequest(**PickupPayload)
        )
        contact = _serialized(request)["shipment"][0]["parties"]["consignor"][
            "party"
        ]["contact"]
        self.assertEqual(contact["emailAddress"], PickupPayload["address"]["email"])
        self.assertEqual(_phones(contact), _kept(PickupPayload["address"]["phone_number"]))


if __name__ == "__main__":
    unittest.main()
