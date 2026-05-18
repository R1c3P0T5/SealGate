from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError


def test_user_register_request_validates_required_fields() -> None:
    from src.auth.schemas import UserRegisterRequest

    request = UserRegisterRequest(
        username="john_doe",
        password="MySecurePass123",
        full_name="John Doe",
        email="john@example.com",
    )

    assert request.username == "john_doe"
    assert request.email == "john@example.com"


def test_user_register_request_rejects_short_password() -> None:
    from src.auth.schemas import UserRegisterRequest

    with pytest.raises(ValidationError):
        UserRegisterRequest(
            username="john_doe",
            password="short",
            full_name="John Doe",
        )


def test_login_response_defaults_token_type_to_bearer() -> None:
    from src.auth.schemas import LoginResponse, UserResponse

    user = UserResponse(
        id=uuid4(),
        username="john_doe",
        full_name="John Doe",
        role_name="user",
        is_active=True,
        created_at=datetime.now(),
    )

    response = LoginResponse(access_token="token", user=user)

    assert response.token_type == "bearer"
    assert response.user.username == "john_doe"
