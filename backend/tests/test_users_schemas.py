from datetime import datetime
from uuid import uuid4


def test_user_update_request_allows_partial_profile_update() -> None:
    from src.users.schemas import UserUpdateRequest

    request = UserUpdateRequest(full_name="Jane Doe")

    assert request.full_name == "Jane Doe"
    assert request.email is None


def test_user_list_response_wraps_users_and_pagination() -> None:
    from src.users.schemas import UserListResponse, UserResponseFull

    user = UserResponseFull(
        id=uuid4(),
        username="admin",
        email="admin@example.com",
        full_name="Admin User",
        role_name="admin",
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    response = UserListResponse(total=1, skip=0, limit=10, users=[user])

    assert response.total == 1
    assert response.users[0].role_name == "admin"
