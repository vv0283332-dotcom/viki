from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import current_user
from ..models import RewardLedger, User

router = APIRouter(
    prefix="/rewards",
    tags=["Rewards"],
)


# VIKI reward policy.
# These are POINTS, not direct cash.
REWARD_VALUES = {
    "post": 10,
    "like_received": 1,
    "comment_received": 3,
    "follower_gained": 5,
    "daily_login": 5,
}


def add_reward(
    db: Session,
    user_id: int,
    activity_type: str,
    points: int,
    reference: str,
    description: str,
):
    existing = db.query(RewardLedger).filter(
        RewardLedger.reference == reference
    ).first()

    if existing:
        return existing

    reward = RewardLedger(
        user_id=user_id,
        activity_type=activity_type,
        points=points,
        status="credited",
        reference=reference,
        description=description,
    )

    db.add(reward)
    db.flush()

    return reward


@router.get("/balance")
def reward_balance(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    total = db.query(
        func.coalesce(func.sum(RewardLedger.points), 0)
    ).filter(
        RewardLedger.user_id == user.id,
        RewardLedger.status == "credited",
    ).scalar()

    return {
        "user_id": user.id,
        "points": int(total or 0),
        "currency": "VIKI",
    }


@router.get("/history")
def reward_history(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(RewardLedger).filter(
        RewardLedger.user_id == user.id
    ).order_by(
        RewardLedger.created_at.desc()
    ).limit(100).all()

    return {
        "count": len(rows),
        "rewards": [
            {
                "id": row.id,
                "activity": row.activity_type,
                "points": row.points,
                "status": row.status,
                "description": row.description,
                "reference": row.reference,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


@router.post("/daily")
def daily_reward(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()
    reference = f"daily:{user.id}:{today.isoformat()}"

    reward = add_reward(
        db=db,
        user_id=user.id,
        activity_type="daily_login",
        points=REWARD_VALUES["daily_login"],
        reference=reference,
        description="Daily VIKI activity bonus",
    )

    db.commit()

    return {
        "success": True,
        "points_awarded": reward.points if reward else 0,
        "message": "Daily reward processed",
    }
