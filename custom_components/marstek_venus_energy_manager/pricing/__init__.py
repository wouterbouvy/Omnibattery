"""Dynamic pricing package.

Holds the price data model and pure price-math/parsing helpers extracted from
``ChargeDischargeController``. The runtime engine and notifications are added in
later stages of the module-8 extraction.
"""
from collections import namedtuple

# Dynamic pricing data structures
PriceSlot = namedtuple("PriceSlot", ["start", "end", "price"])

# Imported after PriceSlot is defined so ``calculations`` can resolve it from
# the partially-initialised package without a circular import.
from . import calculations  # noqa: E402,F401

__all__ = ["PriceSlot", "calculations"]
