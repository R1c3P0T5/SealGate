import asyncio

import numpy as np
import pytest

import worker


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeHttpClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return _FakeResponse(self.payload)


def _settings() -> worker.WorkerSettings:
    return worker.WorkerSettings(
        backend_url="http://backend.test",
        backend_ws_url="ws://backend.test",
        door_id="door-1",
        device_token="device-token",
    )


def test_import_is_safe_without_required_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BACKEND_URL", raising=False)
    monkeypatch.delenv("BACKEND_WS_URL", raising=False)
    monkeypatch.delenv("DOOR_ID", raising=False)
    monkeypatch.delenv("DEVICE_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="BACKEND_URL is required"):
        worker.load_settings()


def test_load_settings_reads_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_URL", "http://backend.test")
    monkeypatch.setenv("BACKEND_WS_URL", "ws://backend.test")
    monkeypatch.setenv("DOOR_ID", "door-1")
    monkeypatch.setenv("DEVICE_TOKEN", "device-token")

    settings = worker.load_settings()

    assert settings.stream_fps == 20
    assert settings.detect_fps == 10
    assert settings.recognize_min_interval_seconds == 0.5
    assert settings.recognize_success_cooldown_seconds == 3.0
    assert settings.recognize_failure_cooldown_seconds == 0.5
    assert settings.max_recognize_in_flight == 1
    assert settings.jpeg_quality == 70


def test_primary_face_box_selects_largest_face_and_normalizes_coordinates() -> None:
    faces = np.array(
        [
            [10.0, 20.0, 30.0, 40.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.75],
            [50.0, 60.0, 100.0, 80.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.95],
        ],
        dtype=np.float32,
    )

    box = worker._primary_face_box_from_faces(faces, frame_width=200, frame_height=100)

    assert box == {
        "x": 0.25,
        "y": 0.6,
        "width": 0.5,
        "height": 0.4,
        "score": 0.95,
    }


def test_primary_face_box_clamps_to_frame_bounds() -> None:
    faces = np.array(
        [[-10.0, -20.0, 250.0, 160.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.8]],
        dtype=np.float32,
    )

    box = worker._primary_face_box_from_faces(faces, frame_width=200, frame_height=100)

    assert box == {
        "x": 0.0,
        "y": 0.0,
        "width": 1.0,
        "height": 1.0,
        "score": 0.8,
    }


def test_primary_face_box_returns_none_without_faces() -> None:
    assert worker._primary_face_box_from_faces(None, frame_width=200, frame_height=100) is None
    assert (
        worker._primary_face_box_from_faces(
            np.empty((0, 15), dtype=np.float32), frame_width=200, frame_height=100
        )
        is None
    )


def test_face_boxes_payload_uses_empty_faces_without_primary_box() -> None:
    assert worker._face_boxes_payload(None) == {"type": "face_boxes", "faces": []}


def test_drain_queue_removes_stale_metadata() -> None:
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    queue.put_nowait({"type": "face_boxes", "faces": [{"x": 0.1}]})
    queue.put_nowait({"type": "face_boxes", "faces": []})

    worker._drain_queue(queue)

    assert queue.empty()


@pytest.mark.asyncio
async def test_send_metadata_logs_and_returns_on_send_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _FailingWebSocket:
        async def send(self, _payload: str) -> None:
            raise RuntimeError("send failed")

    worker._streaming = True
    worker._metadata_queue = asyncio.Queue()
    worker._metadata_queue.put_nowait({"type": "face_boxes", "faces": []})

    await worker._send_metadata(_FailingWebSocket())  # type: ignore[arg-type]

    assert "Metadata send failed" in caplog.text


@pytest.mark.asyncio
async def test_post_recognize_sends_expected_request_and_success_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeHttpClient({"matched": True, "username": "alice", "confidence": 0.9})
    worker._settings = _settings()
    worker._http_client = fake_client  # type: ignore[assignment]
    worker._recognize_semaphore = asyncio.Semaphore(1)
    worker._next_recognize_at = 0.0
    monkeypatch.setattr(worker.time, "monotonic", lambda: 100.0)

    await worker._post_recognize(b"JPEG")

    assert fake_client.calls == [
        {
            "url": "http://backend.test/api/doors/door-1/recognize",
            "files": {"image": ("frame.jpg", b"JPEG", "image/jpeg")},
            "headers": {"X-Device-Token": "device-token"},
            "timeout": 8,
        }
    ]
    assert worker._next_recognize_at == 103.0


@pytest.mark.asyncio
async def test_post_recognize_uses_failure_cooldown_on_unmatched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeHttpClient({"matched": False, "confidence": 0.1})
    worker._settings = _settings()
    worker._http_client = fake_client  # type: ignore[assignment]
    worker._recognize_semaphore = asyncio.Semaphore(1)
    worker._next_recognize_at = 0.0
    monkeypatch.setattr(worker.time, "monotonic", lambda: 100.0)

    await worker._post_recognize(b"JPEG")

    assert worker._next_recognize_at == 100.5
