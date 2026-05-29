from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.handsign.jutsu import SIGN_KANJI

_VALID_SIGNS = frozenset(SIGN_KANJI)


def _validate_signs(signs: list[str]) -> None:
    invalid = [s for s in signs if s not in _VALID_SIGNS]
    if invalid:
        raise ValueError(
            f"Invalid signs: {invalid}. Must be one of: {sorted(_VALID_SIGNS)}"
        )


class JutsuCreateRequest(BaseModel):
    name: str = Field(max_length=128)
    signs: list[str] = Field(min_length=1)

    def model_post_init(self, __context: object) -> None:
        _validate_signs(self.signs)


class JutsuUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    signs: list[str] | None = Field(default=None, min_length=1)

    def model_post_init(self, __context: object) -> None:
        if self.signs is not None:
            _validate_signs(self.signs)


class JutsuResponse(BaseModel):
    id: UUID
    name: str
    signs: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class JutsuListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    jutsu: list[JutsuResponse]


class HandsignFeedRequest(BaseModel):
    sign: str = Field(description="Confirmed romaji sign name (e.g. 'tora').")
    timestamp: float = Field(description="Unix timestamp from Jetson.")


class HandsignFeedResponse(BaseModel):
    step: int = Field(description="Current FSM progress step (0-based).")
    total: int = Field(description="Total steps in the leading jutsu.")
    completed: bool = Field(description="Whether a jutsu was completed this feed.")
