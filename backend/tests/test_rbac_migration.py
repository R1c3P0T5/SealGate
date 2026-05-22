import importlib.util
from pathlib import Path

import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "c3b2fc80fd62_normalize_rbac_uuid_storage.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("rbac_uuid_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_sqlite_rbac_uuid_storage_repairs_role_relationships() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()

    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE role (id TEXT PRIMARY KEY, name TEXT)"))
        conn.execute(
            sa.text('CREATE TABLE "user" (username TEXT, role_id TEXT NOT NULL)')
        )
        conn.execute(
            sa.text(
                "CREATE TABLE rolepermission "
                "(role_id TEXT NOT NULL, permission_id TEXT NOT NULL)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO role (id, name) VALUES "
                "('ee413c5a-7ca5-4650-9320-be20829b1a9c', 'admin')"
            )
        )
        conn.execute(
            sa.text(
                'INSERT INTO "user" (username, role_id) VALUES '
                "('admin', 'ee413c5a7ca546509320be20829b1a9c')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO rolepermission (role_id, permission_id) VALUES "
                "('ee413c5a7ca546509320be20829b1a9c', "
                "'ba405af1bd6040728d8fc22d5d6399e0')"
            )
        )

        migration.normalize_sqlite_rbac_uuid_storage(conn)

        role_id = conn.execute(sa.text("SELECT id FROM role")).scalar_one()
        joined_user = conn.execute(
            sa.text(
                'SELECT "user".username '
                'FROM "user" JOIN role ON role.id = "user".role_id'
            )
        ).scalar_one()
        joined_permission = conn.execute(
            sa.text(
                "SELECT rolepermission.permission_id "
                "FROM rolepermission JOIN role ON role.id = rolepermission.role_id"
            )
        ).scalar_one()

    assert role_id == "ee413c5a7ca546509320be20829b1a9c"
    assert joined_user == "admin"
    assert joined_permission == "ba405af1bd6040728d8fc22d5d6399e0"
