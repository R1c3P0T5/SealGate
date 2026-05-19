from datetime import datetime
from uuid import uuid4


def test_metadata_and_list_response_expose_embedding_size_and_faces() -> None:
    from src.faces.schemas import FaceVectorListResponse, FaceVectorMetadata

    metadata = FaceVectorMetadata(
        id=uuid4(),
        embedding_size=512,
        created_at=datetime(2026, 5, 11),
    )
    response = FaceVectorListResponse(total=1, skip=0, limit=100, faces=[metadata])

    assert metadata.id
    assert metadata.embedding_size == 512
    assert response.total == 1
    assert response.skip == 0
    assert response.limit == 100
    assert response.faces == [metadata]
