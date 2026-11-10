"""PostNord Brev carrier tests fixtures."""

import base64

import karrio.sdk as karrio


# A tiny synthetic franking asset: real PostNord artwork never enters the
# repository (cite-don't-commit; see the design note).
SyntheticFrankingSvg = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'>"
    "<rect width='10' height='10'/></svg>"
)
SyntheticFrankingAsset = base64.b64encode(SyntheticFrankingSvg.encode()).decode()

_settings = dict(
    id="123456789",
    test_mode=True,
    carrier_id="postnord_brev",
    customer_number="20000000",
    franking_asset=SyntheticFrankingAsset,
)

gateway = karrio.gateway["postnord_brev"].create(dict(_settings))


def gateway_without(**drop):
    """Gateway with top-level settings fields removed, for guard tests."""
    return karrio.gateway["postnord_brev"].create(
        {k: v for k, v in _settings.items() if k not in drop}
    )


def gateway_with_phone_policy(policy):
    """Gateway whose connection config sets postnord_phone_number_policy."""
    return karrio.gateway["postnord_brev"].create(
        dict(_settings, config=dict(postnord_phone_number_policy=policy))
    )
