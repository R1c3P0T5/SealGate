"""Download YuNet ONNX model into jetson/models/."""

import hashlib
import sys
import urllib.request
from pathlib import Path

_MODELS_DIR = Path(__file__).parent.parent / "models"

_MODELS = [
    (
        "face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(filename: str, url: str, expected: str) -> None:
    dest = _MODELS_DIR / filename
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    if dest.exists() and _sha256(dest) == expected:
        print(f"{filename} already exists and passed checksum.")
        return

    print(f"Downloading {filename}...")
    try:
        urllib.request.urlretrieve(url, tmp)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)

    actual = _sha256(tmp)
    if actual != expected:
        tmp.unlink(missing_ok=True)
        print(
            f"Checksum mismatch for {filename}:\n  expected {expected}\n  got      {actual}",
            file=sys.stderr,
        )
        sys.exit(1)

    tmp.rename(dest)
    print(f"Saved {dest}")


def main() -> None:
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url, checksum in _MODELS:
        _download(filename, url, checksum)
    print("Face detection model is ready.")


if __name__ == "__main__":
    main()
