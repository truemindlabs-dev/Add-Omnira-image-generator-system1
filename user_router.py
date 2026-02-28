"""
routers/user_router.py
GET /api/user/me      — Info user saat ini
GET /api/user/stats   — Statistik penggunaan user
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from auth import get_current_user, UserContext
from database import get_db, ImageRecord, MemoryStore

router = APIRouter()


@router.get("/user/me")
async def get_me(user: UserContext = Depends(get_current_user)):
    """Info user yang sedang login."""
    return {
        "status":   "success",
        "user_id":  user.user_id,
        "email":    user.email,
        "name":     user.name,
        "picture":  user.picture,
        "provider": user.provider,
    }


@router.get("/user/stats")
async def get_stats(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Statistik penggunaan user."""
    total_images = await db.execute(
        select(func.count()).where(ImageRecord.user_id == user.user_id)
    )
    total_memory = await db.execute(
        select(func.count()).where(MemoryStore.user_id == user.user_id)
    )

    style_result = await db.execute(
        select(ImageRecord.style, func.count().label("count"))
        .where(ImageRecord.user_id == user.user_id)
        .group_by(ImageRecord.style)
    )

    return {
        "status":        "success",
        "user_id":       user.user_id,
        "email":         user.email,
        "total_images":  total_images.scalar(),
        "total_memory":  total_memory.scalar(),
        "styles_used":   {r[0]: r[1] for r in style_result.all()},
    }
