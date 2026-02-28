"""
database.py — Database Models & Init
SQLAlchemy async dengan SQLite (dev) / PostgreSQL (prod)
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer, JSON
from datetime import datetime, timezone
from config import settings
import uuid

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


class ImageRecord(Base):
    """Rekam setiap gambar yang digenerate."""
    __tablename__ = "image_records"

    id: Mapped[str]         = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str]    = mapped_column(String(255), index=True)
    user_email: Mapped[str] = mapped_column(String(255), index=True)
    prompt: Mapped[str]     = mapped_column(Text)
    image_url: Mapped[str]  = mapped_column(Text)
    image_key: Mapped[str]  = mapped_column(String(255))
    resolution: Mapped[str] = mapped_column(String(20), default="512x512")
    style: Mapped[str]      = mapped_column(String(100), default="default")
    meta_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class MemoryStore(Base):
    """Key-value memory store untuk AI agent."""
    __tablename__ = "memory_store"

    id: Mapped[str]         = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[str]        = mapped_column(String(500), index=True)
    user_id: Mapped[str]    = mapped_column(String(255), index=True)
    value: Mapped[dict]     = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
