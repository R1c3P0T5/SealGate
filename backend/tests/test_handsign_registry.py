import asyncio
from uuid import uuid4

import pytest

from src.handsign.registry import HandsignFSMRegistry


def test_registry_load_and_get() -> None:
    registry = HandsignFSMRegistry()
    door_id = uuid4()
    registry.load(door_id, {"火遁": ["亥", "寅"]})

    state = registry.get(door_id)
    assert state is not None
    assert isinstance(state.lock, asyncio.Lock)


def test_registry_get_missing_returns_none() -> None:
    registry = HandsignFSMRegistry()
    assert registry.get(uuid4()) is None


def test_registry_unload() -> None:
    registry = HandsignFSMRegistry()
    door_id = uuid4()
    registry.load(door_id, {"火遁": ["亥", "寅"]})
    registry.unload(door_id)
    assert registry.get(door_id) is None


@pytest.mark.asyncio
async def test_registry_lock_is_per_door() -> None:
    registry = HandsignFSMRegistry()
    door_a = uuid4()
    door_b = uuid4()
    registry.load(door_a, {"A": ["寅"]})
    registry.load(door_b, {"B": ["子"]})

    state_a = registry.get(door_a)
    state_b = registry.get(door_b)
    assert state_a is not None
    assert state_b is not None
    assert state_a.lock is not state_b.lock
