import karrio.references

# The SDK has no switch for shipment advisors, and installed advisor plugins
# append messages that the exact-match assertions do not expect.
karrio.references.get_advisors = lambda: []

from .fixture import gateway
