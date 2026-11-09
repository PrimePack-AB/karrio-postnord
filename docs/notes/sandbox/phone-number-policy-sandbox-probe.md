---
title: "PostNord phone number policy sandbox probe"
created: 2026-11-09
---

# PostNord phone number policy sandbox probe

*Grounding `postnord_phone_number_policy` (released in 2026.11.0) in test-mode truth: whether PostNord accepts bookings without party phones, and whether the printed label follows what was sent.*
*Repo-origin note, not ported from the fork: created 2026-11-09, evidencing sandbox probe P8 through the env-gated harness (segments added in commit 162c387). Captures live under `$XDG_STATE_HOME/karrio-postnord/sandbox/` — `~/.local/state/karrio-postnord/sandbox/` at the default root — and are cited by run directory, file name, and sha256 only. Credentials are referenced by environment variable name only; no apikey, customer number, or application id value appears in this note, and no printout content beyond presence checks is reproduced.*

## Method

The probe ran through the same env-gated harness as P1–P7 (`sandbox_tests/`; method in [cn23-composition-sandbox-probe.md](cn23-composition-sandbox-probe.md)): `POSTNORD_SANDBOX=1` with the sandbox credentials, only `https://atapi2.postnord.com/`, `testIndicator` true on every booking body, each segment fired once ever, and the default budget of four bookings.

Under `omit_when_email_suffices` the connector leaves `contact.phoneNo` and `smsNo` off a booking party that has an e-mail address, unless the basic service needs that party's phone (`PRODUCT_PHONE_PARTIES` in `karrio/providers/postnord/units.py`: Parcel (18) the consignee, 20 and 24 both parties) or, for the consignee, A3, A9, or B8 is booked; `always` sends every phone.
P8 books four domestic parcels through the connector (`sandbox_tests/postnord/test_p8_phone_number_policy.py`), Stockholm to Göteborg, SE to SE, one 1.0 kg parcel, in PDF, with the policy sent as the per-shipment `postnord_phone_number_policy` option.
Both parties carry a person name, a company name, an `example.com` e-mail address, and an invented E.164 phone number.
Each case's mapped request is checked for the expected phone presence per party before its budget and marker are taken, so a mapping mismatch would have failed without firing.

| Segment | Service | Policy | Consignor phone sent | Consignee phone sent |
|---|---|---|---|---|
| `p8_phone_policy_17_always` | MyPack Home (17) with C7 | `always` | yes | yes |
| `p8_phone_policy_17_omit` | MyPack Home (17) with C7 | `omit_when_email_suffices` | no | no |
| `p8_phone_policy_18_omit` | Parcel (18) | `omit_when_email_suffices` | no | yes |
| `p8_phone_policy_18_no_consignee_phone` | Parcel (18), consignee without a phone number | `always` | yes | no |

The last segment asks whether test mode enforces the README's "Parcel (18): consignee contact name and phone number are mandatory" rule that `PRODUCT_PHONE_PARTIES` encodes; "sent" there means both `phoneNo` and `smsNo` present, "not sent" both absent, as the request captures record.

## Captures

The four bookings ran in run `20261109T111647Z` between 11:16:49 and 11:16:51 UTC.
The responses are committed as `tests/postnord/fixtures/sandbox/p8-phone-policy-17-always.response.json`, `p8-phone-policy-17-omit.response.json`, `p8-phone-policy-18-omit.response.json`, and `p8-phone-policy-18-no-consignee-phone.response.json`, all byte-identical to their captures; the printouts stay in the run directory only.

| Run | File | sha256 |
|---|---|---|
| 20261109T111647Z | `001-p8_phone_policy_17_always.response.parsed.json` | `60aaa9f81c946193dcbde312153f26b1561bb71b0da855c724fab1cdf083b233` |
| 20261109T111647Z | `001-p8_phone_policy_17_always.printout01.pdf` | `2f6f5c7d11f6ab908a248965b4bbf0e20bfb6a301310415f4d061cbaaa625f97` |
| 20261109T111647Z | `003-p8_phone_policy_17_omit.response.parsed.json` | `f3d0c61df4eb02554336b266704e16c27476e08718af931d3544ca0821339a05` |
| 20261109T111647Z | `003-p8_phone_policy_17_omit.printout01.pdf` | `cab08c6a048a21cd3a5476f9e3e87f0b762e07044de15f1d9efc62ba95061428` |
| 20261109T111647Z | `005-p8_phone_policy_18_omit.response.parsed.json` | `14bc0ca547d19e7c89a3395894946092fd8577cd41aac51a8655a51a24f3233a` |
| 20261109T111647Z | `005-p8_phone_policy_18_omit.printout01.pdf` | `36194291ac69c2826bfb7041a517391ba52c12bee4eb9f03968f5e5eb7119b12` |
| 20261109T111647Z | `007-p8_phone_policy_18_no_consignee_phone.response.parsed.json` | `68b8518a4a56bb60bbf0cdf97edf6af40f15b20445069ef16520e2b633b3cbbd` |
| 20261109T111647Z | `007-p8_phone_policy_18_no_consignee_phone.printout01.pdf` | `7541e14a9704b98c83aabb66677046504f883db66d522f438514c212c1dcd8de` |

## Findings

PostNord accepted all four bookings.
Each response carries status `OK`, a bookingId, one item id with its printId, and one PDF printout of composition `{label: 1}` for the booked basic service.

| UTC (response logged) | Segment | Outcome | bookingId | Item id | printId |
|---|---|---|---|---|---|
| 11:16:49.23 | `p8_phone_policy_17_always` | accepted | `ILPN0010M426URTRDLSPIUSLRFOEME` | `00173215400196730537` | `992724c00dbc4ecbb99369c5abf899ff` |
| 11:16:49.87 | `p8_phone_policy_17_omit` | accepted | `ILPN0010M426VXAYUBHPMGOFDOVSBL` | `00173215400196730544` | `7227f942f1cf4efa9980404399b397d0` |
| 11:16:50.55 | `p8_phone_policy_18_omit` | accepted | `ILPN0010M426WOYCURMFXVYCJDKIGA` | `00173215400196730551` | `7f107db4f9b243c0a738b114eb293f35` |
| 11:16:51.21 | `p8_phone_policy_18_no_consignee_phone` | accepted | `ILPN0010M426XENRWIEAUTYDRHGDLN` | `00173215400196730568` | `0406b71cf080448585d201434be27152` |

No response carries a `SAO-HR-*` sanitization fault: the two `SAO-HR-25060301` phone and sms sanitizations that P1, P5, P6, and P7 drew on their Albanian consignee do not appear for these Swedish parties, under either policy.
Every response instead carries one fault P1–P7 did not draw, `SAE-BR-25062401` "Invalid Customer Number for Application Id", with references `CustomerOriginValidationError.type` `CUSTOMER_NO_FAULTY` and `RuleAction` `LOG_MODE`, under the message "General client indata error in LOG mode, soon to be activated".
The connector sent `application` with `name` only and no `applicationId`, as in P7, whose 2026-10-26 responses carry no such fault; the rule is logged rather than enforced, and the message says it is soon to be activated, so a booking without an application id matching the customer number may be rejected once it is.
The karrio parse returned a shipment with tracking number and bookingId for every segment, and surfaced the fault as a message with code `SAE-BR-25062401`.

Test mode does not enforce the Parcel (18) consignee phone rule: `p8_phone_policy_18_no_consignee_phone` sent neither `phoneNo` nor `smsNo` on the consignee and was accepted without any fault beyond `SAE-BR-25062401`.
The rule `PRODUCT_PHONE_PARTIES` encodes rests on PostNord's General Descriptions, as the README cites it, not on a PostNord validation, which is what docs/concepts/labels.md "Party phone numbers" already states; this round neither confirms nor refutes production enforcement.

The printed labels follow the request.
Each label is one PDF page with a "Phone:" field in the sender block and one in the recipient block; text extraction (pypdf, in scratch outside the repository) found each party's number present exactly when the request sent it, and the field empty otherwise.

| Segment | Consignor phone printed | Consignee phone printed |
|---|---|---|
| `p8_phone_policy_17_always` | yes | yes |
| `p8_phone_policy_17_omit` | no | no |
| `p8_phone_policy_18_omit` | no | yes |
| `p8_phone_policy_18_no_consignee_phone` | yes | no |

Neither e-mail address appears in the printed text of any label.

Scope: this is test mode, so production may enforce rules test mode only logs or skips, and only PDF at standard size was printed; the printouts stay in the run directory and are not reproduced here.
