"""
routers/image_router.py
POST /api/generate-image — Endpoint utama generator gambar AI
GET  /api/image/{key}    — Serve file PNG
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid, io, base64

from auth import get_current_user, UserContext
from image_engine import generate_image, image_to_base64, image_to_bytes, GenerationConfig, ImageStyle
from storage import storage, LocalStorage
from database import get_db, ImageRecord
from config import settings

router = APIRouter()


# ================================================================
# SCHEMAS
# ================================================================

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000,
                        description="Deskripsi gambar yang ingin digenerate")
    width: int  = Field(default=512, ge=256, le=1024)
    height: int = Field(default=512, ge=256, le=1024)
    style: ImageStyle = Field(default=ImageStyle.AUTO,
                               description="Style gambar. 'auto' = deteksi dari prompt")
    seed: Optional[int] = Field(default=None, description="Seed untuk hasil konsisten")
    return_format: Literal["base64", "url"] = Field(
        default="base64",
        description="Format return. 'base64' untuk inline Base44, 'url' untuk download link"
    )


class GenerateResponse(BaseModel):
    status: str
    image_id: str
    image_url: str
    image_data: Optional[str] = None   # base64 PNG jika return_format=base64
    prompt: str
    user_id: str
    user_email: str
    timestamp: str
    style_used: str
    resolution: str
    alpha_verified: bool
    transparent_pct: float
    message: str


# ================================================================
# ENDPOINTS
# ================================================================

@router.post("/generate-image", response_model=GenerateResponse)
async def generate_image_endpoint(
    req: GenerateRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate gambar AI dari prompt dengan true RGBA alpha transparency.

    Gambar diikat ke user yang login (Gmail via Base44).
    Hasil disimpan ke storage dan database.

    Response compatible dengan Base44 UI:
    - image_data: base64 untuk <img src="data:image/png;base64,...">
    - image_url : URL langsung
    """
    try:
        # 1. Generate gambar
        cfg = GenerationConfig(
            prompt=req.prompt,
            width=req.width,
            height=req.height,
            style=req.style,
            seed=req.seed,
        )
        result = generate_image(cfg)

        # 2. Generate unique key
        image_key = f"{user.user_id[:8]}_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc)

        # 3. Simpan ke storage
        store = storage()
        image_url = await store.save(result.image, image_key)

        # 4. Simpan record ke database
        record = ImageRecord(
            id=str(uuid.uuid4()),
            user_id=user.user_id,
            user_email=user.email,
            prompt=req.prompt,
            image_url=image_url,
            image_key=image_key,
            resolution=f"{req.width}x{req.height}",
            style=result.style_used,
            meta_data={
                "seed": req.seed,
                "alpha_verified": result.alpha_verified,
                "transparent_pct": result.transparent_pct,
                "provider": user.provider,
            },
            created_at=timestamp,
        )
        db.add(record)
        await db.flush()

        # 5. Siapkan response
        response = GenerateResponse(
            status="success",
            image_id=image_key,
            image_url=image_url,
            prompt=req.prompt,
            user_id=user.user_id,
            user_email=user.email,
            timestamp=timestamp.isoformat(),
            style_used=result.style_used,
            resolution=f"{req.width}x{req.height}",
            alpha_verified=result.alpha_verified,
            transparent_pct=result.transparent_pct,
            message=f"✅ Gambar berhasil dibuat dengan style '{result.style_used}' | Alpha: {result.transparent_pct:.1f}% transparan",
        )

        if req.return_format == "base64":
            response.image_data = image_to_base64(result.image)

        return response

    except Exception as e:
        raise HTTPException(500, f"Gagal generate gambar: {str(e)}")


@router.get("/image/{key}")
async def serve_image(key: str):
    """
    Serve file PNG dari local storage.
    Endpoint ini dipakai jika return_format=url.
    """
    store = storage()
    if isinstance(store, LocalStorage):
        path = store.get_path(key)
        if not path or not __import__("os").path.exists(path):
            raise HTTPException(404, f"Gambar '{key}' tidak ditemukan")
        return FileResponse(path, media_type="image/png",
                           headers={"Cache-Control": "public, max-age=3600"})
    else:
        # Redirect ke URL cloud storage
        url = await store.get_url(key)
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url)


@router.get("/user/history")
async def get_user_history(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
):
    """Riwayat generate gambar milik user yang login."""
    result = await db.execute(
        select(ImageRecord)
        .where(ImageRecord.user_id == user.user_id)
        .order_by(desc(ImageRecord.created_at))
        .limit(limit).offset(offset)
    )
    records = result.scalars().all()
    return {
        "status": "success",
        "user_id": user.user_id,
        "user_email": user.email,
        "total": len(records),
        "history": [
            {
                "image_id":    r.image_key,
                "image_url":   r.image_url,
                "prompt":      r.prompt,
                "style":       r.style,
                "resolution":  r.resolution,
                "timestamp":   r.created_at.isoformat(),
            }
            for r in records
        ]
    }


@router.get("/user/gallery")
async def get_gallery(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=12, le=50),
):
    """Galeri gambar — format ringkas untuk UI Base44."""
    result = await db.execute(
        select(ImageRecord)
        .where(ImageRecord.user_id == user.user_id)
        .order_by(desc(ImageRecord.created_at))
        .limit(limit)
    )
    records = result.scalars().all()
    return {
        "status":  "success",
        "user_id": user.user_id,
        "gallery": [
            {"url": r.image_url, "prompt": r.prompt[:50], "id": r.image_key}
            for r in records
        ]
    }
