import ssl
import time
from typing import Protocol

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from starlette.concurrency import run_in_threadpool

from src.core.config import get_settings
from src.core.exceptions import DoorMqttNotConfiguredError
from src.doors.models import Door

_PUBLISH_ERR_MSG = "Failed to publish door unlock command"
_UNLOCK_PULSE_SECONDS = 0.5


class DoorUnlockPublishError(RuntimeError):
    pass


class _PublishResult(Protocol):
    rc: int


class _Disconnectable(Protocol):
    def disconnect(self) -> int: ...


class _MqttClient(Protocol):
    def tls_set(self, tls_version: int | None = None) -> None: ...

    def username_pw_set(self, username: str, password: str | None = None) -> None: ...

    def connect(self, host: str, port: int) -> int: ...

    def publish(self, topic: str, payload: str) -> _PublishResult: ...

    def disconnect(self) -> int: ...


def _disconnect_quietly(client: _Disconnectable) -> None:
    try:
        client.disconnect()
    except Exception:
        pass


def _check_publish(rc: int) -> None:
    if rc != mqtt.MQTT_ERR_SUCCESS:
        raise DoorUnlockPublishError(_PUBLISH_ERR_MSG)


def _publish_door_unlock_sync(
    door: Door,
    *,
    client: _MqttClient | None = None,
) -> None:
    if not door.mqtt_id:
        raise DoorMqttNotConfiguredError()

    settings = get_settings()
    mqtt_client = client or mqtt.Client(CallbackAPIVersion.VERSION2)
    if settings.MQTT_TLS:
        mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    if settings.MQTT_USERNAME is not None:
        mqtt_client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

    topic = settings.MQTT_UNLOCK_TOPIC_TEMPLATE.format(mqtt_id=door.mqtt_id)
    try:
        connect_rc = mqtt_client.connect(settings.MQTT_HOST, settings.MQTT_PORT)
    except Exception as exc:
        raise DoorUnlockPublishError(_PUBLISH_ERR_MSG) from exc

    if connect_rc != mqtt.MQTT_ERR_SUCCESS:
        _disconnect_quietly(mqtt_client)
        raise DoorUnlockPublishError(_PUBLISH_ERR_MSG)

    try:
        _check_publish(mqtt_client.publish(topic, settings.MQTT_UNLOCK_PAYLOAD).rc)
        time.sleep(_UNLOCK_PULSE_SECONDS)
        _check_publish(mqtt_client.publish(topic, settings.MQTT_LOCK_PAYLOAD).rc)
    except DoorUnlockPublishError:
        raise  # prevent re-wrapping by the broad except below
    except Exception as exc:
        raise DoorUnlockPublishError(_PUBLISH_ERR_MSG) from exc
    finally:
        _disconnect_quietly(mqtt_client)


async def publish_door_unlock(door: Door) -> None:
    await run_in_threadpool(_publish_door_unlock_sync, door)
