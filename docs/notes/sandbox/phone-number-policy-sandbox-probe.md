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
