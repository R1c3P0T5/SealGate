from typing import Protocol

from starlette.websockets import WebSocketDisconnect

from src.access_logs.schemas import AccessLogResponse


class _JsonWebSocket(Protocol):
    async def send_json(self, data: dict[str, object]) -> None: ...


class AccessEventBroker:
    """In-process fan-out for live access events."""

    def __init__(self) -> None:
        self._clients: set[_JsonWebSocket] = set()

    def connect(self, websocket: _JsonWebSocket) -> None:
        self._clients.add(websocket)

    def disconnect(self, websocket: _JsonWebSocket) -> None:
        self._clients.discard(websocket)

    async def publish(self, event: AccessLogResponse) -> None:
        payload = event.model_dump(mode="json")
        stale_clients: list[_JsonWebSocket] = []
        for websocket in list(self._clients):
            try:
                await websocket.send_json(payload)
            except (RuntimeError, WebSocketDisconnect):
                stale_clients.append(websocket)

        for websocket in stale_clients:
            self.disconnect(websocket)
