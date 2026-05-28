from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

_VALID_SIGNS = {
    "ne",
    "ushi",
    "tora",
    "u",
    "tatsu",
    "mi",
    "uma",
    "hitsuji",
    "saru",
    "tori",
    "inu",
    "i",
}


class JutsuCreateRequest(BaseModel):
    name: str = Field(max_length=128)
    signs: list[str] = Field(min_length=1)

    def model_post_init(self, __context: object) -> None:
        invalid = [s for s in self.signs if s not in _VALID_SIGNS]
        if invalid:
            raise ValueError(
                f"Invalid signs: {invalid}. Must be one of: {sorted(_VALID_SIGNS)}"
            )


class JutsuUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    signs: list[str] | None = Field(default=None, min_length=1)


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
