"""postnord_phone_number_policy: connection config and per-shipment option."""

import unittest

import karrio.references as references
import karrio.providers.postnord.units as provider_units

from .fixture import gateway, gateway_with_phone_number_policy

ALWAYS = provider_units.PhoneNumberPolicy.always
OMIT = provider_units.PhoneNumberPolicy.omit_when_email_suffices


class TestPhoneNumberPolicyResolution(unittest.TestCase):
    def test_policy_is_published_as_a_connection_config_enum(self):
        config = references.collect_references()["connection_configs"]["postnord"]
        self.assertEqual(config["postnord_phone_number_policy"]["type"], "string")
        self.assertEqual(
            config["postnord_phone_number_policy"]["enum"],
            ["always", "omit_when_email_suffices"],
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
        ]
        for name, requested, configured, expected in cases:
            with self.subTest(case=name):
                self.assertIs(
                    provider_units.phone_number_policy(requested, configured), expected
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


if __name__ == "__main__":
    unittest.main()
