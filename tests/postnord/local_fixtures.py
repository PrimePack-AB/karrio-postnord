"""PostNord-generated printouts kept outside the repository.

PostNord's General Terms and Conditions for digital integration services
(clause 6) do not permit distributing content returned from the Services,
so the captured label and customs printouts the measurement, stamping-seed
and sandbox-evidence tests read are not tracked. They live in a local
directory, ``$POSTNORD_FIXTURES_DIR`` or else
``$XDG_STATE_HOME/karrio-postnord/fixtures`` (``~/.local/state`` when
``XDG_STATE_HOME`` is unset), with the layout of ``tests/postnord/fixtures``.
A test that reads them skips when any file of the set is absent; see
docs/development/index.md for where the files come from.
"""

import base64
import os
import pathlib
import typing
import unittest

ENVIRONMENT_VARIABLE = "POSTNORD_FIXTURES_DIR"

FILES = (
    "postnord_cn22.pdf",
    "postnord_cn22.zpl",
    "postnord_label_cn22_booking.zpl",
    "postnord_label_cn22_booking_two_pages.pdf",
    "postnord_label_cn22_international_parcel.pdf",
    "postnord_label_cn22_international_parcel.zpl",
    "postnord_label_cn22_printid.pdf",
    "postnord_label_cn22_printid.zpl",
    "postnord_label_cn23_international_parcel.pdf",
    "postnord_label_cn23_international_parcel.zpl",
    "sandbox/p1-cn23-gateway.printout01.pdf",
    "sandbox/p5-no-customs-with-application-raw.printout01.pdf",
)


def directory(environ: typing.Mapping[str, str] = os.environ) -> pathlib.Path:
    override = environ.get(ENVIRONMENT_VARIABLE)
    if override:
        return pathlib.Path(override).expanduser()
    state_home = environ.get("XDG_STATE_HOME") or str(
        pathlib.Path(environ.get("HOME") or pathlib.Path.home()) / ".local" / "state"
    )
    return pathlib.Path(state_home) / "karrio-postnord" / "fixtures"


def path(name: str) -> pathlib.Path:
    return directory() / name


def missing() -> typing.List[str]:
    return [name for name in FILES if not path(name).is_file()]


def read_b64(name: str) -> str:
    return base64.b64encode(path(name).read_bytes()).decode("utf-8")


required = unittest.skipIf(
    bool(missing()),
    f"local PostNord printouts absent from {directory()} "
    f"(set {ENVIRONMENT_VARIABLE}; see docs/development/index.md)",
)
