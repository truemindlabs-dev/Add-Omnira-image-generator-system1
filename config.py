"""
config.py — Konfigurasi Omnira Synora
Semua environment variable dikonfigurasi di sini.
"""

import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # === SERVER ===
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # === CORS ===
    ALLOWED_ORIGINS: List[str] = [
        "https://*.base44.com",
        "https://app.base44.com",
        "http://localhost:3000",
        "http://localhost:5173",
        "*",  # Ganti dengan domain Base44 kamu di production
    ]

    # === AUTH ===
    # Secret key untuk verifikasi JWT dari Base44/Google
    JWT_SECRET: str = os.getenv("JWT_SECRET", "GANTI_DENGAN_SECRET_KAMU")
    JWT_ALGORITHM: str = "HS256"

    # Google OAuth (untuk verifikasi token Gmail Base44)
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # === STORAGE ===
    # Pilih: "local" | "supabase" | "s3"
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "./storage/images")

    # Supabase (opsional)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "omnira-images")

    # AWS S3 (opsional)
    AWS_ACCESS_KEY: str = os.getenv("AWS_ACCESS_KEY", "")
    AWS_SECRET_KEY: str = os.getenv("AWS_SECRET_KEY", "")
    AWS_BUCKET: str = os.getenv("AWS_BUCKET", "omnira-images")
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-southeast-1")

    # === DATABASE ===
    # SQLite default, ganti ke PostgreSQL di production
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./omnira.db")

    # === IMAGE ===
    DEFAULT_RESOLUTION: int = 512
    MAX_RESOLUTION: int = 1024
    IMAGE_QUALITY: int = 95
    BASE_IMAGE_URL: str = os.getenv("BASE_IMAGE_URL", "http://localhost:8000/api/image")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# Buat direktori storage jika belum ada
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
