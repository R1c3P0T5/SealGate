import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
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


async def maybe_unlock_both(
    door_id: UUID,
    flag: str,
    store: "DoorSessionStore",
    publish_fn: Callable[[], Awaitable[None]],
    logger: logging.Logger,
) -> bool:
    """Set flag on the door session; if both flags are set, call publish_fn and clear.

    Returns True if the door was unlocked, False otherwise.
    """
    session = store.get_or_create(door_id)
    setattr(session, flag, True)
    if session.is_complete():
        try:
            await publish_fn()
            store.clear(door_id)
            return True
        except Exception as exc:
            logger.warning("MQTT publish failed (both mode) door %s: %s", door_id, exc)
    return False
