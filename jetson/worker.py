"""Jetson camera worker.

職責：
  - 從相機捕捉影格（capture_task，跑 STREAM_FPS）
  - 以 YuNet 本地偵測人臉（detect_task，跑 DETECT_FPS，獨立迴圈）
  - 偵測到人臉時 POST 至後端 /recognize
  - 後端送 "start" 訊號時才推送 JPEG 影格到 WS
"""
import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import httpx
import numpy as np
import websockets
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerSettings:
    backend_url: str
    backend_ws_url: str
    door_id: str
    device_token: str
    camera_index: int = 0
    jpeg_quality: int = 70
    stream_fps: int = 20
    detect_fps: int = 10
    recognize_min_interval_seconds: float = 0.5
    recognize_success_cooldown_seconds: float = 3.0
    recognize_failure_cooldown_seconds: float = 0.5
    max_recognize_in_flight: int = 1
    camera_fail_retry: int = 30
    detector_model: str = "models/yunet.onnx"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def load_settings() -> WorkerSettings:
    load_dotenv()
    return WorkerSettings(
        backend_url=_required_env("BACKEND_URL"),
        backend_ws_url=_required_env("BACKEND_WS_URL"),
        door_id=_required_env("DOOR_ID"),
        device_token=_required_env("DEVICE_TOKEN"),
        camera_index=int(os.getenv("CAMERA_INDEX", "0")),
        jpeg_quality=int(os.getenv("JPEG_QUALITY", "70")),
        stream_fps=int(os.getenv("STREAM_FPS", "20")),
        detect_fps=int(os.getenv("DETECT_FPS", "10")),
        recognize_min_interval_seconds=float(
            os.getenv("RECOGNIZE_MIN_INTERVAL_SECONDS", "0.5")
        ),
        recognize_success_cooldown_seconds=float(
            os.getenv("RECOGNIZE_SUCCESS_COOLDOWN_SECONDS", "3.0")
        ),
        recognize_failure_cooldown_seconds=float(
            os.getenv("RECOGNIZE_FAILURE_COOLDOWN_SECONDS", "0.5")
        ),
        max_recognize_in_flight=int(os.getenv("MAX_RECOGNIZE_IN_FLIGHT", "1")),
        camera_fail_retry=int(os.getenv("CAMERA_FAIL_RETRY", "30")),
        detector_model=os.getenv("FACE_DETECTOR_MODEL", "models/yunet.onnx"),
    )

_streaming = False
_frame_queue: asyncio.Queue[bytes]
_recognize_semaphore: asyncio.Semaphore
_http_client: httpx.AsyncClient
_background_tasks: set[asyncio.Task[None]] = set()
_next_recognize_at = 0.0
_latest_raw_frame: np.ndarray | None = None
_settings: WorkerSettings


def _load_detector() -> cv2.FaceDetectorYN:
    path = str(Path(_settings.detector_model).resolve())
    return cv2.FaceDetectorYN.create(path, "", (320, 240))


def _detect_face(detector: cv2.FaceDetectorYN, frame: np.ndarray) -> bool:
    h, w = frame.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(frame)
    return faces is not None and len(faces) > 0


def _encode_jpeg(frame: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(
        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _settings.jpeg_quality]
    )
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return buf.tobytes()


async def _post_recognize(frame_bytes: bytes) -> None:
    global _next_recognize_at

    async with _recognize_semaphore:
        headers = {"X-Device-Token": _settings.device_token}
        cooldown = _settings.recognize_failure_cooldown_seconds
        try:
            r = await _http_client.post(
                f"{_settings.backend_url}/api/doors/{_settings.door_id}/recognize",
                files={"image": ("frame.jpg", frame_bytes, "image/jpeg")},
                headers=headers,
                timeout=8,
            )
            r.raise_for_status()
            result = r.json()
            cooldown = _settings.recognize_failure_cooldown_seconds
            if result.get("matched"):
                cooldown = _settings.recognize_success_cooldown_seconds
                logger.info(
                    "Recognized: %s (confidence=%.3f)",
                    result.get("username"),
                    result.get("confidence", 0),
                )
        except Exception as exc:
            logger.warning("Recognize failed: %s", exc)
            cooldown = _settings.recognize_failure_cooldown_seconds
        finally:
            new_at = time.monotonic() + cooldown
            _next_recognize_at = max(_next_recognize_at, new_at)


async def ws_task() -> None:
    """維持與後端的 WS 連線。監聽 start/stop，推送影格。"""
    global _streaming

    while True:
        url = f"{_settings.backend_ws_url}/ws/camera/{_settings.door_id}/push"
        try:
            async with websockets.connect(
                url,
                additional_headers={"X-Device-Token": _settings.device_token},
            ) as ws:
                logger.info("Connected to backend camera push endpoint")

                async def _send_frames() -> None:
                    while True:
                        frame_bytes = await _frame_queue.get()
                        if not _streaming:
                            continue
                        try:
                            await ws.send(frame_bytes)
                        except Exception:
                            return

                send_task = asyncio.create_task(_send_frames())
                try:
                    async for raw_msg in ws:
                        msg = json.loads(raw_msg)
                        cmd = msg.get("type")
                        if cmd == "start":
                            _streaming = True
                            logger.info("Streaming started")
                        elif cmd == "stop":
                            _streaming = False
                            while not _frame_queue.empty():
                                try:
                                    _frame_queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break
                            logger.info("Streaming stopped")
                finally:
                    send_task.cancel()
                    _streaming = False

        except Exception as exc:
            logger.warning("WS error: %s — retrying in 3s", exc)
            _streaming = False
            await asyncio.sleep(3)


async def capture_task() -> None:
    """捕捉相機影格（STREAM_FPS），串流時將 JPEG 放入佇列。"""
    global _latest_raw_frame
    loop = asyncio.get_running_loop()

    def _open_camera() -> cv2.VideoCapture:
        cap = cv2.VideoCapture(_settings.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {_settings.camera_index}")
        logger.info("Camera opened (index=%d)", _settings.camera_index)
        return cap

    cap: cv2.VideoCapture | None = None
    while cap is None:
        try:
            cap = _open_camera()
        except RuntimeError as exc:
            logger.warning("Cannot open camera at startup: %s — retrying in 5s", exc)
            await asyncio.sleep(5.0)

    frame_interval = 1.0 / _settings.stream_fps
    consecutive_failures = 0
    try:
        while True:
            t0 = time.monotonic()
            ret, frame = await loop.run_in_executor(None, cap.read)
            if not ret:
                consecutive_failures += 1
                if consecutive_failures >= _settings.camera_fail_retry:
                    logger.warning("Camera read failed %d times — reopening", consecutive_failures)
                    cap.release()
                    await asyncio.sleep(1.0)
                    try:
                        cap = _open_camera()
                        consecutive_failures = 0
                    except RuntimeError as exc:
                        logger.warning("Cannot reopen camera: %s — retrying in 5s", exc)
                        await asyncio.sleep(4.0)
                else:
                    await asyncio.sleep(0.1)
                continue
            consecutive_failures = 0
            _latest_raw_frame = frame

            if _streaming:
                frame_bytes = await loop.run_in_executor(None, _encode_jpeg, frame)
                if _frame_queue.full():
                    try:
                        _frame_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    _frame_queue.put_nowait(frame_bytes)
                except asyncio.QueueFull:
                    pass

            elapsed = time.monotonic() - t0
            await asyncio.sleep(max(0.0, frame_interval - elapsed))
    finally:
        cap.release()
        logger.info("Camera released")


async def detect_task() -> None:
    """以 DETECT_FPS 獨立迴圈做人臉偵測，觸發 recognize。"""
    global _next_recognize_at
    loop = asyncio.get_running_loop()

    detector = _load_detector()
    detect_interval = 1.0 / _settings.detect_fps
    while True:
        t0 = time.monotonic()
        frame = _latest_raw_frame
        if frame is not None:
            can_recognize = (
                not _recognize_semaphore.locked()
                and time.monotonic() >= _next_recognize_at
            )
            if can_recognize:
                face_found = await loop.run_in_executor(None, _detect_face, detector, frame)
                if face_found:
                    _next_recognize_at = (
                        time.monotonic() + _settings.recognize_min_interval_seconds
                    )
                    frame_bytes = await loop.run_in_executor(None, _encode_jpeg, frame)
                    task = asyncio.create_task(_post_recognize(frame_bytes))
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
        elapsed = time.monotonic() - t0
        await asyncio.sleep(max(0.0, detect_interval - elapsed))


async def main() -> None:
    global _frame_queue, _recognize_semaphore, _http_client, _settings
    _settings = load_settings()
    _frame_queue = asyncio.Queue(maxsize=3)
    _recognize_semaphore = asyncio.Semaphore(_settings.max_recognize_in_flight)
    logger.info("Starting Jetson worker for door %s", _settings.door_id)
    async with httpx.AsyncClient() as client:
        _http_client = client
        await asyncio.gather(ws_task(), capture_task(), detect_task())


if __name__ == "__main__":
    asyncio.run(main())
