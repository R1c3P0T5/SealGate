import pytest
from starlette.websockets import WebSocketDisconnect


class _FakeWS:
    def __init__(self, fail: bool = False) -> None:
        self.bytes_sent: list[bytes] = []
        self.json_sent: list[dict] = []
        self._fail = fail

    async def send_bytes(self, data: bytes) -> None:
        if self._fail:
            raise WebSocketDisconnect()
        self.bytes_sent.append(data)

    async def send_json(self, data: dict) -> None:
        if self._fail:
            raise WebSocketDisconnect()
        self.json_sent.append(data)


@pytest.mark.asyncio
async def test_first_viewer_signals_start_to_producer() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    producer = _FakeWS()
    viewer = _FakeWS()

    await broker.connect_producer("door-1", producer)
    await broker.connect_viewer("door-1", viewer)

    assert producer.json_sent == [{"type": "start"}]


@pytest.mark.asyncio
async def test_second_viewer_does_not_signal_start() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    producer = _FakeWS()
    v1, v2 = _FakeWS(), _FakeWS()

    await broker.connect_producer("door-1", producer)
    await broker.connect_viewer("door-1", v1)
    await broker.connect_viewer("door-1", v2)

    assert producer.json_sent == [{"type": "start"}]


@pytest.mark.asyncio
async def test_last_viewer_disconnect_signals_stop() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    producer = _FakeWS()
    viewer = _FakeWS()

    await broker.connect_producer("door-1", producer)
    await broker.connect_viewer("door-1", viewer)
    await broker.disconnect_viewer("door-1", viewer)

    assert producer.json_sent == [{"type": "start"}, {"type": "stop"}]


@pytest.mark.asyncio
async def test_non_last_viewer_disconnect_does_not_signal_stop() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    producer = _FakeWS()
    v1, v2 = _FakeWS(), _FakeWS()

    await broker.connect_producer("door-1", producer)
    await broker.connect_viewer("door-1", v1)
    await broker.connect_viewer("door-1", v2)
    await broker.disconnect_viewer("door-1", v1)

    assert producer.json_sent == [{"type": "start"}]


@pytest.mark.asyncio
async def test_relay_frame_broadcasts_to_all_viewers() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    v1, v2 = _FakeWS(), _FakeWS()

    await broker.connect_viewer("door-1", v1)
    await broker.connect_viewer("door-1", v2)
    await broker.relay_frame("door-1", b"JPEG_DATA")

    assert v1.bytes_sent == [b"JPEG_DATA"]
    assert v2.bytes_sent == [b"JPEG_DATA"]


@pytest.mark.asyncio
async def test_relay_metadata_broadcasts_to_all_viewers() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    v1, v2 = _FakeWS(), _FakeWS()
    payload = {
        "type": "face_boxes",
        "faces": [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4, "score": 0.95}],
    }

    await broker.connect_viewer("door-1", v1)
    await broker.connect_viewer("door-1", v2)
    await broker.relay_metadata("door-1", payload)

    assert v1.json_sent == [payload]
    assert v2.json_sent == [payload]


@pytest.mark.asyncio
async def test_stale_producer_cannot_relay_frames_after_replacement() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    old_producer = _FakeWS()
    new_producer = _FakeWS()
    viewer = _FakeWS()

    await broker.connect_viewer("door-1", viewer)
    await broker.connect_producer("door-1", old_producer)
    await broker.connect_producer("door-1", new_producer)

    await broker.relay_frame("door-1", b"OLD_FRAME", old_producer)
    await broker.relay_frame("door-1", b"NEW_FRAME", new_producer)

    assert viewer.bytes_sent == [b"NEW_FRAME"]


@pytest.mark.asyncio
async def test_stale_producer_cannot_relay_metadata_after_replacement() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    old_producer = _FakeWS()
    new_producer = _FakeWS()
    viewer = _FakeWS()
    payload = {"type": "face_boxes", "faces": []}

    await broker.connect_viewer("door-1", viewer)
    await broker.connect_producer("door-1", old_producer)
    await broker.connect_producer("door-1", new_producer)

    await broker.relay_metadata("door-1", payload, old_producer)
    await broker.relay_metadata("door-1", payload, new_producer)

    assert viewer.json_sent == [payload]


@pytest.mark.asyncio
async def test_relay_frame_drops_stale_viewer_and_signals_stop() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    producer = _FakeWS()
    stale = _FakeWS(fail=True)

    await broker.connect_producer("door-1", producer)
    await broker.connect_viewer("door-1", stale)
    producer.json_sent.clear()

    await broker.relay_frame("door-1", b"JPEG_DATA")

    assert stale.bytes_sent == []
    assert producer.json_sent == [{"type": "stop"}]


@pytest.mark.asyncio
async def test_disconnect_viewer_is_noop_when_viewer_already_removed() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    producer = _FakeWS()
    viewer = _FakeWS()

    await broker.connect_producer("door-1", producer)
    await broker.connect_viewer("door-1", viewer)
    await broker.disconnect_viewer("door-1", viewer)
    await broker.disconnect_viewer("door-1", viewer)

    assert producer.json_sent == [{"type": "start"}, {"type": "stop"}]


@pytest.mark.asyncio
async def test_producer_connect_with_existing_viewers_signals_start() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    viewer = _FakeWS()
    producer = _FakeWS()

    await broker.connect_viewer("door-1", viewer)
    await broker.connect_producer("door-1", producer)

    assert producer.json_sent == [{"type": "start"}]


@pytest.mark.asyncio
async def test_frames_isolated_per_door() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    v_a, v_b = _FakeWS(), _FakeWS()

    await broker.connect_viewer("door-a", v_a)
    await broker.connect_viewer("door-b", v_b)
    await broker.relay_frame("door-a", b"FRAME_A")

    assert v_a.bytes_sent == [b"FRAME_A"]
    assert v_b.bytes_sent == []


@pytest.mark.asyncio
async def test_old_producer_disconnect_does_not_remove_replacement() -> None:
    from src.camera.broker import CameraFrameBroker

    broker = CameraFrameBroker()
    old_producer = _FakeWS()
    new_producer = _FakeWS()
    viewer = _FakeWS()

    await broker.connect_viewer("door-1", viewer)
    await broker.connect_producer("door-1", old_producer)
    await broker.connect_producer("door-1", new_producer)
    broker.disconnect_producer("door-1", old_producer)

    await broker.disconnect_viewer("door-1", viewer)

    assert new_producer.json_sent == [{"type": "start"}, {"type": "stop"}]
