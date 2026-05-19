from uuid import UUID

import numpy as np
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.exceptions import FaceVectorLimitExceededError, FaceVectorNotFoundError
from src.faces.models import FaceVector
from src.faces.schemas import EMBEDDING_DIM, RecognizeResponse
from src.users.models import User


MAX_FACE_VECTORS_PER_USER = 100


async def list_face_vectors(
    user_id: UUID,
    session: AsyncSession,
    skip: int = 0,
    limit: int = MAX_FACE_VECTORS_PER_USER,
) -> tuple[int, list[FaceVector]]:
    total = (
        await session.exec(
            select(func.count())
            .select_from(FaceVector)
            .where(FaceVector.user_id == user_id)
        )
    ).one()
    faces = list(
        (
            await session.exec(
                select(FaceVector)
                .where(FaceVector.user_id == user_id)
                .offset(skip)
                .limit(limit)
            )
        ).all()
    )
    return total, faces


async def add_face_vector(
    user_id: UUID,
    embedding: bytes,
    session: AsyncSession,
) -> FaceVector:
    count = (
        await session.exec(
            select(func.count())
            .select_from(FaceVector)
            .where(FaceVector.user_id == user_id)
        )
    ).one()
    if count >= MAX_FACE_VECTORS_PER_USER:
        raise FaceVectorLimitExceededError()
    fv = FaceVector(user_id=user_id, embedding=embedding)
    session.add(fv)
    await session.commit()
    await session.refresh(fv)
    return fv


async def delete_face_vector(
    face_id: UUID,
    user_id: UUID,
    session: AsyncSession,
) -> None:
    fv = await session.get(FaceVector, face_id)
    if fv is None or fv.user_id != user_id:
        raise FaceVectorNotFoundError()
    await session.delete(fv)
    await session.commit()


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a_flat = a.flatten()
    b_flat = b.flatten()
    denom = np.linalg.norm(a_flat) * np.linalg.norm(b_flat)
    return float(np.dot(a_flat, b_flat) / denom) if denom != 0 else 0.0


async def recognize_face_vector(
    query_embedding: bytes,
    session: AsyncSession,
    threshold: float,
) -> RecognizeResponse:
    face_vectors = list((await session.exec(select(FaceVector))).all())
    if not face_vectors:
        return RecognizeResponse(
            matched=False,
            user_id=None,
            username=None,
            confidence=0.0,
        )

    query = np.frombuffer(query_embedding, dtype=np.float32).reshape(1, EMBEDDING_DIM)
    best_score = float("-inf")
    best_face: FaceVector | None = None

    for face_vector in face_vectors:
        stored = np.frombuffer(face_vector.embedding, dtype=np.float32).reshape(
            1,
            EMBEDDING_DIM,
        )
        score = _cosine(query, stored)
        if score > best_score:
            best_score = score
            best_face = face_vector

    if best_face is None or best_score < threshold:
        return RecognizeResponse(
            matched=False,
            user_id=None,
            username=None,
            confidence=best_score,
        )

    user = await session.get(User, best_face.user_id)
    if user is None:
        return RecognizeResponse(
            matched=False,
            user_id=None,
            username=None,
            confidence=0.0,
        )

    return RecognizeResponse(
        matched=True,
        user_id=user.id,
        username=user.username,
        confidence=best_score,
    )
