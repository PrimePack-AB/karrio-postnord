"""Sandbox segments ``p8_phone_policy_*``: booking party phones under the phone number policy.

``postnord_phone_number_policy`` (released in 2026.11.0) decides whether
the booking parties' ``contact.phoneNo`` and ``smsNo`` are sent. Under
``omit_when_email_suffices`` a party with an e-mail address loses both
unless the basic service needs that party's phone (``PRODUCT_PHONE_PARTIES``:
Parcel (18) the consignee) or, for the consignee, A3, A9, or B8 is
booked. The segments book domestic Stockholm to Göteborg parcels through
the connector, in PDF, with the policy as the per-shipment option, and
answer whether PostNord accepts each shape and whether the printed label
shows each party's phone.

- ``17_always``: MyPack Home (17) with C7, ``always``; the control.
- ``17_omit``: the same under ``omit_when_email_suffices``; neither party
  sends a phone.
- ``18_omit``: Parcel (18) under ``omit_when_email_suffices``; only the
  consignee phone is sent.
- ``18_no_consignee_phone``: Parcel (18) under ``always`` with the
  consignee's phone left out and its e-mail kept; tests whether test mode
  enforces the "18: consignee phone mandatory" rule behind
  ``PRODUCT_PHONE_PARTIES``. A rejection is a valid finding.

Each case's mapped request is checked for the expected phone presence per
party before its budget and marker are taken, so a mapping mismatch
fails without firing. The four bookings fire in ``CASES`` order, each its
own one-shot segment; none retries.
"""

import base64
import dataclasses
import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from . import harness, payloads

SEGMENT_PREFIX = "p8_phone_policy"
PARTIES = ("consignor", "consignee")


@dataclasses.dataclass(frozen=True)
class Case:
    name: str
    service: str
    policy: str
    options: typing.Mapping[str, typing.Any]
    recipient_without_phone: bool
    expected_phones: typing.Mapping[str, bool]


CASES: typing.Tuple[Case, ...] = (
    Case(
        name="17_always",
        service="postnord_mypack_home",
        policy="always",
        options={"postnord_flexchange": True},
        recipient_without_phone=False,
        expected_phones={"consignor": True, "consignee": True},
    ),
    Case(
        name="17_omit",
        service="postnord_mypack_home",
        policy="omit_when_email_suffices",
        options={"postnord_flexchange": True},
        recipient_without_phone=False,
        expected_phones={"consignor": False, "consignee": False},
    ),
    Case(
        name="18_omit",
        service="postnord_parcel",
        policy="omit_when_email_suffices",
        options={},
        recipient_without_phone=False,
        expected_phones={"consignor": False, "consignee": True},
    ),
    Case(
        name="18_no_consignee_phone",
        service="postnord_parcel",
        policy="always",
        options={},
        recipient_without_phone=True,
        expected_phones={"consignor": True, "consignee": False},
    ),
)


def segment_name(case: Case) -> str:
    return f"{SEGMENT_PREFIX}_{case.name}"


def reference(case: Case) -> str:
    return f"P8-{case.name.upper().replace('_', '-')}"


def shipment_request(case: Case) -> models.ShipmentRequest:
    return models.ShipmentRequest(
        **payloads.domestic_payload(
            case.service,
            reference(case),
            case.policy,
            options=case.options,
            recipient_without_phone=case.recipient_without_phone,
        )
    )


def party_phones(body: typing.Mapping[str, typing.Any]) -> typing.Dict[str, bool]:
    """Whether each booking party's contact carries ``phoneNo`` or ``smsNo``."""
    parties = body["shipment"][0]["parties"]
    return {
        role: any(
            (parties[role]["party"].get("contact") or {}).get(field)
            for field in ("phoneNo", "smsNo")
        )
        for role in PARTIES
    }


def mapped_body(gateway, case: Case) -> typing.Dict[str, typing.Any]:
    """The booking body the connector maps for ``case``, without sending it."""
    return typing.cast(
        typing.Dict[str, typing.Any],
        lib.to_dict(
            gateway.mapper.create_shipment_request(shipment_request(case)).serialize()
        ),
    )


class TestSandboxP8PhoneNumberPolicy(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment(SEGMENT_PREFIX)

    def _book(self, case: Case) -> None:
        self.maxDiff = None
        segment = segment_name(case)
        gateway = self.session.gateway()
        self.assertEqual(
            party_phones(mapped_body(gateway, case)),
            dict(case.expected_phones),
            "the mapped request's party phones differ from the case; not firing",
        )
        harness.require_booking(self, self.session)
        harness.require_fire(self, self.session, segment)

        shipment, messages = (
            karrio.Shipment.create(shipment_request(case)).from_(gateway).parse()
        )

        bodies = self.session.capture_gateway_calls(gateway, segment)
        print_id = harness.find_print_id(bodies[0]) if bodies else None
        meta = (shipment.meta or {}) if shipment else {}
        self.session.write_result(
            segment,
            dict(
                service=case.service,
                phone_number_policy=case.policy,
                recipient_without_phone=case.recipient_without_phone,
                expected_phones=dict(case.expected_phones),
                karrio=dict(
                    tracking_number=shipment.tracking_number if shipment else None,
                    booking_id=meta.get("booking_id"),
                    printout_composition=meta.get("printout_composition"),
                    label_type=shipment.label_type if shipment else None,
                    label_bytes=(
                        len(base64.b64decode(shipment.docs.label))
                        if shipment and shipment.docs.label
                        else 0
                    ),
                    messages=lib.to_dict(messages),
                ),
                calls_captured=len(bodies),
                print_id=print_id,
            ),
        )
        self.session.log_booking(
            segment,
            self.id(),
            tracking_number=shipment.tracking_number if shipment else None,
            booking_id=meta.get("booking_id"),
            print_id=print_id,
        )
        self.assertEqual(len(bodies), 1, "expected exactly the booking call")

    def test_1_17_always(self):
        self._book(CASES[0])

    def test_2_17_omit(self):
        self._book(CASES[1])

    def test_3_18_omit(self):
        self._book(CASES[2])

    def test_4_18_no_consignee_phone(self):
        self._book(CASES[3])
