from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import engine, Base
from app.api.v1.router import api_router


# -----------------------------------------------------------------------------
# Lifespan
# Replaces the deprecated @app.on_event("startup") / ("shutdown") pattern.
# Everything before `yield` runs on startup, everything after on shutdown.
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # -- Startup ---------------------------------------------------------------
    # In production, Alembic handles migrations — never use create_all() there.
    # This is only for local development convenience.
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield

    # -- Shutdown --------------------------------------------------------------
    await engine.dispose()


# -----------------------------------------------------------------------------
# App Factory
# -----------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # -- Middleware -------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Routers ---------------------------------------------------------------
    app.include_router(api_router)

    # -- Health Check ----------------------------------------------------------
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }

    return app


# -----------------------------------------------------------------------------
# App instance
# Uvicorn / Gunicorn targets: app.main:app
# -----------------------------------------------------------------------------
app = create_app()
