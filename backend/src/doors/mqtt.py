import time
from typing import Protocol

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from starlette.concurrency import run_in_threadpool

from src.core.config import get_settings
from src.core.exceptions import DoorMqttNotConfiguredError
from src.doors.models import Door


class DoorUnlockPublishError(RuntimeError):
    pass


class _PublishResult(Protocol):
    rc: int


class _Disconnectable(Protocol):
    def disconnect(self) -> int: ...


class _MqttClient(Protocol):
    def username_pw_set(self, username: str, password: str | None = None) -> None: ...

    def connect(self, host: str, port: int) -> int: ...

    def publish(self, topic: str, payload: str) -> _PublishResult: ...

    def disconnect(self) -> int: ...


def _disconnect_quietly(client: _Disconnectable) -> None:
    try:
        client.disconnect()
    except Exception:
        pass


def _publish_door_unlock_sync(
    door: Door,
    *,
    client: _MqttClient | None = None,
) -> None:
    if not door.mqtt_id:
        raise DoorMqttNotConfiguredError()

    settings = get_settings()
    mqtt_client = client or mqtt.Client(CallbackAPIVersion.VERSION2)
    if settings.MQTT_USERNAME is not None:
        mqtt_client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

    topic = settings.MQTT_UNLOCK_TOPIC_TEMPLATE.format(mqtt_id=door.mqtt_id)
    try:
        connect_rc = mqtt_client.connect(settings.MQTT_HOST, settings.MQTT_PORT)
    except Exception as exc:
        raise DoorUnlockPublishError("Failed to publish door unlock command") from exc

    if connect_rc != mqtt.MQTT_ERR_SUCCESS:
        _disconnect_quietly(mqtt_client)
        raise DoorUnlockPublishError("Failed to publish door unlock command")

    try:
        result = mqtt_client.publish(topic, settings.MQTT_UNLOCK_PAYLOAD)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise DoorUnlockPublishError("Failed to publish door unlock command")
        time.sleep(0.5)
        result = mqtt_client.publish(topic, settings.MQTT_LOCK_PAYLOAD)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise DoorUnlockPublishError("Failed to publish door unlock command")
    except DoorUnlockPublishError:
        raise
    except Exception as exc:
        raise DoorUnlockPublishError("Failed to publish door unlock command") from exc
    finally:
        _disconnect_quietly(mqtt_client)


async def publish_door_unlock(door: Door) -> None:
    await run_in_threadpool(_publish_door_unlock_sync, door)
