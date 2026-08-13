from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import current_user
from ..models import Follow, Post, User
import os
import uuid


router = APIRouter(
    prefix="/profiles",
    tags=["Profiles"],
)


@router.get("/{username}")
def get_profile(
    username: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(User).filter(
        User.username == username.lower()
    ).first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    followers = db.query(Follow).filter(
        Follow.following_id == profile.id
    ).count()

    following = db.query(Follow).filter(
        Follow.follower_id == profile.id
    ).count()

    posts = db.query(Post).filter(
        Post.user_id == profile.id
    ).count()

    is_following = db.query(Follow).filter(
        Follow.follower_id == user.id,
        Follow.following_id == profile.id,
    ).first() is not None

    return {
        "id": profile.id,
        "username": profile.username,
        "full_name": profile.full_name,
        "bio": profile.bio,
        "avatar_url": profile.avatar_url,
        "is_creator": bool(profile.is_creator),
        "followers": followers,
        "following": following,
        "posts": posts,
        "is_following": is_following,
        "is_me": profile.id == user.id,
    }


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Upload or replace the authenticated user's profile picture."""

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG, WEBP, and GIF images are allowed.",
        )

    data = await file.read()

    # Prevent extremely large uploads.
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="Profile picture must be 5 MB or smaller.",
        )

    extension = allowed_types[file.content_type]
    filename = f"{user.id}-{uuid.uuid4().hex}{extension}"

    upload_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../uploads/avatars")
    )
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as output:
        output.write(data)

    avatar_url = f"/uploads/avatars/{filename}"

    user.avatar_url = avatar_url
    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "avatar_url": avatar_url,
    }
