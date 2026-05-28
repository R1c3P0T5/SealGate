from datetime import datetime
from uuid import uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from src.access_logs.schemas import AccessLogResponse


class _FakeWebSocket:
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: dict[str, object]) -> None:
        if self._exc is not None:
            raise self._exc
        self.sent.append(data)


@pytest.mark.asyncio
async def test_access_event_broker_connect_disconnect_and_publish() -> None:
    from src.access_events.broker import AccessEventBroker

    broker = AccessEventBroker()
    websocket = _FakeWebSocket()
    event = AccessLogResponse(
        id=uuid4(),
        timestamp=datetime(2026, 5, 20, 9, 30, 0),
        door_id=uuid4(),
        user_id=uuid4(),
        username="alice",
        confidence=0.93,
        door_opened=True,
    )

    broker.connect(websocket)
    await broker.publish(event)

    assert websocket.sent == [
        {
            "id": str(event.id),
            "timestamp": "2026-05-20T09:30:00Z",
            "door_id": str(event.door_id),
            "user_id": str(event.user_id),
            "username": "alice",
            "confidence": 0.93,
            "door_opened": True,
        }
    ]

    broker.disconnect(websocket)
    await broker.publish(event)

    assert len(websocket.sent) == 1


@pytest.mark.asyncio
async def test_access_event_broker_drops_disconnected_clients() -> None:
    from src.access_events.broker import AccessEventBroker

    broker = AccessEventBroker()
    disconnected = _FakeWebSocket(WebSocketDisconnect())
    active = _FakeWebSocket()
    event = AccessLogResponse(
        id=uuid4(),
        timestamp=datetime(2026, 5, 20, 9, 30, 0),
        door_id=uuid4(),
        user_id=None,
        username=None,
        confidence=None,
        door_opened=False,
    )

    broker.connect(disconnected)
    broker.connect(active)
    await broker.publish(event)
    await broker.publish(event)

    assert disconnected.sent == []
    assert len(active.sent) == 2


def test_create_app_uses_isolated_access_event_brokers() -> None:
    from main import create_app

    first_app = create_app()
    second_app = create_app()

    assert (
        first_app.state.access_event_broker is not second_app.state.access_event_broker
    )
