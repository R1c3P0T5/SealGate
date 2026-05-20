import pytest

from src.doors.models import Door


class _FakePublishResult:
    def __init__(self, rc: int) -> None:
        self.rc = rc


class _FakeMqttClient:
    def __init__(
        self,
        *,
        connect_rc: int = 0,
        publish_rc: int = 0,
        fail_connect: bool = False,
    ) -> None:
        self.connect_rc = connect_rc
        self.publish_rc = publish_rc
        self.fail_connect = fail_connect
        self.username = None
        self.password = None
        self.connected_to = None
        self.published = []
        self.disconnected = False

    def username_pw_set(self, username: str, password: str | None = None) -> None:
        self.username = username
        self.password = password

    def connect(self, host: str, port: int) -> int:
        if self.fail_connect:
            raise OSError("broker offline")
        self.connected_to = (host, port)
        return self.connect_rc

    def publish(self, topic: str, payload: str) -> _FakePublishResult:
        self.published.append((topic, payload))
        return _FakePublishResult(self.publish_rc)

    def disconnect(self) -> int:
        self.disconnected = True
        return 0


def test_publish_door_unlock_sync_publishes_expected_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.doors.mqtt import _publish_door_unlock_sync

    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("MQTT_HOST", "mqtt.local")
    monkeypatch.setenv("MQTT_PORT", "1884")
    monkeypatch.setenv("MQTT_USERNAME", "worker")
    monkeypatch.setenv("MQTT_PASSWORD", "secret")
    monkeypatch.setenv("MQTT_UNLOCK_TOPIC_TEMPLATE", "facelock/{mqtt_id}/cmd")
    monkeypatch.setenv("MQTT_UNLOCK_PAYLOAD", "open")
    client = _FakeMqttClient()
    door = Door(name="Front", mqtt_id="front-gate")

    _publish_door_unlock_sync(door, client=client)

    assert client.username == "worker"
    assert client.password == "secret"
    assert client.connected_to == ("mqtt.local", 1884)
    assert client.published == [("facelock/front-gate/cmd", "open")]
    assert client.disconnected is True


def test_publish_door_unlock_sync_raises_when_publish_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.doors.mqtt import DoorUnlockPublishError, _publish_door_unlock_sync

    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    client = _FakeMqttClient(publish_rc=1)
    door = Door(name="Front", mqtt_id="front-gate")

    with pytest.raises(DoorUnlockPublishError):
        _publish_door_unlock_sync(door, client=client)

    assert client.disconnected is True


def test_publish_door_unlock_sync_raises_when_connect_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.doors.mqtt import DoorUnlockPublishError, _publish_door_unlock_sync

    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    client = _FakeMqttClient(fail_connect=True)
    door = Door(name="Front", mqtt_id="front-gate")

    with pytest.raises(DoorUnlockPublishError):
        _publish_door_unlock_sync(door, client=client)

    assert client.disconnected is False


def test_publish_door_unlock_sync_raises_when_connect_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.doors.mqtt import DoorUnlockPublishError, _publish_door_unlock_sync

    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    client = _FakeMqttClient(connect_rc=1)
    door = Door(name="Front", mqtt_id="front-gate")

    with pytest.raises(DoorUnlockPublishError):
        _publish_door_unlock_sync(door, client=client)

    assert client.disconnected is True
