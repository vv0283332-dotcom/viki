from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import current_user
from ..models import Follow, User

router = APIRouter(
    prefix="/discover",
    tags=["Discover"],
)


@router.get("/users")
def search_users(
    q: str = "",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = q.strip().lower()

    query = db.query(User)

    if q:
        query = query.filter(
            or_(
                User.username.ilike(f"%{q}%"),
                User.full_name.ilike(f"%{q}%"),
            )
        )

    users = query.order_by(User.id.desc()).limit(30).all()

    following_ids = {
        row.following_id
        for row in db.query(Follow).filter(
            Follow.follower_id == user.id
        ).all()
    }

    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "is_creator": bool(u.is_creator),
                "is_following": u.id in following_ids,
            }
            for u in users
            if u.id != user.id
        ]
    }


@router.post("/follow/{user_id}")
def follow_user(
    user_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if user_id == user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot follow yourself",
        )

    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    existing = db.query(Follow).filter(
        Follow.follower_id == user.id,
        Follow.following_id == user_id,
    ).first()

    if existing:
        return {
            "success": True,
            "following": True,
            "message": "Already following",
        }

    db.add(
        Follow(
            follower_id=user.id,
            following_id=user_id,
        )
    )

    db.commit()

    return {
        "success": True,
        "following": True,
    }


@router.delete("/follow/{user_id}")
def unfollow_user(
    user_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(Follow).filter(
        Follow.follower_id == user.id,
        Follow.following_id == user_id,
    ).first()

    if existing:
        db.delete(existing)
        db.commit()

    return {
        "success": True,
        "following": False,
    }
