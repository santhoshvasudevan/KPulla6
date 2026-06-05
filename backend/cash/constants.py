"""Supported cash account currencies (native ledger; no FX in storage)."""

from __future__ import annotations

# Display/base (5) + additional major currencies (15) = 20 total.
SUPPORTED_CASH_CURRENCIES: frozenset[str] = frozenset(
    {
        "EUR",
        "USD",
        "INR",
        "GBP",
        "CHF",
        "JPY",
        "CNY",
        "CAD",
        "AUD",
        "HKD",
        "SGD",
        "KRW",
        "BRL",
        "MXN",
        "ZAR",
        "SEK",
        "NOK",
        "DKK",
        "PLN",
        "AED",
    }
)

SUPPORTED_CASH_CURRENCY_CHOICES: list[tuple[str, str]] = [
    (code, code) for code in sorted(SUPPORTED_CASH_CURRENCIES)
]
