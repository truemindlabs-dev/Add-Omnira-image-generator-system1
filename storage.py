"""
storage.py — Storage Backend
Mendukung: Local filesystem | Supabase Storage | AWS S3
"""

import os, uuid, base64
from abc import ABC, abstractmethod
from config import settings
from image_engine import image_to_bytes
from PIL import Image


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, image: Image.Image, key: str) -> str:
        """Simpan gambar, return public URL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    async def get_url(self, key: str) -> str:
        pass


# ================================================================
# LOCAL STORAGE
# ================================================================
class LocalStorage(StorageBackend):
    def __init__(self):
        self.dir = settings.STORAGE_DIR
        os.makedirs(self.dir, exist_ok=True)

    async def save(self, image: Image.Image, key: str) -> str:
        path = os.path.join(self.dir, f"{key}.png")
        img_bytes = image_to_bytes(image)
        with open(path, "wb") as f:
            f.write(img_bytes)
        return f"{settings.BASE_IMAGE_URL}/{key}"

    async def delete(self, key: str) -> bool:
        path = os.path.join(self.dir, f"{key}.png")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    async def get_url(self, key: str) -> str:
        return f"{settings.BASE_IMAGE_URL}/{key}"

    def get_path(self, key: str) -> str:
        return os.path.join(self.dir, f"{key}.png")


# ================================================================
# SUPABASE STORAGE (opsional)
# ================================================================
class SupabaseStorage(StorageBackend):
    def __init__(self):
        try:
            from supabase import create_client
            self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            self.bucket = settings.SUPABASE_BUCKET
        except ImportError:
            raise RuntimeError("Install: pip install supabase")

    async def save(self, image: Image.Image, key: str) -> str:
        img_bytes = image_to_bytes(image)
        filename  = f"{key}.png"
        self.client.storage.from_(self.bucket).upload(
            filename, img_bytes,
            {"content-type": "image/png", "upsert": "true"}
        )
        public_url = self.client.storage.from_(self.bucket).get_public_url(filename)
        return public_url

    async def delete(self, key: str) -> bool:
        self.client.storage.from_(self.bucket).remove([f"{key}.png"])
        return True

    async def get_url(self, key: str) -> str:
        return self.client.storage.from_(self.bucket).get_public_url(f"{key}.png")


# ================================================================
# AWS S3 STORAGE (opsional)
# ================================================================
class S3Storage(StorageBackend):
    def __init__(self):
        try:
            import boto3
            self.s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY,
                aws_secret_access_key=settings.AWS_SECRET_KEY,
                region_name=settings.AWS_REGION,
            )
            self.bucket = settings.AWS_BUCKET
            self.region = settings.AWS_REGION
        except ImportError:
            raise RuntimeError("Install: pip install boto3")

    async def save(self, image: Image.Image, key: str) -> str:
        import io
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        filename = f"{key}.png"
        self.s3.upload_fileobj(
            buf, self.bucket, filename,
            ExtraArgs={"ContentType": "image/png", "ACL": "public-read"}
        )
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{filename}"

    async def delete(self, key: str) -> bool:
        self.s3.delete_object(Bucket=self.bucket, Key=f"{key}.png")
        return True

    async def get_url(self, key: str) -> str:
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}.png"


# ================================================================
# FACTORY
# ================================================================
def get_storage() -> StorageBackend:
    backend = settings.STORAGE_BACKEND.lower()
    if backend == "supabase":
        return SupabaseStorage()
    elif backend == "s3":
        return S3Storage()
    else:
        return LocalStorage()

# Singleton instance
_storage_instance: StorageBackend = None

def storage() -> StorageBackend:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = get_storage()
    return _storage_instance
