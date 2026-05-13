import logging
from typing import Annotated
from uuid import UUID

import cv2
import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    Form,
    Path,
    Query,
    UploadFile,
    WebSocket,
    status,
)
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.websockets import WebSocketDisconnect

from src.auth.dependencies import get_current_user
from src.core.access import require_self_or_admin
from src.core.config import get_settings
from src.core.database import SessionDep, session_context
from src.core.exceptions import (
    InvalidImageError,
    NoFaceDetectedError,
)
from src.faces.engine import EngineDep, FaceEngine
from src.faces.models import FaceVector
from src.faces.schemas import (
    FaceVectorListResponse,
    FaceVectorMetadata,
    RecognizeResponse,
)
from src.faces.service import (
    MAX_FACE_VECTORS_PER_USER,
    add_face_vector,
    delete_face_vector,
    list_face_vectors,
    recognize_face_vector,
)
from src.users.models import User


router = APIRouter(tags=["faces"])
logger = logging.getLogger(__name__)


def _to_metadata(face: FaceVector) -> FaceVectorMetadata:
    return FaceVectorMetadata(
        id=face.id,
        label=face.label,
        embedding_size=len(face.embedding),
        created_at=face.created_at,
    )


def _decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise InvalidImageError()
    return image


async def _recognize_image_bytes(
    data: bytes,
    session: AsyncSession,
    engine: FaceEngine,
    threshold: float,
) -> RecognizeResponse:
    image_bgr = _decode_image(data)
    embedding = engine.detect_and_embed(image_bgr)
    if embedding is None:
        raise NoFaceDetectedError()
    return await recognize_face_vector(
        embedding,
        session,
        threshold,
    )


def _websocket_error(error: str, detail: str) -> dict[str, object]:
    return {"type": "error", "error": error, "detail": detail}


def _websocket_result(response: RecognizeResponse) -> dict[str, object]:
    return {"type": "result", **response.model_dump(mode="json")}


@router.get(
    "/api/users/{user_id}/faces",
    response_model=FaceVectorListResponse,
    summary="List face vectors",
)
async def list_user_face_vectors(
    user_id: Annotated[UUID, Path(description="User ID whose face vectors to list.")],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
    skip: Annotated[
        int,
        Query(
            ge=0, description="Number of face vectors to skip before returning results."
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_FACE_VECTORS_PER_USER,
            description="Maximum number of face vectors to return.",
        ),
    ] = MAX_FACE_VECTORS_PER_USER,
) -> FaceVectorListResponse:
    require_self_or_admin(current_user, user_id)
    total, faces = await list_face_vectors(user_id, session, skip=skip, limit=limit)
    return FaceVectorListResponse(
        total=total,
        skip=skip,
        limit=limit,
        faces=[_to_metadata(face) for face in faces],
    )


@router.delete(
    "/api/users/{user_id}/faces/{face_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a face vector",
)
async def delete_user_face_vector(
    user_id: Annotated[UUID, Path(description="User ID that owns the face vector.")],
    face_id: Annotated[UUID, Path(description="Face vector ID to delete.")],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    require_self_or_admin(current_user, user_id)
    await delete_face_vector(face_id, user_id, session)


@router.post(
    "/api/users/{user_id}/faces/from-image",
    response_model=FaceVectorMetadata,
    status_code=status.HTTP_201_CREATED,
    summary="Add a face vector from image",
    description=(
        "Upload an image. The backend detects the largest face, computes a "
        "128-dim SFace embedding, and stores it."
    ),
)
async def add_face_from_image(
    user_id: Annotated[UUID, Path(description="User ID to attach the face to.")],
    image: UploadFile,
    session: SessionDep,
    engine: EngineDep,
    current_user: Annotated[User, Depends(get_current_user)],
    label: Annotated[str | None, Form(min_length=1, max_length=64)] = None,
) -> FaceVectorMetadata:
    require_self_or_admin(current_user, user_id)
    image_bgr = _decode_image(await image.read())
    embedding = engine.detect_and_embed(image_bgr)
    if embedding is None:
        raise NoFaceDetectedError()
    face = await add_face_vector(user_id, embedding, label, session)
    return _to_metadata(face)


@router.post(
    "/api/faces/recognize/from-image",
    response_model=RecognizeResponse,
    summary="Recognize a face from image",
    description=(
        "Upload an image. The backend detects the largest face, computes an "
        "embedding, and returns the closest matching user above the configured "
        "threshold. No authentication required."
    ),
)
async def recognize_face_from_image(
    image: UploadFile,
    session: SessionDep,
    engine: EngineDep,
) -> RecognizeResponse:
    return await _recognize_image_bytes(
        await image.read(),
        session,
        engine,
        get_settings().COSINE_THRESHOLD,
    )


@router.websocket("/ws/faces/recognize")
async def recognize_faces_websocket(
    websocket: WebSocket,
    engine: EngineDep,
) -> None:
    settings = get_settings()
    max_image_bytes = settings.WEBSOCKET_MAX_IMAGE_BYTES
    threshold = settings.COSINE_THRESHOLD

    await websocket.accept()
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            data = message.get("bytes")
            if data is None:
                await websocket.send_json(
                    _websocket_error(
                        "unsupported_message",
                        "Send image frames as binary WebSocket messages",
                    )
                )
                continue

            if len(data) > max_image_bytes:
                await websocket.send_json(
                    _websocket_error(
                        "image_too_large",
                        f"WebSocket image frame exceeds the {max_image_bytes} byte limit",
                    )
                )
                continue

            try:
                async with session_context() as session:
                    response = await _recognize_image_bytes(
                        data,
                        session,
                        engine,
                        threshold,
                    )
            except InvalidImageError as exc:
                await websocket.send_json(_websocket_error("invalid_image", exc.detail))
            except NoFaceDetectedError:
                await websocket.send_json(
                    _websocket_result(
                        RecognizeResponse(
                            matched=False,
                            user_id=None,
                            username=None,
                            confidence=0.0,
                        )
                    )
                )
            except Exception:
                logger.exception("Face recognition WebSocket frame failed")
                await websocket.send_json(
                    _websocket_error(
                        "recognition_failed",
                        "Face recognition failed",
                    )
                )
            else:
                await websocket.send_json(_websocket_result(response))
    except WebSocketDisconnect:
        return
