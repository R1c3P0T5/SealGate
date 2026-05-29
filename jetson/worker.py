"""Jetson camera worker.

職責：
  - 從相機捕捉影格（capture_task，跑 STREAM_FPS）
  - 以 YuNet 本地偵測人臉（detect_task，跑 DETECT_FPS，獨立迴圈）
  - 偵測到人臉時 POST 至後端 /recognize
  - 後端送 "start" 訊號時才推送 JPEG 影格到 WS
"""
import asyncio
import concurrent.futures
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import httpx
import numpy as np
import websockets
from dotenv import load_dotenv

try:
    import mediapipe as mp  # type: ignore[import-untyped]
    import torch  # type: ignore[import-untyped]
    import torchvision.transforms as T  # type: ignore[import-untyped]

    try:
        from jetson.jutsu import SIGN_CLASSES, SignFilter  # type: ignore[import-untyped]
    except ImportError:
        from jutsu import SIGN_CLASSES, SignFilter  # type: ignore[import-untyped]

    _HANDSIGN_AVAILABLE = True
except ImportError:
    _HANDSIGN_AVAILABLE = False

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
    detector_model: str = "models/face_detection_yunet_2023mar.onnx"
    handsign_fps: int = 5
    handsign_hold_ms: int = 500
    handsign_checkpoint: str = "models/best_cnn.pth"
    handsign_threshold: float = 0.4


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
        detector_model=os.getenv("FACE_DETECTOR_MODEL", "models/face_detection_yunet_2023mar.onnx"),
        handsign_fps=int(os.getenv("HANDSIGN_FPS", "5")),
        handsign_hold_ms=int(os.getenv("HANDSIGN_HOLD_MS", "500")),
        handsign_checkpoint=os.getenv("HANDSIGN_CHECKPOINT", "models/best_cnn.pth"),
        handsign_threshold=float(os.getenv("HANDSIGN_THRESHOLD", "0.4")),
    )

_streaming = False
_frame_queue: asyncio.Queue[bytes]
_metadata_queue: asyncio.Queue[dict[str, object]]
_recognize_semaphore: asyncio.Semaphore
_http_client: httpx.AsyncClient
_background_tasks: set[asyncio.Task[None]] = set()
_next_recognize_at = 0.0
_latest_raw_frame: np.ndarray | None = None
_settings: WorkerSettings
_handsign_executor: concurrent.futures.ThreadPoolExecutor | None = None


def _drain_queue(queue: asyncio.Queue[Any]) -> None:
    while not queue.empty():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            break


def _load_detector() -> cv2.FaceDetectorYN:
    model = Path(_settings.detector_model)
    path = str(model if model.is_absolute() else Path(__file__).parent / model)
    return cv2.FaceDetectorYN.create(path, "", (320, 240))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _primary_face_box_from_faces(
    faces: np.ndarray | None, *, frame_width: int, frame_height: int
) -> dict[str, float] | None:
    if faces is None or len(faces) == 0:
        return None

    areas = faces[:, 2] * faces[:, 3]
    face = faces[int(np.argmax(areas))]
    x1 = _clamp(float(face[0]), 0.0, float(frame_width))
    y1 = _clamp(float(face[1]), 0.0, float(frame_height))
    x2 = _clamp(float(face[0] + face[2]), 0.0, float(frame_width))
    y2 = _clamp(float(face[1] + face[3]), 0.0, float(frame_height))

    return {
        "x": round(x1 / frame_width, 6),
        "y": round(y1 / frame_height, 6),
        "width": round(max(0.0, x2 - x1) / frame_width, 6),
        "height": round(max(0.0, y2 - y1) / frame_height, 6),
        "score": round(float(face[14]), 6),  # col 14 = confidence score (YuNet spec)
    }


def _face_boxes_payload(face_box: dict[str, float] | None) -> dict[str, Any]:
    return {"type": "face_boxes", "faces": [] if face_box is None else [face_box]}


def _detect_primary_face_box(
    detector: cv2.FaceDetectorYN, frame: np.ndarray
) -> dict[str, float] | None:
    h, w = frame.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(frame)
    return _primary_face_box_from_faces(faces, frame_width=w, frame_height=h)


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


async def _send_metadata(ws: object) -> None:
    while True:
        payload = await _metadata_queue.get()
        if not _streaming:
            continue
        try:
            await ws.send(json.dumps(payload))  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning("Metadata send failed: %s", exc)
            return


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
                metadata_task = asyncio.create_task(_send_metadata(ws))
                try:
                    async for raw_msg in ws:
                        msg = json.loads(raw_msg)
                        cmd = msg.get("type")
                        if cmd == "start":
                            _streaming = True
                            logger.info("Streaming started")
                        elif cmd == "stop":
                            _streaming = False
                            _drain_queue(_frame_queue)
                            _drain_queue(_metadata_queue)
                            logger.info("Streaming stopped")
                finally:
                    send_task.cancel()
                    metadata_task.cancel()
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
        cap = cv2.VideoCapture(_settings.camera_index, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
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
            face_box = await loop.run_in_executor(
                None, _detect_primary_face_box, detector, frame
            )
            if _streaming:
                payload = _face_boxes_payload(face_box)
                if _metadata_queue.full():
                    try:
                        _metadata_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    _metadata_queue.put_nowait(payload)
                except asyncio.QueueFull:
                    pass
            can_recognize = (
                not _recognize_semaphore.locked()
                and time.monotonic() >= _next_recognize_at
            )
            if can_recognize and face_box is not None:
                _next_recognize_at = (
                    time.monotonic() + _settings.recognize_min_interval_seconds
                )
                frame_bytes = await loop.run_in_executor(None, _encode_jpeg, frame)
                task = asyncio.create_task(_post_recognize(frame_bytes))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
        elapsed = time.monotonic() - t0
        await asyncio.sleep(max(0.0, detect_interval - elapsed))


async def handsign_task() -> None:
    global _handsign_executor
    if not _HANDSIGN_AVAILABLE:
        logger.info("mediapipe/torch not available — handsign loop disabled")
        return
    checkpoint = Path(_settings.handsign_checkpoint)
    full_path = checkpoint if checkpoint.is_absolute() else Path(__file__).parent / checkpoint
    if not full_path.exists():
        logger.warning("Handsign checkpoint not found: %s — loop disabled", full_path)
        return
    model = torch.load(str(full_path), map_location="cpu")
    model.eval()
    sign_filter = SignFilter(hold_ms=_settings.handsign_hold_ms)
    mp_hands = mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.5,
    )
    _handsign_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="handsign"
    )
    loop = asyncio.get_running_loop()
    interval = 1.0 / _settings.handsign_fps

    def _infer(frame: np.ndarray) -> tuple[int, float, list[dict]]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = mp_hands.process(rgb)
        hands_meta: list[dict] = []
        if not result.multi_hand_landmarks:
            return -1, 0.0, hands_meta
        lm = result.multi_hand_landmarks[0]
        h, w = frame.shape[:2]
        xs = [p.x * w for p in lm.landmark]
        ys = [p.y * h for p in lm.landmark]
        x1 = max(0, int(min(xs)) - 10)
        y1 = max(0, int(min(ys)) - 10)
        x2 = min(w, int(max(xs)) + 10)
        y2 = min(h, int(max(ys)) + 10)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return -1, 0.0, hands_meta
        inp = T.Compose([T.ToPILImage(), T.Resize((64, 64)), T.ToTensor()])(
            crop
        ).unsqueeze(0)
        with torch.no_grad():
            out = model(inp)
            probs = torch.softmax(out, dim=1)
            conf, idx = probs.max(dim=1)
        conf_val = conf.item()
        idx_val = int(idx.item())
        sign_name = SIGN_CLASSES[idx_val] if conf_val >= _settings.handsign_threshold else None
        hands_meta = [
            {
                "box": [x1 / w, y1 / h, (x2 - x1) / w, (y2 - y1) / h],
                "sign": sign_name,
                "confidence": round(conf_val, 4),
            }
        ]
        return idx_val, conf_val, hands_meta

    logger.info("Handsign loop starting at %d FPS", _settings.handsign_fps)
    while True:
        t0 = time.monotonic()
        frame = _latest_raw_frame
        if frame is not None:
            sign_idx, _confidence, hands_meta = await loop.run_in_executor(
                _handsign_executor, _infer, frame
            )
            if _streaming:
                payload: dict = {"type": "hand_meta", "hands": hands_meta}
                if _metadata_queue.full():
                    try:
                        _metadata_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    _metadata_queue.put_nowait(payload)
                except asyncio.QueueFull:
                    pass
            confirmed = sign_filter.update(
                sign_idx, SIGN_CLASSES, time.monotonic()
            )
            if confirmed:
                try:
                    await _http_client.post(
                        f"{_settings.backend_url}/api/doors/{_settings.door_id}/handsign/feed",
                        json={"sign": confirmed, "timestamp": time.time()},
                        headers={"X-Device-Token": _settings.device_token},
                        timeout=5,
                    )
                except Exception as exc:
                    logger.warning("Handsign feed POST failed: %s", exc)
        elapsed = time.monotonic() - t0
        await asyncio.sleep(max(0.0, interval - elapsed))


async def main() -> None:
    global _frame_queue, _metadata_queue, _recognize_semaphore, _http_client, _settings
    _settings = load_settings()
    _frame_queue = asyncio.Queue(maxsize=3)
    _metadata_queue = asyncio.Queue(maxsize=3)
    _recognize_semaphore = asyncio.Semaphore(_settings.max_recognize_in_flight)
    logger.info("Starting Jetson worker for door %s", _settings.door_id)
    async with httpx.AsyncClient() as client:
        _http_client = client
        await asyncio.gather(ws_task(), capture_task(), detect_task(), handsign_task())


if __name__ == "__main__":
    asyncio.run(main())
