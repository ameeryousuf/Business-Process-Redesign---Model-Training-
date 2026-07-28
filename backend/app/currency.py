import requests

RATE_API_URL = "https://open.er-api.com/v6/latest/USD"
BASE_CURRENCY = "PKR"
REQUEST_TIMEOUT_SECONDS = 5

_rate_cache = {}


def _fetch_usd_rates():
    if "rates" in _rate_cache:
        return _rate_cache["rates"]

    response = requests.get(RATE_API_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    if payload.get("result") != "success":
        raise RuntimeError(f"Exchange rate API returned non-success result: {payload.get('result')}")

    rates = payload["rates"]
    _rate_cache["rates"] = rates
    return rates


def convert_to_usd(amount, from_currency):
    if amount is None:
        return None

    currency = (from_currency or "USD").upper()

    if currency == "USD":
        return amount

    rates = _fetch_usd_rates()

    if currency not in rates:
        raise ValueError(f"Unsupported currency '{currency}': not found in exchange rate API response")

    return amount / rates[currency]


def convert_to_pkr(amount, from_currency):
    if amount is None:
        return None

    currency = (from_currency or BASE_CURRENCY).upper()

    if currency == BASE_CURRENCY:
        return amount

    rates = _fetch_usd_rates()

    if "USD" not in rates or BASE_CURRENCY not in rates:
        raise RuntimeError("Exchange rate API response is missing USD or PKR rates")

    if currency == "USD":
        usd_amount = amount
    else:
        if currency not in rates:
            raise ValueError(f"Unsupported currency '{currency}': not found in exchange rate API response")
        usd_amount = amount / rates[currency]

    pkr_per_usd = rates[BASE_CURRENCY]
    return usd_amount * pkr_per_usd


if __name__ == "__main__":
    print("100 PKR ->", convert_to_usd(100, "PKR"), "USD")
    print("100 USD ->", convert_to_usd(100, "USD"), "USD")
    print("100 USD ->", convert_to_pkr(100, "USD"), "PKR")
