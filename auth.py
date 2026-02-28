"""
auth.py — Autentikasi Gmail + Base44
Verifikasi JWT token yang dikirim dari Base44 frontend.
"""

from fastapi import HTTPException, Header, Depends
from typing import Optional
import jwt
import httpx
from pydantic import BaseModel
from config import settings
import logging

logger = logging.getLogger(__name__)


class UserContext(BaseModel):
    """Data user yang terverifikasi dari token."""
    user_id: str
    email: str
    name: str = ""
    picture: str = ""
    provider: str = "google"


# Cache Google public keys
_google_keys_cache: dict = {}


async def get_google_public_keys() -> dict:
    """Ambil Google public keys untuk verifikasi JWT."""
    global _google_keys_cache
    if _google_keys_cache:
        return _google_keys_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://www.googleapis.com/oauth2/v3/certs")
        _google_keys_cache = resp.json()
    return _google_keys_cache


def decode_base44_token(token: str) -> dict:
    """
    Decode JWT dari Base44.
    Base44 mengirim token dengan format standar JWT.
    Payload berisi: user_id, email, name, picture.
    """
    try:
        # Mode development: decode tanpa verifikasi signature
        if settings.DEBUG or settings.JWT_SECRET == "GANTI_DENGAN_SECRET_KAMU":
            payload = jwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload

        # Mode production: verifikasi dengan secret
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token sudah expired. Silakan login ulang.")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Token tidak valid: {str(e)}")


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None),
) -> UserContext:
    """
    Dependency untuk mendapatkan user saat ini.

    Base44 mengirim user info via:
    1. Authorization: Bearer <jwt_token>  — cara standar
    2. X-User-Id + X-User-Email headers   — cara alternatif Base44

    Untuk development/testing, gunakan header X-User-* langsung.
    """

    # --- Cara 1: JWT Token ---
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            payload = decode_base44_token(token)
            return UserContext(
                user_id=payload.get("sub") or payload.get("user_id") or payload.get("id", "unknown"),
                email=payload.get("email", ""),
                name=payload.get("name", ""),
                picture=payload.get("picture", ""),
            )
        except HTTPException:
            pass  # Coba cara lain

    # --- Cara 2: Header langsung dari Base44 ---
    if x_user_id and x_user_email:
        return UserContext(
            user_id=x_user_id,
            email=x_user_email,
        )

    # --- Development mode: anonymous user ---
    if settings.DEBUG:
        return UserContext(
            user_id="dev_user_001",
            email="dev@omnira.ai",
            name="Developer",
        )

    raise HTTPException(
        401,
        "Autentikasi diperlukan. Kirim Authorization header atau login via Gmail Base44."
    )


def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None),
) -> Optional[UserContext]:
    """User opsional — tidak raise error jika tidak ada token."""
    try:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            get_current_user(authorization, x_user_id, x_user_email)
        )
    except HTTPException:
        return None
