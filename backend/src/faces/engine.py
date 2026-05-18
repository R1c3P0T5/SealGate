from pathlib import Path
from typing import Annotated

import cv2
import numpy as np
from fastapi import Depends

from src.core.config import get_settings


class FaceEngine:
    def __init__(self, detector_model: Path, recognizer_model: Path) -> None:
        self._detector = cv2.FaceDetectorYN.create(
            model=str(detector_model),
            config="",
            input_size=(320, 320),
            score_threshold=0.9,
            nms_threshold=0.3,
            top_k=50,
        )
        self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer_model), "")

    def detect_largest(self, image_bgr: np.ndarray) -> np.ndarray | None:
        height, width = image_bgr.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(image_bgr)
        if faces is None or len(faces) == 0:
            return None
        areas = faces[:, 2] * faces[:, 3]
        return faces[int(np.argmax(areas))]

    def embed(self, image_bgr: np.ndarray, face_row: np.ndarray) -> bytes:
        aligned = self._recognizer.alignCrop(image_bgr, face_row)
        feature = self._recognizer.feature(aligned)
        return np.asarray(feature, dtype=np.float32).tobytes()

    def detect_and_embed(self, image_bgr: np.ndarray) -> bytes | None:
        face_row = self.detect_largest(image_bgr)
        if face_row is None:
            return None
        return self.embed(image_bgr, face_row)


_engine: FaceEngine | None = None


async def load_engine() -> None:
    global _engine
    settings = get_settings()
    _engine = FaceEngine(settings.FACE_DETECTOR_MODEL, settings.FACE_RECOGNIZER_MODEL)


async def unload_engine() -> None:
    global _engine
    _engine = None


def get_engine() -> FaceEngine:
    if _engine is None:
        raise RuntimeError("FaceEngine not loaded. Call load_engine() first.")
    return _engine


EngineDep = Annotated[FaceEngine, Depends(get_engine)]
