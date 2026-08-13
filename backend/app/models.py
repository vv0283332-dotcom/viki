from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    is_creator: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        index=True,
    )
    available: Mapped[float] = mapped_column(Float, default=0.0)
    pending: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "currency",
            name="uq_wallet_user_currency",
        ),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entry_type: Mapped[str] = mapped_column(String(50))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    description: Mapped[str] = mapped_column(String(255))
    reference: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Follow(Base):
    __tablename__ = "follows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    following_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        UniqueConstraint(
            "follower_id",
            "following_id",
            name="uq_follow"
        ),
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    media_url: Mapped[str] = mapped_column(String(1000), default="")
    media_type: Mapped[str] = mapped_column(String(20), default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Like(Base):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "post_id",
            name="uq_post_like"
        ),
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class MonetizationTransaction(Base):
    __tablename__ = "monetization_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True
    )

    creator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True
    )

    gross_amount: Mapped[float] = mapped_column(Float)
    creator_amount: Mapped[float] = mapped_column(Float)
    platform_amount: Mapped[float] = mapped_column(Float)

    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD"
    )

    transaction_type: Mapped[str] = mapped_column(
        String(50),
        default="gift"
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="completed"
    )

    reference: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=now
    )


class RewardLedger(Base):
    __tablename__ = "reward_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True
    )

    activity_type: Mapped[str] = mapped_column(
        String(50),
        index=True
    )

    points: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(
        String(20),
        default="credited"
    )

    reference: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        index=True
    )

    description: Mapped[str] = mapped_column(
        String(255)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=now,
        index=True
    )

class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True
    )

    currency: Mapped[str] = mapped_column(
        String(3)
    )

    amount: Mapped[float] = mapped_column(
        Float
    )

    provider: Mapped[str] = mapped_column(
        String(50)
    )

    provider_reference: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=now
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )


class Beneficiary(Base):
    __tablename__ = "beneficiaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True
    )

    beneficiary_type: Mapped[str] = mapped_column(
        String(30)
    )

    country: Mapped[str] = mapped_column(
        String(2)
    )

    currency: Mapped[str] = mapped_column(
        String(3)
    )

    provider: Mapped[str] = mapped_column(
        String(50)
    )

    account_name: Mapped[str] = mapped_column(
        String(150)
    )

    account_number: Mapped[str] = mapped_column(
        String(150)
    )

    provider_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=now
    )


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True
    )

    beneficiary_id: Mapped[int] = mapped_column(
        ForeignKey("beneficiaries.id"),
        index=True
    )

    currency: Mapped[str] = mapped_column(
        String(3)
    )

    amount: Mapped[float] = mapped_column(
        Float
    )

    fee: Mapped[float] = mapped_column(
        Float,
        default=0.0
    )

    provider: Mapped[str] = mapped_column(
        String(50)
    )

    provider_reference: Mapped[str | None] = mapped_column(
        String(150),
        unique=True,
        index=True,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=now
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
