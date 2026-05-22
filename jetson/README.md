# Jetson Facelock Worker

Async Python worker that runs on the Jetson device (or any Linux machine with a
camera). It captures frames, detects faces locally with YuNet, and forwards
images to the backend for recognition. Recognized matches trigger the door via
the backend's MQTT pipeline.

The worker maintains a WebSocket connection to the backend for live camera
streaming and receives start/stop commands from the dashboard. See
[`../README.md`](../README.md) for the system-level architecture.

## Setup

Install dependencies from the `jetson/` directory:

```bash
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values. See the [Environment](#environment)
section below for details.

Download the YuNet face detection model:

```bash
python scripts/download_models.py
```

The file is saved in `jetson/models/` and is intentionally ignored by Git.

## Running

Start the worker from the `jetson/` directory:

```bash
python worker.py
```

The worker connects to the backend WebSocket and begins capturing frames. Logs
are written to stdout.

## Environment

Copy `.env.example` to `.env` and set the following values:

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `BACKEND_URL` | Yes | HTTP base URL of the backend, e.g. `http://192.168.1.10:8000` |
| `BACKEND_WS_URL` | Yes | WebSocket base URL of the backend, e.g. `ws://192.168.1.10:8000` |
| `DOOR_ID` | Yes | UUID of the door this device is assigned to. Obtain from the backend admin panel. |
| `DEVICE_TOKEN` | Yes | Device token for authenticating with the backend. Obtain from the backend admin panel. |
| `CAMERA_INDEX` | No | V4L2 camera index (default `0`) |
| `JPEG_QUALITY` | No | JPEG compression quality sent to the backend (default `70`) |
| `STREAM_FPS` | No | Frames per second pushed over WebSocket when streaming (default `20`) |
| `DETECT_FPS` | No | Face detection loop frequency (default `10`) |
| `RECOGNIZE_MIN_INTERVAL_SECONDS` | No | Minimum gap between recognition requests (default `0.5`) |
| `RECOGNIZE_SUCCESS_COOLDOWN_SECONDS` | No | Cooldown after a successful match (default `3.0`) |
| `RECOGNIZE_FAILURE_COOLDOWN_SECONDS` | No | Cooldown after a failed match (default `0.5`) |
| `MAX_RECOGNIZE_IN_FLIGHT` | No | Maximum concurrent recognition requests (default `1`) |
| `CAMERA_FAIL_RETRY` | No | Consecutive read failures before reopening the camera (default `30`) |
| `FACE_DETECTOR_MODEL` | No | Path to YuNet ONNX model (default `models/face_detection_yunet_2023mar.onnx`) |

`DOOR_ID` and `DEVICE_TOKEN` are issued by the backend. Create a device through
the admin panel and copy the values into `.env`.

## Project Structure

```text
jetson/
├── worker.py               # Main async worker: capture, detect, stream, recognize
├── scripts/
│   └── download_models.py  # Downloads YuNet model into jetson/models/
├── models/                 # ONNX model files (git-ignored, populated by download script)
├── .env.example            # Environment variable template
└── requirements.txt        # Python dependencies
```
