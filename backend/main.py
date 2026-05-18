from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import src.core.database as db
import src.faces.engine as face_engine
from src.auth.router import router as auth_router
from src.auth.service import ensure_default_admin
from src.core.config import get_settings
from src.doors.router import router as doors_router
from src.faces.router import router as faces_router
from src.permissions.router import router as permissions_router
from src.roles.router import router as roles_router
from src.users.router import router as users_router
import src.roles.models as _roles_models  # noqa: F401
import src.permissions.models as _permissions_models  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    if settings.JETSON_CAMERA_TOKEN is None:
        logger.warning(
            "JETSON_CAMERA_TOKEN is not configured; recognition WebSocket "
            "connections will be rejected."
        )
    await db.init_db()
    await db.create_db_and_tables()
    await db.seed_roles_and_permissions()
    await face_engine.load_engine()
    async with db.session_context() as session:
        await ensure_default_admin(settings, session)
    try:
        yield
    finally:
        await db.close_db()
        await face_engine.unload_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Jetson Facelock API",
        description="Backend API for Jetson Facelock user authentication and access control.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(faces_router)
    app.include_router(doors_router)
    app.include_router(roles_router)
    app.include_router(permissions_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
