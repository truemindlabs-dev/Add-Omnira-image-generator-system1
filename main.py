"""
==============================================================
OMNIRA SYNORA — AI IMAGE GENERATOR SERVER
Production-Ready FastAPI Backend
Integrasi: Base44 + Gmail Auth + Alpha PNG Generator
==============================================================
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

from routers import image_router, store_router, user_router
from config import settings
from database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("✅ Omnira Synora Server siap!")
    yield

app = FastAPI(
    title="Omnira Synora — AI Image Generator",
    description="AI Image Generator terintegrasi Base44 + Gmail Auth + True Alpha PNG",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(image_router.router, prefix="/api", tags=["Image Generator"])
app.include_router(store_router.router,  prefix="/api", tags=["Storage"])
app.include_router(user_router.router,   prefix="/api", tags=["User"])

@app.get("/")
async def root():
    return {
        "service": "Omnira Synora AI Image Generator",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "POST /api/generate-image":   "Generate gambar AI dari prompt",
            "POST /api/store":            "Simpan data ke memory",
            "GET  /api/retrieve/{key}":   "Ambil data dari memory",
            "GET  /api/user/history":     "Riwayat gambar user",
            "GET  /api/user/gallery":     "Galeri gambar user",
            "GET  /health":               "Health check",
        }
    }

@app.get("/health")
async def health():
    return {"status": "ok", "service": "omnira-synora"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
