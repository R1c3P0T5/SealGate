from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe


@dataclass(frozen=True)
class WebSocketTicket:
    ticket: str
    purpose: str
    door_id: str
    expires_at: datetime


class WebSocketTicketStore:
    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._tickets: dict[str, WebSocketTicket] = {}

    def issue(self, *, purpose: str, door_id: str, ttl_seconds: int) -> WebSocketTicket:
        self._purge_expired()
        ticket = WebSocketTicket(
            ticket=token_urlsafe(32),
            purpose=purpose,
            door_id=door_id,
            expires_at=self._now() + timedelta(seconds=ttl_seconds),
        )
        self._tickets[ticket.ticket] = ticket
        return ticket

    def consume(self, ticket: str, *, purpose: str, door_id: str) -> bool:
        self._purge_expired()
        stored = self._tickets.get(ticket)
        if stored is None:
            return False
        if stored.expires_at <= self._now():
            del self._tickets[ticket]
            return False
        if stored.purpose != purpose or stored.door_id != door_id:
            return False
        del self._tickets[ticket]
        return True

    def _purge_expired(self) -> None:
        now = self._now()
        stale = [k for k, v in self._tickets.items() if v.expires_at <= now]
        for k in stale:
            del self._tickets[k]
