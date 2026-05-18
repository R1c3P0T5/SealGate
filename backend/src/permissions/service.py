from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.permissions.models import Permission, RolePermission, UserPermissionOverride
from src.roles.models import Role
from src.users.models import User


async def list_all_permissions(session: AsyncSession) -> list[Permission]:
    return list((await session.exec(select(Permission))).all())


async def get_user_permissions_detail(user: User, session: AsyncSession) -> dict:
    # WHERE + subquery to avoid join onclause pyright bool-inference issue
    role_stmt = select(Permission.name).where(
        Permission.id.in_(  # type: ignore[attr-defined]
            select(RolePermission.permission_id).where(
                RolePermission.role_id == user.role_id  # type: ignore[attr-defined]
            )
        )
    )
    role_perms = list((await session.exec(role_stmt)).all())

    override_stmt = select(Permission.name, UserPermissionOverride.granted).where(
        UserPermissionOverride.user_id == user.id,
        UserPermissionOverride.permission_id == Permission.id,  # type: ignore[arg-type]
    )
    overrides_raw = list((await session.exec(override_stmt)).all())
    overrides = [
        {"permission": name, "granted": granted} for name, granted in overrides_raw
    ]

    effective: set[str] = set(role_perms)
    for name, granted in overrides_raw:
        if granted:
            effective.add(name)
        else:
            effective.discard(name)

    return {
        "effective": sorted(effective),
        "role_permissions": sorted(role_perms),
        "overrides": overrides,
    }


async def set_user_permission_overrides(
    user: User,
    overrides: list[dict],
    session: AsyncSession,
) -> None:
    existing = (
        await session.exec(
            select(UserPermissionOverride).where(
                UserPermissionOverride.user_id == user.id
            )
        )
    ).all()
    for o in existing:
        await session.delete(o)
    await session.flush()

    if overrides:
        perm_names = [item["permission"] for item in overrides]
        perm_rows = (
            await session.exec(
                select(Permission).where(Permission.name.in_(perm_names))  # type: ignore[attr-defined]
            )
        ).all()
        perm_map = {p.name: p for p in perm_rows}

        unknown = set(perm_names) - perm_map.keys()
        if unknown:
            from src.core.exceptions import BaseAPIError

            raise BaseAPIError(
                detail=f"Unknown permission(s): {', '.join(sorted(unknown))}",
                status_code=400,
            )

        for item in overrides:
            session.add(
                UserPermissionOverride(
                    user_id=user.id,
                    permission_id=perm_map[item["permission"]].id,
                    granted=item["granted"],
                )
            )

    await session.commit()


async def set_user_role(
    user: User, role_id: UUID, session: AsyncSession
) -> tuple[User, str]:
    role = await session.get(Role, role_id)
    if role is None:
        from src.core.exceptions import BaseAPIError

        raise BaseAPIError(detail="Role not found", status_code=404)
    user.role_id = role_id  # type: ignore[attr-defined]
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, role.name
