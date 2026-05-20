import asyncio

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
