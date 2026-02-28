"""
routers/store_router.py
POST /api/store           — Simpan data ke memory AI
GET  /api/retrieve/{key}  — Ambil data dari memory
DELETE /api/store/{key}   — Hapus data
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid

from auth import get_current_user, UserContext
from database import get_db, MemoryStore

router = APIRouter()


# ================================================================
# SCHEMAS
# ================================================================

class StoreRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=500,
                     description="Key unik untuk menyimpan data")
    value: Any = Field(..., description="Data yang disimpan (JSON)")
    namespace: Optional[str] = Field(default="default",
                                     description="Namespace untuk grouping")


class StoreResponse(BaseModel):
    status: str
    key: str
    user_id: str
    timestamp: str
    message: str


class RetrieveResponse(BaseModel):
    status: str
    key: str
    value: Any
    user_id: str
    created_at: str
    updated_at: str


# ================================================================
# ENDPOINTS
# ================================================================

@router.post("/store", response_model=StoreResponse)
async def store_data(
    req: StoreRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Simpan data ke AI memory store.
    Key dibuat unik per user — user A tidak bisa akses data user B.

    Contoh penggunaan:
    POST /api/store
    {
      "key": "last_prompt",
      "value": {"prompt": "bunga merah", "style": "mandala", "timestamp": "..."}
    }
    """
    # Key dibuat user-scoped
    scoped_key = f"{user.user_id}::{req.namespace}::{req.key}"
    timestamp  = datetime.now(timezone.utc)

    # Cek apakah sudah ada
    existing = await db.execute(
        select(MemoryStore).where(MemoryStore.key == scoped_key)
    )
    record = existing.scalar_one_or_none()

    payload = {
        "data":      req.value,
        "key":       req.key,
        "namespace": req.namespace,
        "user_id":   user.user_id,
        "email":     user.email,
        "saved_at":  timestamp.isoformat(),
    }

    if record:
        record.value      = payload
        record.updated_at = timestamp
    else:
        record = MemoryStore(
            id=str(uuid.uuid4()),
            key=scoped_key,
            user_id=user.user_id,
            value=payload,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(record)

    await db.flush()

    return StoreResponse(
        status="success",
        key=req.key,
        user_id=user.user_id,
        timestamp=timestamp.isoformat(),
        message=f"✅ Data '{req.key}' berhasil disimpan",
    )


@router.get("/retrieve/{key}", response_model=RetrieveResponse)
async def retrieve_data(
    key: str,
    namespace: str = "default",
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ambil data dari AI memory store berdasarkan key.

    Data yang diambil hanya milik user yang sedang login.
    """
    scoped_key = f"{user.user_id}::{namespace}::{key}"
    result = await db.execute(
        select(MemoryStore).where(MemoryStore.key == scoped_key)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(404, f"Data dengan key '{key}' tidak ditemukan untuk user ini")

    return RetrieveResponse(
        status="success",
        key=key,
        value=record.value.get("data"),
        user_id=user.user_id,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.get("/store/list")
async def list_keys(
    namespace: str = "default",
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Daftar semua key yang tersimpan untuk user ini."""
    prefix = f"{user.user_id}::{namespace}::"
    result = await db.execute(
        select(MemoryStore).where(MemoryStore.user_id == user.user_id)
    )
    records = result.scalars().all()
    return {
        "status":    "success",
        "user_id":   user.user_id,
        "namespace": namespace,
        "keys": [
            {
                "key":        r.key.replace(prefix, ""),
                "updated_at": r.updated_at.isoformat()
            }
            for r in records if r.key.startswith(prefix)
        ]
    }


@router.delete("/store/{key}")
async def delete_data(
    key: str,
    namespace: str = "default",
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hapus data dari memory store."""
    scoped_key = f"{user.user_id}::{namespace}::{key}"
    await db.execute(
        delete(MemoryStore).where(MemoryStore.key == scoped_key)
    )
    return {"status": "success", "message": f"Key '{key}' dihapus"}
