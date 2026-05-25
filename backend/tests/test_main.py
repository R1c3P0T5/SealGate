import pytest
from fastapi.routing import APIRoute
from sqlmodel import select

import src.core.database as db
from main import app, create_app, lifespan
from src.core.config import get_settings
from src.permissions.models import Permission, RolePermission
from src.roles.models import Role
from src.users.models import User


def test_create_app_returns_configured_fastapi_app() -> None:
    created_app = create_app()

    assert created_app.title == "SealGate API"
    assert created_app.version == "0.1.0"


def test_create_app_configures_cors_for_local_development() -> None:
    created_app = create_app()

    cors_middleware = [
        middleware
        for middleware in created_app.user_middleware
        if getattr(middleware.cls, "__name__", "") == "CORSMiddleware"
    ]

    assert len(cors_middleware) == 1
    assert getattr(cors_middleware[0], "kwargs")["allow_origins"] == [
        "http://localhost:3000",
        "http://localhost:8000",
    ]


def test_main_app_includes_auth_routes() -> None:
    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert ("/api/auth/register", ("POST",)) in routes
    assert ("/api/auth/login", ("POST",)) in routes
    assert ("/api/auth/token", ("POST",)) in routes
    assert ("/api/auth/me", ("GET",)) in routes


def test_main_app_includes_health_route() -> None:
    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert ("/health", ("GET",)) in routes


def test_openapi_docs_include_operation_and_schema_descriptions() -> None:
    openapi_schema = app.openapi()

    expected_summaries = {
        ("/api/auth/register", "post"): "Register user",
        ("/api/auth/login", "post"): "Login with JSON credentials",
        ("/api/auth/token", "post"): "Issue OAuth2 access token",
        ("/api/auth/me", "get"): "Get current user",
        ("/api/users", "get"): "List users",
        ("/api/users/{user_id}", "get"): "Get user profile",
        ("/api/users/{user_id}", "put"): "Update user profile",
        ("/api/users/{user_id}", "delete"): "Delete user",
        ("/api/access-logs", "get"): "List access logs",
        ("/api/devices", "get"): "List devices",
        ("/api/devices", "post"): "Create device",
        ("/api/doors/{door_id}/unlock", "post"): "Unlock door",
        ("/api/doors/{door_id}/recognize", "post"): "Recognize door access",
    }

    for (path, method), summary in expected_summaries.items():
        operation = openapi_schema["paths"][path][method]
        assert operation["summary"] == summary
        assert operation["description"]

    schemas = openapi_schema["components"]["schemas"]
    assert schemas["UserRegisterRequest"]["properties"]["username"]["description"]
    assert schemas["UserRegisterRequest"]["properties"]["password"]["description"]
    assert schemas["UserLoginRequest"]["properties"]["username"]["description"]
    assert schemas["UserListResponse"]["properties"]["users"]["description"]


@pytest.mark.asyncio
async def test_lifespan_seeds_configured_default_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEFAULT_ADMIN_USERNAME", "startup_admin")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "StartupPassword123")
    get_settings.cache_clear()

    async with lifespan(create_app()):
        assert db.async_session is not None
        async with db.async_session() as session:
            admin = (
                await session.exec(select(User).where(User.username == "startup_admin"))
            ).one()
            role = await session.get(Role, admin.role_id)
            assert role is not None
            assert role.name == "admin"


@pytest.mark.asyncio
async def test_lifespan_seeds_user_with_door_read_only() -> None:
    async with lifespan(create_app()):
        assert db.async_session is not None
        async with db.async_session() as session:
            door_read = (
                await session.exec(
                    select(Permission).where(Permission.name == "door:read")
                )
            ).one()
            log_read = (
                await session.exec(
                    select(Permission).where(Permission.name == "log:read")
                )
            ).one()
            admin_role = (
                await session.exec(select(Role).where(Role.name == "admin"))
            ).one()
            user_role = (
                await session.exec(select(Role).where(Role.name == "user"))
            ).one()

            admin_grant = (
                await session.exec(
                    select(RolePermission).where(
                        RolePermission.role_id == admin_role.id,
                        RolePermission.permission_id == door_read.id,
                    )
                )
            ).one_or_none()
            user_door_read_grant = (
                await session.exec(
                    select(RolePermission).where(
                        RolePermission.role_id == user_role.id,
                        RolePermission.permission_id == door_read.id,
                    )
                )
            ).one_or_none()
            user_log_read_grant = (
                await session.exec(
                    select(RolePermission).where(
                        RolePermission.role_id == user_role.id,
                        RolePermission.permission_id == log_read.id,
                    )
                )
            ).one_or_none()

            assert admin_grant is not None
            assert user_door_read_grant is not None
            assert user_log_read_grant is None


@pytest.mark.asyncio
async def test_lifespan_does_not_seed_unused_permissions() -> None:
    async with lifespan(create_app()):
        assert db.async_session is not None
        async with db.async_session() as session:
            for permission_name in (
                "door:open",
                "door:lock",
                "door:recognize",
                "log:delete",
            ):
                permission = (
                    await session.exec(
                        select(Permission).where(Permission.name == permission_name)
                    )
                ).one_or_none()
                assert permission is None


@pytest.mark.asyncio
async def test_lifespan_seeds_camera_preview_for_admin_only() -> None:
    async with lifespan(create_app()):
        assert db.async_session is not None
        async with db.async_session() as session:
            permission = (
                await session.exec(
                    select(Permission).where(Permission.name == "camera:preview")
                )
            ).one()
            admin_role = (
                await session.exec(select(Role).where(Role.name == "admin"))
            ).one()
            user_role = (
                await session.exec(select(Role).where(Role.name == "user"))
            ).one()

            admin_grant = (
                await session.exec(
                    select(RolePermission).where(
                        RolePermission.role_id == admin_role.id,
                        RolePermission.permission_id == permission.id,
                    )
                )
            ).one_or_none()
            user_grant = (
                await session.exec(
                    select(RolePermission).where(
                        RolePermission.role_id == user_role.id,
                        RolePermission.permission_id == permission.id,
                    )
                )
            ).one_or_none()

            assert admin_grant is not None
            assert user_grant is None


@pytest.mark.asyncio
async def test_lifespan_seeds_device_manage_for_admin_only() -> None:
    async with lifespan(create_app()):
        assert db.async_session is not None
        async with db.async_session() as session:
            permission = (
                await session.exec(
                    select(Permission).where(Permission.name == "device:manage")
                )
            ).one()
            admin_role = (
                await session.exec(select(Role).where(Role.name == "admin"))
            ).one()
            user_role = (
                await session.exec(select(Role).where(Role.name == "user"))
            ).one()

            admin_grant = (
                await session.exec(
                    select(RolePermission).where(
                        RolePermission.role_id == admin_role.id,
                        RolePermission.permission_id == permission.id,
                    )
                )
            ).one_or_none()
            user_grant = (
                await session.exec(
                    select(RolePermission).where(
                        RolePermission.role_id == user_role.id,
                        RolePermission.permission_id == permission.id,
                    )
                )
            ).one_or_none()

            assert admin_grant is not None
            assert user_grant is None
