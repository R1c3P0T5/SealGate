import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from src.handsign.jutsu import JutsuFSM


@dataclass
class HandsignDoorState:
    fsm: JutsuFSM
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class HandsignFSMRegistry:
    def __init__(self) -> None:
        self._states: dict[UUID, HandsignDoorState] = {}

    def load(self, door_id: UUID, jutsu_dict: dict[str, list[str]]) -> None:
        fsm = JutsuFSM(jutsu=jutsu_dict, gap_ms=3000, cooldown_ms=5000)
        # Preserve existing lock so in-flight feed requests aren't orphaned
        existing = self._states.get(door_id)
        lock = existing.lock if existing is not None else asyncio.Lock()
        self._states[door_id] = HandsignDoorState(fsm=fsm, lock=lock)

    def unload(self, door_id: UUID) -> None:
        self._states.pop(door_id, None)

    def get(self, door_id: UUID) -> HandsignDoorState | None:
        return self._states.get(door_id)
