import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import current_user
from ..models import (
    LedgerEntry,
    MonetizationTransaction,
    User,
    Wallet,
)

router = APIRouter(
    prefix="/monetization",
    tags=["Monetization"],
)


# VIKI's initial platform fee.
# Keep this server-side; never trust a fee sent by the client.
PLATFORM_FEE_RATE = 0.20


class GiftRequest(BaseModel):
    creator_username: str
    amount: float = Field(gt=0, le=10000)
    currency: str = Field(default="USD", min_length=3, max_length=3)


@router.post("/gift")
def send_gift(
    data: GiftRequest,
    sender: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    currency = data.currency.upper()

    creator = db.query(User).filter(
        User.username == data.creator_username.lower()
    ).first()

    if not creator:
        raise HTTPException(
            status_code=404,
            detail="Creator not found",
        )

    if creator.id == sender.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot send a gift to yourself",
        )

    if not creator.is_creator:
        raise HTTPException(
            status_code=400,
            detail="This account is not a creator account",
        )

    sender_wallet = db.query(Wallet).filter(
        Wallet.user_id == sender.id,
        Wallet.currency == currency,
    ).first()

    creator_wallet = db.query(Wallet).filter(
        Wallet.user_id == creator.id,
        Wallet.currency == currency,
    ).first()

    if not sender_wallet:
        raise HTTPException(
            status_code=400,
            detail=f"Sender has no {currency} wallet",
        )

    if not creator_wallet:
        creator_wallet = Wallet(
            user_id=creator.id,
            currency=currency,
            available=0,
            pending=0,
        )
        db.add(creator_wallet)
        db.flush()

    amount = round(data.amount, 2)
    platform_amount = round(
        amount * PLATFORM_FEE_RATE,
        2,
    )
    creator_amount = round(
        amount - platform_amount,
        2,
    )

    if sender_wallet.available < amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient wallet balance",
        )

    reference = "VIKI-" + secrets.token_hex(12)

    sender_wallet.available = round(
        sender_wallet.available - amount,
        2,
    )

    creator_wallet.available = round(
        creator_wallet.available + creator_amount,
        2,
    )

    transaction = MonetizationTransaction(
        sender_id=sender.id,
        creator_id=creator.id,
        gross_amount=amount,
        creator_amount=creator_amount,
        platform_amount=platform_amount,
        currency=currency,
        transaction_type="gift",
        status="completed",
        reference=reference,
    )

    db.add(transaction)

    db.add(
        LedgerEntry(
            user_id=sender.id,
            entry_type="gift_sent",
            amount=-amount,
            currency=currency,
            description=f"Gift sent to @{creator.username}",
            reference=reference,
        )
    )

    db.add(
        LedgerEntry(
            user_id=creator.id,
            entry_type="creator_earning",
            amount=creator_amount,
            currency=currency,
            description=f"Creator gift from @{sender.username}",
            reference=reference,
        )
    )

    db.commit()

    return {
        "success": True,
        "reference": reference,
        "gross_amount": amount,
        "creator_amount": creator_amount,
        "platform_amount": platform_amount,
        "currency": currency,
    }


@router.get("/creator/earnings")
def creator_earnings(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(
        MonetizationTransaction.currency,
        func.coalesce(
            func.sum(
                MonetizationTransaction.creator_amount
            ),
            0,
        ),
    ).filter(
        MonetizationTransaction.creator_id == user.id,
        MonetizationTransaction.status == "completed",
    ).group_by(
        MonetizationTransaction.currency
    ).all()

    return {
        "username": user.username,
        "earnings": [
            {
                "currency": currency,
                "amount": round(float(amount), 2),
            }
            for currency, amount in rows
        ],
    }


@router.get("/owner/revenue")
def owner_revenue(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Owner access required",
        )

    rows = db.query(
        MonetizationTransaction.currency,
        func.coalesce(
            func.sum(
                MonetizationTransaction.platform_amount
            ),
            0,
        ),
    ).filter(
        MonetizationTransaction.status == "completed",
    ).group_by(
        MonetizationTransaction.currency
    ).all()

    return {
        "platform": "VIKI",
        "revenue": [
            {
                "currency": currency,
                "amount": round(float(amount), 2),
            }
            for currency, amount in rows
        ],
    }
