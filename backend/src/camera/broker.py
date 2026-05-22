from typing import Protocol

from starlette.websockets import WebSocketDisconnect


class _BytesWebSocket(Protocol):
    async def send_bytes(self, data: bytes) -> None: ...
    async def send_json(self, data: dict[str, object]) -> None: ...


class CameraFrameBroker:
    """各門的相機預覽影格 fan-out broker。

    根據 viewer 數量訊號通知 Jetson producer 開始/停止串流。
    """

    def __init__(self) -> None:
        self._viewers: dict[str, set[_BytesWebSocket]] = {}
        self._producers: dict[str, _BytesWebSocket] = {}

    async def connect_producer(self, door_id: str, ws: _BytesWebSocket) -> None:
        self._producers[door_id] = ws
        if self._viewers.get(door_id):
            await self._signal(door_id, "start")

    def disconnect_producer(self, door_id: str, ws: _BytesWebSocket) -> None:
        if self._producers.get(door_id) is ws:
            self._producers.pop(door_id, None)

    async def connect_viewer(self, door_id: str, ws: _BytesWebSocket) -> None:
        viewers = self._viewers.setdefault(door_id, set())
        was_empty = len(viewers) == 0
        viewers.add(ws)
        if was_empty:
            await self._signal(door_id, "start")

    async def disconnect_viewer(self, door_id: str, ws: _BytesWebSocket) -> None:
        viewers = self._viewers.get(door_id)
        if viewers is None or ws not in viewers:
            return
        viewers.discard(ws)
        if not viewers:
            self._viewers.pop(door_id, None)
            await self._signal(door_id, "stop")

    async def relay_frame(
        self, door_id: str, frame: bytes, producer: _BytesWebSocket | None = None
    ) -> None:
        if producer is not None and self._producers.get(door_id) is not producer:
            return
        viewers = self._viewers.get(door_id, set())
        stale: list[_BytesWebSocket] = []
        for ws in list(viewers):
            try:
                await ws.send_bytes(frame)
            except (RuntimeError, WebSocketDisconnect):
                stale.append(ws)
        for ws in stale:
            await self.disconnect_viewer(door_id, ws)

    async def relay_metadata(
        self,
        door_id: str,
        payload: dict[str, object],
        producer: _BytesWebSocket | None = None,
    ) -> None:
        if producer is not None and self._producers.get(door_id) is not producer:
            return
        viewers = self._viewers.get(door_id, set())
        stale: list[_BytesWebSocket] = []
        for ws in list(viewers):
            try:
                await ws.send_json(payload)
            except (RuntimeError, WebSocketDisconnect):
                stale.append(ws)
        for ws in stale:
            await self.disconnect_viewer(door_id, ws)

    async def _signal(self, door_id: str, cmd: str) -> None:
        producer = self._producers.get(door_id)
        if producer is None:
            return
        try:
            await producer.send_json({"type": cmd})
        except (RuntimeError, WebSocketDisconnect):
            self.disconnect_producer(door_id, producer)
