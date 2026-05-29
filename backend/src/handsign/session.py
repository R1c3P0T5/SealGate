import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

_SESSION_WINDOW_SECONDS = 60.0


@dataclass
class DoorSession:
    face_ok: bool = False
    handsign_ok: bool = False
    expires_at: float = field(
        default_factory=lambda: time.monotonic() + _SESSION_WINDOW_SECONDS
    )

    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at

    def reset(self) -> None:
        self.face_ok = False
        self.handsign_ok = False
        self.expires_at = time.monotonic() + _SESSION_WINDOW_SECONDS

    def is_complete(self) -> bool:
        return self.face_ok and self.handsign_ok


class DoorSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[UUID, DoorSession] = {}

    def get_or_create(self, door_id: UUID) -> DoorSession:
        session = self._sessions.get(door_id)
        if session is None or session.is_expired():
            session = DoorSession()
            self._sessions[door_id] = session
        return session

    def clear(self, door_id: UUID) -> None:
        self._sessions.pop(door_id, None)


async def try_unlock_both(
    door_id: UUID,
    auth_factor: Literal["face_ok", "handsign_ok"],
    store: "DoorSessionStore",
    publish_fn: Callable[[], Awaitable[None]],
    logger: logging.Logger,
) -> bool:
    """Record one auth factor; if both are satisfied, call publish_fn and clear.

    publish_fn is the MQTT unlock coroutine. It is called only when both
    face_ok and handsign_ok are set on the session for this door.

    The session is cleared on both success and failure so a publish error
    does not leave the door permanently in an unlockable state.

    Returns True if the door was unlocked this call, False otherwise.
    """
    door_session = store.get_or_create(door_id)
    setattr(door_session, auth_factor, True)
    if door_session.is_complete():
        try:
            await publish_fn()
            store.clear(door_id)
            return True
        except Exception as exc:
            logger.warning("MQTT publish failed (both mode) door %s: %s", door_id, exc)
            store.clear(door_id)
    return False
