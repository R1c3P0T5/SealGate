from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.ws_tickets.store import WebSocketTicketStore


def test_ticket_store_consumes_valid_ticket_once() -> None:
    store = WebSocketTicketStore()
    door_id = str(uuid4())

    ticket = store.issue(
        purpose="camera-preview",
        door_id=door_id,
        ttl_seconds=30,
    )

    assert store.consume(ticket.ticket, purpose="camera-preview", door_id=door_id)
    assert not store.consume(ticket.ticket, purpose="camera-preview", door_id=door_id)


def test_ticket_store_rejects_expired_ticket() -> None:
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    store = WebSocketTicketStore(now=lambda: now)
    door_id = str(uuid4())

    ticket = store.issue(
        purpose="camera-preview",
        door_id=door_id,
        ttl_seconds=30,
    )
    store._now = lambda: now + timedelta(seconds=31)

    assert not store.consume(ticket.ticket, purpose="camera-preview", door_id=door_id)


def test_ticket_store_rejects_wrong_purpose() -> None:
    store = WebSocketTicketStore()
    door_id = str(uuid4())
    ticket = store.issue(
        purpose="camera-preview",
        door_id=door_id,
        ttl_seconds=30,
    )

    assert not store.consume(ticket.ticket, purpose="access-events", door_id=door_id)
    assert store.consume(ticket.ticket, purpose="camera-preview", door_id=door_id)


def test_ticket_store_rejects_wrong_door() -> None:
    store = WebSocketTicketStore()
    door_id = str(uuid4())
    ticket = store.issue(
        purpose="camera-preview",
        door_id=door_id,
        ttl_seconds=30,
    )

    assert not store.consume(
        ticket.ticket,
        purpose="camera-preview",
        door_id=str(uuid4()),
    )
    assert store.consume(ticket.ticket, purpose="camera-preview", door_id=door_id)
