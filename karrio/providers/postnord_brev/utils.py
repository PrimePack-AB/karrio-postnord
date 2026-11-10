import typing

import karrio.lib as lib
import karrio.core as core


class Settings(core.Settings):
    """PostNord Brev (port payé) connection settings.

    The carrier never contacts PostNord: letters are franked by the sender's
    port payé agreement, so the inputs are the agreement customer number and
    the franking asset rendered onto the label.
    """

    customer_number: typing.Optional[str] = None
    franking_asset: typing.Optional[str] = None

    @property
    def carrier_name(self):
        return "postnord_brev"

    @property
    def connection_config(self):
        from karrio.providers.postnord_brev.units import ConnectionConfig

        return lib.to_connection_config(
            self.config or {},
            option_type=ConnectionConfig,
        )
