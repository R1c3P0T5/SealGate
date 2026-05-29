from datetime import datetime, timezone
from uuid import uuid4

import pytest


def test_door_response_serializes_correctly() -> None:
    from src.doors.schemas import DoorResponse

    door_id = uuid4()
    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)

    resp = DoorResponse(
        id=door_id,
        name="Main Entrance",
        mqtt_id="main-entrance",
        location="Building A",
        is_active=True,
        auth_mode="face",
        created_at=now,
    )

    assert resp.id == door_id
    assert resp.name == "Main Entrance"
    assert resp.mqtt_id == "main-entrance"
    assert resp.location == "Building A"
    assert resp.is_active is True
    assert resp.auth_mode == "face"


def test_door_list_response_has_pagination_fields() -> None:
    from src.doors.schemas import DoorListResponse, DoorResponse

    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    doors = [
        DoorResponse(
            id=uuid4(),
            name=f"Door {i}",
            mqtt_id=f"door-{i}",
            location=None,
            is_active=True,
            auth_mode="face",
            created_at=now,
        )
        for i in range(3)
    ]

    resp = DoorListResponse(total=3, skip=0, limit=10, doors=doors)

    assert resp.total == 3
    assert len(resp.doors) == 3


def test_door_update_request_all_fields_optional() -> None:
    from src.doors.schemas import DoorUpdateRequest

    req = DoorUpdateRequest()

    assert req.name is None
    assert req.mqtt_id is None
    assert req.location is None
    assert req.is_active is None


def test_door_create_request_rejects_invalid_mqtt_id() -> None:
    from pydantic import ValidationError

    from src.doors.schemas import DoorCreateRequest

    with pytest.raises(ValidationError):
        DoorCreateRequest(name="Test", mqtt_id="Invalid ID!")


def test_door_create_request_default_auth_mode_is_face() -> None:
    from src.doors.schemas import DoorCreateRequest

    req = DoorCreateRequest(name="Test", mqtt_id="test-door")

    assert req.auth_mode == "face"


def test_door_create_request_accepts_all_auth_modes() -> None:
    from src.doors.schemas import DoorCreateRequest

    for mode in ("face", "handsign", "both"):
        req = DoorCreateRequest(name="Test", mqtt_id="test-door", auth_mode=mode)
        assert req.auth_mode == mode


def test_door_create_request_rejects_invalid_auth_mode() -> None:
    from pydantic import ValidationError

    from src.doors.schemas import DoorCreateRequest

    with pytest.raises(ValidationError):
        DoorCreateRequest(name="Test", mqtt_id="test-door", auth_mode="fingerprint")  # type: ignore[arg-type]


def test_door_update_request_auth_mode_defaults_to_none() -> None:
    from src.doors.schemas import DoorUpdateRequest

    req = DoorUpdateRequest()

    assert req.auth_mode is None


def test_door_update_request_accepts_valid_auth_modes() -> None:
    from src.doors.schemas import DoorUpdateRequest

    for mode in ("face", "handsign", "both"):
        req = DoorUpdateRequest(auth_mode=mode)
        assert req.auth_mode == mode


def test_door_update_request_rejects_invalid_auth_mode() -> None:
    from pydantic import ValidationError

    from src.doors.schemas import DoorUpdateRequest

    with pytest.raises(ValidationError):
        DoorUpdateRequest(auth_mode="badge")  # type: ignore[arg-type]
