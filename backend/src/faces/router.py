from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    UploadFile,
    status,
)
from starlette.concurrency import run_in_threadpool

from src.auth.dependencies import get_current_user
from src.core.database import SessionDep
from src.core.exceptions import NoFaceDetectedError
from src.core.permissions import check_access
from src.faces.engine import EngineDep
from src.faces.models import FaceVector
from src.faces.schemas import (
    FaceVectorListResponse,
    FaceVectorMetadata,
)
from src.faces.service import (
    MAX_FACE_VECTORS_PER_USER,
    add_face_vector,
    decode_image,
    delete_face_vector,
    list_face_vectors,
)
from src.users.models import User


router = APIRouter(tags=["faces"])


def _to_metadata(face: FaceVector) -> FaceVectorMetadata:
    return FaceVectorMetadata(
        id=face.id,
        embedding_size=len(face.embedding),
        created_at=face.created_at,
    )


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
    await check_access(current_user, user_id, "face:read", session)
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
    await check_access(current_user, user_id, "face:delete", session)
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
) -> FaceVectorMetadata:
    await check_access(current_user, user_id, "face:create", session)
    image_bgr = decode_image(await image.read())
    embedding = await run_in_threadpool(engine.detect_and_embed, image_bgr)
    if embedding is None:
        raise NoFaceDetectedError()
    face = await add_face_vector(user_id, embedding, session)
    return _to_metadata(face)
