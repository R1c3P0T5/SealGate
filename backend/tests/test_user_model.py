from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.users.models import User


def test_user_model_defaults_and_required_fields() -> None:
    role_id = uuid4()
    user = User(
        id=uuid4(),
        username="testuser",
        password_hash="hash",
        full_name="Test User",
        role_id=role_id,
    )

    assert isinstance(user.id, UUID)
    assert user.username == "testuser"
    assert user.email is None
    assert user.role_id == role_id
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)


def test_user_table_has_expected_columns_and_constraints() -> None:
    table: Any = getattr(User, "__table__")

    assert table.name == "user"
    assert set(table.columns.keys()) == {
        "id",
        "username",
        "email",
        "password_hash",
        "full_name",
        "role_id",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert table.columns["id"].primary_key is True
    assert table.columns["username"].unique is True
    assert table.columns["username"].index is True
    assert table.columns["email"].unique is True
    assert table.columns["email"].index is True
    assert table.columns["password_hash"].nullable is False
    assert table.columns["full_name"].nullable is False
    assert table.columns["role_id"].foreign_keys
    assert table.columns["role_id"].index is True
    assert table.columns["role_id"].nullable is False
