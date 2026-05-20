from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import src.core.database as db
import src.faces.engine as face_engine
from src.access_events.broker import AccessEventBroker
from src.access_events.router import router as access_events_router
from src.access_logs.router import router as access_logs_router
from src.auth.router import router as auth_router
from src.auth.service import ensure_default_admin
from src.camera.router import router as camera_router
from src.core.config import get_settings
from src.doors.router import router as doors_router
from src.faces.router import router as faces_router
from src.permissions.router import router as permissions_router
from src.roles.router import router as roles_router
from src.users.router import router as users_router
from src.ws_tickets.router import router as ws_tickets_router
from src.ws_tickets.store import WebSocketTicketStore
import src.roles.models as _roles_models  # noqa: F401
import src.permissions.models as _permissions_models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
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
    app.state.access_event_broker = AccessEventBroker()
    app.state.ws_ticket_store = WebSocketTicketStore()

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
    app.include_router(access_logs_router)
    app.include_router(access_events_router)
    app.include_router(ws_tickets_router)
    app.include_router(camera_router)
    app.include_router(roles_router)
    app.include_router(permissions_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
