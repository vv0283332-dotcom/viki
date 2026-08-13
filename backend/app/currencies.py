SUPPORTED_CURRENCIES = {
    "USD": {"name": "US Dollar", "symbol": "$", "decimals": 2},
    "EUR": {"name": "Euro", "symbol": "€", "decimals": 2},
    "GBP": {"name": "British Pound", "symbol": "£", "decimals": 2},
    "NGN": {"name": "Nigerian Naira", "symbol": "₦", "decimals": 2},
    "XOF": {"name": "West African CFA Franc", "symbol": "CFA", "decimals": 0},
    "GHS": {"name": "Ghanaian Cedi", "symbol": "₵", "decimals": 2},
    "CAD": {"name": "Canadian Dollar", "symbol": "C$", "decimals": 2},
    "AUD": {"name": "Australian Dollar", "symbol": "A$", "decimals": 2},
    "JPY": {"name": "Japanese Yen", "symbol": "¥", "decimals": 0},
    "CNY": {"name": "Chinese Yuan", "symbol": "¥", "decimals": 2},
    "ZAR": {"name": "South African Rand", "symbol": "R", "decimals": 2},
    "INR": {"name": "Indian Rupee", "symbol": "₹", "decimals": 2},
}


def is_supported_currency(currency: str) -> bool:
    return currency.upper() in SUPPORTED_CURRENCIES
