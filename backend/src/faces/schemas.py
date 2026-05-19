from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


EMBEDDING_DIM = 128
EMBEDDING_BYTES = 512  # 128 × float32 (4 bytes each)


class FaceVectorMetadata(BaseModel):
    """Face vector metadata — does not expose raw embedding bytes."""

    id: UUID = Field(description="Stable face vector identifier.")
    embedding_size: int = Field(description="Stored embedding size in bytes.")
    created_at: datetime = Field(
        description="UTC timestamp when the vector was created."
    )


class FaceVectorListResponse(BaseModel):
    total: int = Field(description="Total number of face vectors stored.")
    skip: int = Field(description="Number of face vectors skipped.")
    limit: int = Field(description="Maximum face vectors requested.")
    faces: list[FaceVectorMetadata] = Field(description="Face vectors.")


class RecognizeResponse(BaseModel):
    matched: bool = Field(description="Whether a face vector matched the request.")
    user_id: UUID | None = Field(default=None, description="Matched user identifier.")
    username: str | None = Field(default=None, description="Matched username.")
    confidence: float = Field(description="Recognition confidence score.")
