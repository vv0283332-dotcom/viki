import os
import hmac
import hashlib
from abc import ABC, abstractmethod

import httpx


class PaymentProvider(ABC):
    name = "unknown"

    @abstractmethod
    def supports(self, currency: str, country: str = "") -> bool:
        pass

    @abstractmethod
    async def initialize(
        self,
        *,
        reference: str,
        amount: float,
        currency: str,
        email: str,
        name: str,
        callback_url: str,
        metadata: dict,
    ) -> dict:
        pass

    @abstractmethod
    async def verify(self, reference: str) -> dict:
        pass


class FlutterwaveProvider(PaymentProvider):
    name = "flutterwave"

    def __init__(self):
        self.secret = os.getenv("FLW_SECRET_KEY", "").strip()

    def supports(self, currency: str, country: str = "") -> bool:
        if not self.secret:
            return False

        return currency.upper() in {
            "NGN", "GHS", "XOF", "XAF", "KES",
            "UGX", "RWF", "TZS", "ZAR", "MWK",
            "EGP", "USD", "EUR", "GBP",
        }

    async def initialize(
        self,
        *,
        reference,
        amount,
        currency,
        email,
        name,
        callback_url,
        metadata,
    ):
        if not self.secret:
            raise RuntimeError("Flutterwave is not configured")

        payload = {
            "tx_ref": reference,
            "amount": amount,
            "currency": currency,
            "redirect_url": callback_url,
            "customer": {
                "email": email,
                "name": name,
            },
            "customizations": {
                "title": "VIKI Wallet",
                "description": "Fund your VIKI wallet",
            },
            "meta": metadata,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.flutterwave.com/v3/payments",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.secret}",
                    "Content-Type": "application/json",
                },
            )

        data = response.json()

        if response.status_code >= 400 or data.get("status") != "success":
            raise RuntimeError(
                data.get("message", "Flutterwave initialization failed")
            )

        return {
            "checkout_url": data["data"]["link"],
            "provider_reference": reference,
        }

    async def verify(self, reference):
        if not self.secret:
            raise RuntimeError("Flutterwave is not configured")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"https://api.flutterwave.com/v3/transactions/verify_by_reference?tx_ref={reference}",
                headers={
                    "Authorization": f"Bearer {self.secret}",
                },
            )

        data = response.json()

        if response.status_code >= 400:
            raise RuntimeError(
                data.get("message", "Flutterwave verification failed")
            )

        transaction = data.get("data") or {}

        return {
            "success": data.get("status") == "success",
            "status": transaction.get("status"),
            "reference": transaction.get("tx_ref"),
            "provider_transaction_id": transaction.get("id"),
            "amount": transaction.get("amount"),
            "currency": transaction.get("currency"),
        }


class PaystackProvider(PaymentProvider):
    name = "paystack"

    def __init__(self):
        self.secret = os.getenv("PAYSTACK_SECRET_KEY", "").strip()

    def supports(self, currency: str, country: str = "") -> bool:
        if not self.secret:
            return False

        return currency.upper() in {
            "NGN", "GHS", "ZAR", "KES",
        }

    async def initialize(
        self,
        *,
        reference,
        amount,
        currency,
        email,
        name,
        callback_url,
        metadata,
    ):
        if not self.secret:
            raise RuntimeError("Paystack is not configured")

        # Paystack expects amounts in the currency's subunit.
        amount_subunit = int(round(amount * 100))

        payload = {
            "email": email,
            "amount": str(amount_subunit),
            "currency": currency,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": metadata,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.paystack.co/transaction/initialize",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.secret}",
                    "Content-Type": "application/json",
                },
            )

        data = response.json()

        if response.status_code >= 400 or not data.get("status"):
            raise RuntimeError(
                data.get("message", "Paystack initialization failed")
            )

        return {
            "checkout_url": data["data"]["authorization_url"],
            "provider_reference": data["data"]["reference"],
        }

    async def verify(self, reference):
        if not self.secret:
            raise RuntimeError("Paystack is not configured")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers={
                    "Authorization": f"Bearer {self.secret}",
                },
            )

        data = response.json()

        if response.status_code >= 400 or not data.get("status"):
            raise RuntimeError(
                data.get("message", "Paystack verification failed")
            )

        transaction = data.get("data") or {}

        return {
            "success": transaction.get("status") == "success",
            "status": transaction.get("status"),
            "reference": transaction.get("reference"),
            "provider_transaction_id": transaction.get("id"),
            "amount": transaction.get("amount"),
            "currency": transaction.get("currency"),
        }


class PaymentService:
    def __init__(self):
        self.providers = {
            "flutterwave": FlutterwaveProvider(),
            "paystack": PaystackProvider(),
        }

    def get(self, name):
        provider = self.providers.get(name.lower())
        if not provider:
            raise ValueError(f"Unsupported payment provider: {name}")
        return provider

    def available(self, currency, country=""):
        return [
            provider.name
            for provider in self.providers.values()
            if provider.supports(currency.upper(), country.upper())
        ]

    def choose(self, currency, country="", requested=None):
        if requested:
            provider = self.get(requested)

            if not provider.supports(currency.upper(), country.upper()):
                raise ValueError(
                    f"{provider.name} does not support {currency.upper()}"
                )

            return provider

        available = self.available(currency, country)

        if not available:
            raise ValueError(
                f"No configured payment provider supports {currency.upper()}"
            )

        return self.get(available[0])


payment_service = PaymentService()
