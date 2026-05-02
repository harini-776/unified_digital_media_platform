import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.limiter import limiter

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
    yield


# Gate /docs and /redoc behind DEBUG. In any non-debug environment they are
# disabled to avoid enumerating endpoints (including /auth/*) to anonymous
# clients. Use DEBUG=true in .env for local development.
_docs_url = "/docs" if settings.debug else None
_redoc_url = "/redoc" if settings.debug else None

app = FastAPI(
    title=settings.app_name,
    description="Unified Digital Media Trust Platform - Multimodal Deepfake Detection & Blockchain Provenance",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

# Rate limiter wiring
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "docs": _docs_url or "disabled (DEBUG=false)",
        "health": f"{settings.api_prefix}/health",
    }
