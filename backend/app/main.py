from datetime import datetime, timezone
import secrets
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import json
import os
import cloudinary
import cloudinary.uploader
import httpx

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .dependencies import current_user
from .models import (
    Comment,
    Deposit,
    Beneficiary,
    Withdrawal,
    Follow,
    LedgerEntry,
    Like,
    Post,
    User,
    Wallet,
    RewardLedger,
)
from .schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
    WalletResponse,
)
from .security import create_access_token, hash_password, verify_password
from .currencies import SUPPORTED_CURRENCIES, is_supported_currency
from .routers.monetization import router as monetization_router
from .routers.discover import router as discover_router
from .routers.profile import router as profile_router
from .routers.rewards import router as rewards_router, add_reward



class ExchangeRequest(BaseModel):
    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)
    amount: float = Field(gt=0)


class WithdrawalRequest(BaseModel):
    beneficiary_id: int = Field(gt=0)
    amount: float = Field(gt=0, le=100000)


class BeneficiaryRequest(BaseModel):
    beneficiary_type: str = Field(min_length=3, max_length=30)
    country: str = Field(min_length=2, max_length=2)
    currency: str = Field(min_length=3, max_length=3)
    provider: str = Field(min_length=2, max_length=50)
    account_name: str = Field(min_length=2, max_length=150)
    account_number: str = Field(min_length=3, max_length=150)


class DepositRequest(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    amount: float = Field(gt=0, le=100000)
    provider: str = Field(min_length=2, max_length=50)

Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="VIKI API",
    version="1.1.0",
    description="VIKI social media and creator economy API",
)


# =========================
# CLOUDINARY MEDIA STORAGE
# =========================

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(monetization_router)
app.include_router(discover_router)
app.include_router(profile_router)
app.include_router(rewards_router)


class PostCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    media_url: str = Field(default="", max_length=1000)
    media_type: str = Field(default="none", max_length=20)
    music_url: str = Field(default="", max_length=1000)
    music_title: str = Field(default="", max_length=255)
    music_artist: str = Field(default="", max_length=255)


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


@app.get("/")
def root():
    return {
        "app": "VIKI",
        "status": "online",
        "message": "Create. Connect. Earn.",
        "version": "1.1.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# =========================
# AUTH
# =========================

@app.post("/auth/register", response_model=LoginResponse)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    username = data.username.strip().lower()
    email = str(data.email).lower()

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, "Username already exists")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email already exists")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(data.password),
        full_name=data.full_name.strip(),
    )

    db.add(user)
    db.flush()

    currency = data.currency.upper()

    if not is_supported_currency(currency):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency: {currency}",
        )

    db.add(
        Wallet(
            user_id=user.id,
            currency=currency,
            available=0,
            pending=0,
        )
    )

    db.commit()
    db.refresh(user)

    return LoginResponse(
        access_token=create_access_token(user.id),
        user=user,
    )


@app.post("/auth/login", response_model=LoginResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower()

    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    return LoginResponse(
        access_token=create_access_token(user.id),
        user=user,
    )


@app.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user


# =========================
# PROFILE
# =========================

@app.get("/users/{username}")
def get_profile(
    username: str,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.username == username.lower()
    ).first()

    if not user:
        raise HTTPException(404, "User not found")

    followers = db.query(func.count(Follow.id)).filter(
        Follow.following_id == user.id
    ).scalar()

    following = db.query(func.count(Follow.id)).filter(
        Follow.follower_id == user.id
    ).scalar()

    posts = db.query(func.count(Post.id)).filter(
        Post.user_id == user.id
    ).scalar()

    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "bio": user.bio,
        "avatar_url": user.avatar_url,
        "is_creator": user.is_creator,
        "followers": followers,
        "following": following,
        "posts": posts,
        "created_at": user.created_at,
    }


# =========================
# FOLLOW SYSTEM
# =========================

@app.post("/users/{username}/follow")
def follow_user(
    username: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(
        User.username == username.lower()
    ).first()

    if not target:
        raise HTTPException(404, "User not found")

    if target.id == user.id:
        raise HTTPException(400, "You cannot follow yourself")

    existing = db.query(Follow).filter(
        Follow.follower_id == user.id,
        Follow.following_id == target.id,
    ).first()

    if existing:
        return {
            "following": True,
            "message": "Already following",
        }

    db.add(
        Follow(
            follower_id=user.id,
            following_id=target.id,
        )
    )

    add_reward(
        db=db,
        user_id=target.id,
        activity_type="follower_gained",
        points=5,
        reference=f"follow:{user.id}:{target.id}",
        description=f"New follower: @{user.username}",
    )

    db.commit()

    return {
        "following": True,
        "username": target.username,
    }


@app.delete("/users/{username}/follow")
def unfollow_user(
    username: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(
        User.username == username.lower()
    ).first()

    if not target:
        raise HTTPException(404, "User not found")

    deleted = db.query(Follow).filter(
        Follow.follower_id == user.id,
        Follow.following_id == target.id,
    ).delete()

    db.commit()

    return {
        "following": False,
        "removed": bool(deleted),
    }


# =========================
# MEDIA UPLOAD
# =========================

@app.post("/upload-media")
async def upload_media(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
):
    if not file.filename:
        raise HTTPException(400, "No file selected")

    content_type = (file.content_type or "").lower()

    allowed = {
        "video/mp4": "video",
        "video/webm": "video",
        "video/quicktime": "video",
        "image/jpeg": "image",
        "image/png": "image",
        "image/webp": "image",
    }

    if content_type not in allowed:
        raise HTTPException(
            400,
            "Only MP4, WebM, MOV, JPG, PNG and WEBP files are allowed",
        )

    media_type = allowed[content_type]

    # 100 MB maximum
    contents = await file.read()

    if len(contents) > 100 * 1024 * 1024:
        raise HTTPException(413, "File is too large. Maximum size is 100 MB.")

    try:
        result = cloudinary.uploader.upload(
            contents,
            resource_type="video" if media_type == "video" else "image",
            folder="viki",
        )

        return {
            "success": True,
            "url": result["secure_url"],
            "media_type": media_type,
            "public_id": result.get("public_id"),
        }

    except Exception as exc:
        raise HTTPException(
            500,
            f"Media upload failed: {str(exc)}",
        )


# =========================
# ONLINE MUSIC SEARCH
# =========================

@app.get("/music/search")
def search_music(
    q: str,
    limit: int = 10,
):
    q = q.strip()

    if not q:
        return {"count": 0, "tracks": []}

    limit = max(1, min(limit, 25))

    url = (
        "https://itunes.apple.com/search"
        f"?term={quote(q)}"
        "&media=music"
        "&entity=song"
        f"&limit={limit}"
    )

    try:
        request = Request(
            url,
            headers={"User-Agent": "VIKI/1.1"},
        )

        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Music search unavailable: {exc}",
        )

    tracks = []

    for item in payload.get("results", []):
        preview = item.get("previewUrl")

        if not preview:
            continue

        tracks.append({
            "id": item.get("trackId"),
            "title": item.get("trackName", ""),
            "artist": item.get("artistName", ""),
            "album": item.get("collectionName", ""),
            "artwork_url": item.get("artworkUrl100", ""),
            "preview_url": preview,
            "store_url": item.get("trackViewUrl", ""),
        })

    return {
        "count": len(tracks),
        "tracks": tracks,
    }


# =========================
# POSTS
# =========================

@app.post("/posts")
def create_post(
    data: PostCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    post = Post(
        user_id=user.id,
        content=data.content.strip(),
        media_url=data.media_url.strip(),
        media_type=data.media_type.strip().lower(),
        music_url=data.music_url.strip(),
        music_title=data.music_title.strip(),
        music_artist=data.music_artist.strip(),
    )

    db.add(post)
    db.flush()

    add_reward(
        db=db,
        user_id=user.id,
        activity_type="post",
        points=10,
        reference=f"post:{post.id}",
        description="VIKI post creation reward",
    )

    db.commit()
    db.refresh(post)

    return {
        "id": post.id,
        "message": "Post created",
        "post": {
            "id": post.id,
            "content": post.content,
            "media_url": post.media_url,
            "media_type": post.media_type,
            "created_at": post.created_at,
        },
    }


@app.get("/posts/{post_id}")
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)

    if not post:
        raise HTTPException(404, "Post not found")

    author = db.get(User, post.user_id)

    likes = db.query(func.count(Like.id)).filter(
        Like.post_id == post.id
    ).scalar()

    comments = db.query(func.count(Comment.id)).filter(
        Comment.post_id == post.id
    ).scalar()

    return {
        "id": post.id,
        "author": {
            "id": author.id,
            "username": author.username,
            "full_name": author.full_name,
            "avatar_url": author.avatar_url,
        },
        "content": post.content,
        "media_url": post.media_url,
        "media_type": post.media_type,
        "music_url": post.music_url,
        "music_title": post.music_title,
        "music_artist": post.music_artist,
        "likes": likes,
        "comments": comments,
        "created_at": post.created_at,
    }


@app.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)

    if not post:
        raise HTTPException(404, "Post not found")

    if post.user_id != user.id and not user.is_admin:
        raise HTTPException(403, "You cannot delete this post")

    db.query(Like).filter(
        Like.post_id == post.id
    ).delete()

    db.query(Comment).filter(
        Comment.post_id == post.id
    ).delete()

    db.delete(post)
    db.commit()

    return {
        "deleted": True,
        "post_id": post_id,
    }


# =========================
# FEED
# =========================

@app.get("/feed")
def feed(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
):
    limit = max(1, min(limit, 50))

    following_ids = [
        row.following_id
        for row in db.query(Follow).filter(
            Follow.follower_id == user.id
        ).all()
    ]

    following_ids.append(user.id)

    posts = db.query(Post).filter(
        Post.user_id.in_(following_ids)
    ).order_by(
        Post.created_at.desc()
    ).limit(limit).all()

    result = []

    for post in posts:
        author = db.get(User, post.user_id)

        likes = db.query(func.count(Like.id)).filter(
            Like.post_id == post.id
        ).scalar()

        comments = db.query(func.count(Comment.id)).filter(
            Comment.post_id == post.id
        ).scalar()

        liked = db.query(Like).filter(
            Like.post_id == post.id,
            Like.user_id == user.id,
        ).first() is not None

        result.append({
            "id": post.id,
            "author": {
                "id": author.id,
                "username": author.username,
                "full_name": author.full_name,
                "avatar_url": author.avatar_url,
            },
            "content": post.content,
            "media_url": post.media_url,
            "media_type": post.media_type,
            "music_url": post.music_url,
            "music_title": post.music_title,
            "music_artist": post.music_artist,
            "likes": likes,
            "comments": comments,
            "liked_by_me": liked,
            "created_at": post.created_at,
        })

    return {
        "count": len(result),
        "posts": result,
    }


# =========================
# LIKES
# =========================

@app.post("/posts/{post_id}/like")
def like_post(
    post_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)

    if not post:
        raise HTTPException(404, "Post not found")

    existing = db.query(Like).filter(
        Like.user_id == user.id,
        Like.post_id == post.id,
    ).first()

    if existing:
        return {
            "liked": True,
            "message": "Already liked",
        }

    db.add(
        Like(
            user_id=user.id,
            post_id=post.id,
        )
    )

    if post.user_id != user.id:
        add_reward(
            db=db,
            user_id=post.user_id,
            activity_type="like_received",
            points=1,
            reference=f"like:{user.id}:{post.id}",
            description=f"Like received from @{user.username}",
        )

    db.commit()

    return {
        "liked": True,
        "post_id": post.id,
    }


@app.delete("/posts/{post_id}/like")
def unlike_post(
    post_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    deleted = db.query(Like).filter(
        Like.user_id == user.id,
        Like.post_id == post_id,
    ).delete()

    db.commit()

    return {
        "liked": False,
        "removed": bool(deleted),
    }


# =========================
# COMMENTS
# =========================

@app.post("/posts/{post_id}/comments")
def create_comment(
    post_id: int,
    data: CommentCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)

    if not post:
        raise HTTPException(404, "Post not found")

    comment = Comment(
        user_id=user.id,
        post_id=post.id,
        content=data.content.strip(),
    )

    db.add(comment)
    db.flush()

    if post.user_id != user.id:
        add_reward(
            db=db,
            user_id=post.user_id,
            activity_type="comment_received",
            points=3,
            reference=f"comment:{comment.id}",
            description=f"Comment received from @{user.username}",
        )

    db.commit()
    db.refresh(comment)

    return {
        "id": comment.id,
        "post_id": post.id,
        "content": comment.content,
        "author": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
        },
        "created_at": comment.created_at,
    }


@app.get("/posts/{post_id}/comments")
def get_comments(
    post_id: int,
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)

    if not post:
        raise HTTPException(404, "Post not found")

    comments = db.query(Comment).filter(
        Comment.post_id == post_id
    ).order_by(
        Comment.created_at.asc()
    ).all()

    result = []

    for comment in comments:
        author = db.get(User, comment.user_id)

        result.append({
            "id": comment.id,
            "content": comment.content,
            "author": {
                "id": author.id,
                "username": author.username,
                "full_name": author.full_name,
                "avatar_url": author.avatar_url,
            },
            "created_at": comment.created_at,
        })

    return {
        "count": len(result),
        "comments": result,
    }




@app.post("/beneficiaries")
def create_beneficiary(
    data: BeneficiaryRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    beneficiary_type = data.beneficiary_type.strip().lower()
    country = data.country.strip().upper()
    currency = data.currency.strip().upper()
    provider = data.provider.strip()

    if beneficiary_type not in {"bank", "wallet"}:
        raise HTTPException(
            status_code=400,
            detail="Beneficiary type must be bank or wallet",
        )

    if not is_supported_currency(currency):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency: {currency}",
        )

    beneficiary = Beneficiary(
        user_id=user.id,
        beneficiary_type=beneficiary_type,
        country=country,
        currency=currency,
        provider=provider,
        account_name=data.account_name.strip(),
        account_number=data.account_number.strip(),
        status="pending",
    )

    db.add(beneficiary)
    db.commit()
    db.refresh(beneficiary)

    return {
        "success": True,
        "beneficiary": {
            "id": beneficiary.id,
            "type": beneficiary.beneficiary_type,
            "country": beneficiary.country,
            "currency": beneficiary.currency,
            "provider": beneficiary.provider,
            "account_name": beneficiary.account_name,
            "account_number": beneficiary.account_number,
            "status": beneficiary.status,
        },
    }


@app.get("/beneficiaries")
def list_beneficiaries(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(Beneficiary).filter(
        Beneficiary.user_id == user.id
    ).order_by(
        Beneficiary.created_at.desc()
    ).all()

    return {
        "count": len(rows),
        "beneficiaries": [
            {
                "id": row.id,
                "type": row.beneficiary_type,
                "country": row.country,
                "currency": row.currency,
                "provider": row.provider,
                "account_name": row.account_name,
                "account_number": row.account_number,
                "status": row.status,
            }
            for row in rows
        ],
    }


@app.delete("/beneficiaries/{beneficiary_id}")
def delete_beneficiary(
    beneficiary_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    beneficiary = db.query(Beneficiary).filter(
        Beneficiary.id == beneficiary_id,
        Beneficiary.user_id == user.id,
    ).first()

    if not beneficiary:
        raise HTTPException(
            status_code=404,
            detail="Beneficiary not found",
        )

    db.delete(beneficiary)
    db.commit()

    return {
        "success": True,
        "message": "Beneficiary deleted",
    }




@app.post("/wallets/withdraw")
def create_withdrawal(
    data: WithdrawalRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    beneficiary = db.query(Beneficiary).filter(
        Beneficiary.id == data.beneficiary_id,
        Beneficiary.user_id == user.id,
    ).first()

    if not beneficiary:
        raise HTTPException(
            status_code=404,
            detail="Beneficiary not found",
        )

    currency = beneficiary.currency.upper()
    amount = round(float(data.amount), 2)

    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Withdrawal amount must be greater than zero",
        )

    wallet = db.query(Wallet).filter(
        Wallet.user_id == user.id,
        Wallet.currency == currency,
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail=f"{currency} wallet not found",
        )

    fee = 0.0
    total = round(amount + fee, 2)

    if wallet.available < total:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient {currency} balance",
        )

    provider_reference = "VIKI-WD-" + secrets.token_hex(12)

    # Reserve the money while the provider processes the withdrawal.
    wallet.available = round(
        wallet.available - total,
        2,
    )

    wallet.pending = round(
        wallet.pending + total,
        2,
    )

    withdrawal = Withdrawal(
        user_id=user.id,
        beneficiary_id=beneficiary.id,
        currency=currency,
        amount=amount,
        fee=fee,
        provider="pending_provider",
        provider_reference=provider_reference,
        status="pending",
    )

    db.add(withdrawal)

    db.add(
        LedgerEntry(
            user_id=user.id,
            entry_type="withdrawal_pending",
            amount=-total,
            currency=currency,
            description=(
                f"Withdrawal pending to "
                f"{beneficiary.account_name}"
            ),
            reference=provider_reference,
        )
    )

    db.commit()
    db.refresh(withdrawal)

    return {
        "success": True,
        "message": "Withdrawal created and funds reserved",
        "withdrawal": {
            "id": withdrawal.id,
            "currency": withdrawal.currency,
            "amount": withdrawal.amount,
            "fee": withdrawal.fee,
            "total": total,
            "provider": withdrawal.provider,
            "provider_reference": withdrawal.provider_reference,
            "status": withdrawal.status,
            "beneficiary": {
                "id": beneficiary.id,
                "type": beneficiary.beneficiary_type,
                "country": beneficiary.country,
                "currency": beneficiary.currency,
                "provider": beneficiary.provider,
                "account_name": beneficiary.account_name,
                "account_number": beneficiary.account_number,
            },
        },
        "wallet": {
            "currency": currency,
            "available": wallet.available,
            "pending": wallet.pending,
        },
    }


@app.get("/wallets/withdrawals")
def list_withdrawals(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(Withdrawal).filter(
        Withdrawal.user_id == user.id
    ).order_by(
        Withdrawal.created_at.desc()
    ).all()

    return {
        "count": len(rows),
        "withdrawals": [
            {
                "id": row.id,
                "currency": row.currency,
                "amount": row.amount,
                "fee": row.fee,
                "provider": row.provider,
                "provider_reference": row.provider_reference,
                "status": row.status,
                "beneficiary_id": row.beneficiary_id,
                "created_at": row.created_at,
                "completed_at": row.completed_at,
            }
            for row in rows
        ],
    }


# =========================
# WALLET
# =========================


@app.get("/currencies")
def currencies():
    return {
        "currencies": [
            {
                "code": code,
                **details,
            }
            for code, details in SUPPORTED_CURRENCIES.items()
        ]
    }



@app.post("/wallets/create")
def create_wallet(
    currency: str = "USD",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    currency = currency.upper()

    if not is_supported_currency(currency):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency: {currency}",
        )

    existing = db.query(Wallet).filter(
        Wallet.user_id == user.id,
        Wallet.currency == currency,
    ).first()

    if existing:
        return {
            "success": True,
            "created": False,
            "message": "Wallet already exists",
            "wallet": {
                "id": existing.id,
                "currency": existing.currency,
                "available": existing.available,
                "pending": existing.pending,
            },
        }

    wallet = Wallet(
        user_id=user.id,
        currency=currency,
        available=0,
        pending=0,
    )

    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    return {
        "success": True,
        "created": True,
        "message": f"{currency} wallet created",
        "wallet": {
            "id": wallet.id,
            "currency": wallet.currency,
            "available": wallet.available,
            "pending": wallet.pending,
        },
    }

@app.get("/wallets")
def wallets(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    wallet_rows = db.query(Wallet).filter(
        Wallet.user_id == user.id
    ).order_by(
        Wallet.currency.asc()
    ).all()

    return {
        "user_id": user.id,
        "count": len(wallet_rows),
        "wallets": [
            {
                "id": wallet.id,
                "currency": wallet.currency,
                "available": wallet.available,
                "pending": wallet.pending,
            }
            for wallet in wallet_rows
        ],
    }




@app.post("/wallets/deposit")
def create_deposit(
    data: DepositRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    currency = data.currency.upper()
    amount = round(float(data.amount), 2)
    provider = data.provider.strip().lower()

    if not is_supported_currency(currency):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency: {currency}",
        )

    wallet = db.query(Wallet).filter(
        Wallet.user_id == user.id,
        Wallet.currency == currency,
    ).first()

    if not wallet:
        wallet = Wallet(
            user_id=user.id,
            currency=currency,
            available=0,
            pending=0,
        )
        db.add(wallet)
        db.flush()

    provider_reference = (
        "VIKI-DEP-" + secrets.token_hex(12)
    )

    deposit = Deposit(
        user_id=user.id,
        currency=currency,
        amount=amount,
        provider=provider,
        provider_reference=provider_reference,
        status="pending",
    )

    db.add(deposit)
    db.commit()
    db.refresh(deposit)

    return {
        "success": True,
        "message": "Deposit created and awaiting payment verification",
        "development_only": True,
        "deposit": {
            "id": deposit.id,
            "currency": deposit.currency,
            "amount": deposit.amount,
            "provider": deposit.provider,
            "provider_reference": deposit.provider_reference,
            "status": deposit.status,
        },
    }

@app.post("/wallets/exchange")
def exchange_wallet(
    data: ExchangeRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    from_currency = data.from_currency.upper()
    to_currency = data.to_currency.upper()
    amount = round(float(data.amount), 2)

    if from_currency == to_currency:
        raise HTTPException(
            status_code=400,
            detail="Source and destination currencies must be different",
        )

    if not is_supported_currency(from_currency):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency: {from_currency}",
        )

    if not is_supported_currency(to_currency):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency: {to_currency}",
        )

    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero",
        )

    source = db.query(Wallet).filter(
        Wallet.user_id == user.id,
        Wallet.currency == from_currency,
    ).first()

    if not source:
        raise HTTPException(
            status_code=404,
            detail=f"{from_currency} wallet not found",
        )

    if source.available < amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient {from_currency} balance",
        )

    destination = db.query(Wallet).filter(
        Wallet.user_id == user.id,
        Wallet.currency == to_currency,
    ).first()

    if not destination:
        destination = Wallet(
            user_id=user.id,
            currency=to_currency,
            available=0,
            pending=0,
        )
        db.add(destination)
        db.flush()

    # ---------------------------------------------------------
    # VIKI FX BASE RATES
    #
    # Each value represents how many units of that currency
    # equal approximately 1 USD.
    #
    # These are server-side rates. They are NOT supplied by
    # the client.
    #
    # Before real-money operation, replace these with a
    # verified live FX provider and add appropriate spread/
    # fee handling.
    # ---------------------------------------------------------

    usd_rates = {
        "USD": 1.0,
        "EUR": 0.85,
        "GBP": 0.74,
        "NGN": 1362.95,
        "XOF": 560.00,
        "GHS": 12.30,
        "CAD": 1.37,
        "AUD": 1.52,
        "JPY": 147.00,
        "CNY": 7.18,
        "ZAR": 17.80,
        "INR": 87.50,
    }

    from_rate = usd_rates.get(from_currency)
    to_rate = usd_rates.get(to_currency)

    if from_rate is None or to_rate is None:
        raise HTTPException(
            status_code=400,
            detail="Exchange rate is not configured",
        )

    # Convert source -> USD -> destination.
    usd_value = amount / from_rate
    converted = round(usd_value * to_rate, 2)

    if converted <= 0:
        raise HTTPException(
            status_code=400,
            detail="Conversion amount is too small",
        )

    reference = "VIKI-FX-" + secrets.token_hex(12)

    source.available = round(
        source.available - amount,
        2,
    )

    destination.available = round(
        destination.available + converted,
        2,
    )

    db.add(
        LedgerEntry(
            user_id=user.id,
            entry_type="currency_exchange_sent",
            amount=-amount,
            currency=from_currency,
            description=f"Exchanged {from_currency} to {to_currency}",
            reference=reference,
        )
    )

    db.add(
        LedgerEntry(
            user_id=user.id,
            entry_type="currency_exchange_received",
            amount=converted,
            currency=to_currency,
            description=f"Received {to_currency} from {from_currency} exchange",
            reference=reference,
        )
    )

    db.commit()

    return {
        "success": True,
        "reference": reference,
        "from": {
            "currency": from_currency,
            "amount": amount,
            "remaining": source.available,
        },
        "to": {
            "currency": to_currency,
            "amount": converted,
            "balance": destination.available,
        },
        "rate": round(to_rate / from_rate, 8),
        "base_currency": "USD",
        "status": "completed",
    }


@app.get("/wallet", response_model=WalletResponse)
def wallet(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    wallet = db.query(Wallet).filter(
        Wallet.user_id == user.id
    ).first()

    if not wallet:
        raise HTTPException(404, "Wallet not found")

    return wallet


@app.post("/admin/dev/fund-wallet")
def dev_fund_wallet(
    username: str,
    amount: float = 10.0,
    currency: str = "USD",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    DEVELOPMENT ONLY.

    Allows an administrator to credit a user's wallet for local
    development/testing. This is not a real-money deposit system.
    """

    if not user.is_admin:
        raise HTTPException(403, "Admin access required")

    amount = round(float(amount), 2)
    currency = currency.upper()

    if amount <= 0:
        raise HTTPException(400, "Amount must be greater than zero")

    if not is_supported_currency(currency):
        raise HTTPException(
            400,
            f"Unsupported currency: {currency}",
        )

    target = db.query(User).filter(
        User.username == username.lower()
    ).first()

    if not target:
        raise HTTPException(404, "User not found")

    wallet = db.query(Wallet).filter(
        Wallet.user_id == target.id,
        Wallet.currency == currency,
    ).first()

    if not wallet:
        wallet = Wallet(
            user_id=target.id,
            currency=currency,
            available=0,
            pending=0,
        )
        db.add(wallet)
        db.flush()

    wallet.available = round(wallet.available + amount, 2)

    reference = "DEV-FUND-" + secrets.token_hex(12)

    db.add(
        LedgerEntry(
            user_id=target.id,
            entry_type="dev_funding",
            amount=amount,
            currency=currency,
            description="Development wallet funding",
            reference=reference,
        )
    )

    db.commit()

    return {
        "success": True,
        "development_only": True,
        "username": target.username,
        "amount": amount,
        "currency": currency,
        "available": wallet.available,
        "reference": reference,
    }


@app.get("/wallet/ledger")
def ledger(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    entries = db.query(LedgerEntry).filter(
        LedgerEntry.user_id == user.id
    ).order_by(
        LedgerEntry.created_at.desc()
    ).all()

    return [
        {
            "id": entry.id,
            "type": entry.entry_type,
            "amount": entry.amount,
            "currency": entry.currency,
            "description": entry.description,
            "reference": entry.reference,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]
