#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
from pathlib import Path


DEV_ADMIN_PASSWORD = "AdminPassword123"
DEV_DOOR_ID = "00000000-0000-4000-8000-000000000001"
DEV_DEVICE_TOKEN = "dev-device-token"
DEV_COMPOSE_PROJECT = "sealgate-dev"

PLACEHOLDER_MARKERS = (
    "<",
    ">",
    "generate",
    "set-a-strong-password",
    "uuid-from-web-ui",
    "one-time-token-from-device",
)


def _is_missing_or_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env(path: Path, values: dict[str, str]) -> None:
    existing_lines = (
        path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    )
    seen: set[str] = set()
    output: list[str] = []

    for line in existing_lines:
        if "=" not in line or line.lstrip().startswith("#"):
            output.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in values:
            output.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            output.append(line)

    for key, value in values.items():
        if key not in seen:
            output.append(f"{key}={value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def _copy_example_if_missing(path: Path, example_path: Path) -> bool:
    if path.exists():
        return False
    if example_path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return True


def _set_if_missing(
    values: dict[str, str],
    key: str,
    value: str,
    *,
    force: bool = False,
) -> None:
    if force or _is_missing_or_placeholder(values.get(key)):
        values[key] = value


def ensure_env_files(repo_root: Path, *, reset: bool = False) -> None:
    """Create local development env files and fill only missing placeholders."""

    backend_env = repo_root / "backend" / ".env"
    jetson_env = repo_root / "jetson" / ".env"

    backend_created = _copy_example_if_missing(
        backend_env, repo_root / "backend" / ".env.example"
    )
    _copy_example_if_missing(jetson_env, repo_root / "jetson" / ".env.example")

    backend_values = _read_env(backend_env)
    _set_if_missing(backend_values, "SECRET_KEY", secrets.token_hex(32))
    _set_if_missing(
        backend_values,
        "DEBUG",
        "True",
        force=backend_created and backend_values.get("DEBUG") == "False",
    )
    _set_if_missing(backend_values, "DEFAULT_ADMIN_USERNAME", "admin")
    _set_if_missing(backend_values, "DEFAULT_ADMIN_PASSWORD", DEV_ADMIN_PASSWORD)
    _set_if_missing(backend_values, "DEFAULT_ADMIN_FULL_NAME", "Development Admin")
    _set_if_missing(backend_values, "DEFAULT_ADMIN_EMAIL", "admin@example.test")
    _write_env(backend_env, backend_values)

    jetson_values = _read_env(jetson_env)
    _set_if_missing(jetson_values, "BACKEND_URL", "http://backend:8000")
    _set_if_missing(jetson_values, "BACKEND_WS_URL", "ws://backend:8000")
    _set_if_missing(jetson_values, "DOOR_ID", DEV_DOOR_ID, force=reset)
    _set_if_missing(jetson_values, "DEVICE_TOKEN", DEV_DEVICE_TOKEN, force=reset)
    _write_env(jetson_env, jetson_values)


def _run(
    command: list[str],
    repo_root: Path,
    *,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=capture_output,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        if capture_output:
            if exc.stdout:
                print(exc.stdout, end="", file=sys.stdout)
            if exc.stderr:
                print(exc.stderr, end="", file=sys.stderr)
        raise


def _compose_command(*args: str) -> list[str]:
    return ["docker", "compose", "-p", DEV_COMPOSE_PROJECT, *args]


def reset_dev_stack(repo_root: Path) -> None:
    _run(_compose_command("down", "-v"), repo_root)


def _seed_env_args(repo_root: Path) -> list[str]:
    backend_values = _read_env(repo_root / "backend" / ".env")
    jetson_values = _read_env(repo_root / "jetson" / ".env")
    seed_values = {
        key: value
        for key, value in {
            "DEFAULT_ADMIN_USERNAME": backend_values.get("DEFAULT_ADMIN_USERNAME"),
            "DEFAULT_ADMIN_PASSWORD": backend_values.get("DEFAULT_ADMIN_PASSWORD"),
            "DEFAULT_ADMIN_FULL_NAME": backend_values.get("DEFAULT_ADMIN_FULL_NAME"),
            "DEFAULT_ADMIN_EMAIL": backend_values.get("DEFAULT_ADMIN_EMAIL"),
            "DEV_DOOR_ID": jetson_values.get("DOOR_ID"),
            "DEV_DEVICE_TOKEN": jetson_values.get("DEVICE_TOKEN"),
        }.items()
        if value is not None
    }
    args: list[str] = []
    for key, value in seed_values.items():
        args.extend(["-e", f"{key}={value}"])
    return args


def run_backend_seed(repo_root: Path) -> None:
    result = _run(
        _compose_command(
            "--profile",
            "server",
            "run",
            "--rm",
            *_seed_env_args(repo_root),
            "backend",
            "python",
            "-m",
            "scripts.dev_seed",
        ),
        repo_root,
        capture_output=True,
    )
    seed_result = json.loads(result.stdout.strip().splitlines()[-1])
    jetson_env = repo_root / "jetson" / ".env"
    jetson_values = _read_env(jetson_env)
    jetson_values["DOOR_ID"] = seed_result["door_id"]
    jetson_values["DEVICE_TOKEN"] = seed_result["device_token"]
    _write_env(jetson_env, jetson_values)


def download_models(repo_root: Path) -> None:
    _run(
        [sys.executable, str(repo_root / "jetson" / "scripts" / "download_models.py")],
        repo_root,
    )


def generate_openapi(repo_root: Path) -> None:
    openapi_path = repo_root / "openapi.json"
    if openapi_path.exists():
        return
    result = _run(
        _compose_command(
            "--profile",
            "server",
            "run",
            "--rm",
            "--no-deps",
            "backend",
            "python",
            "scripts/openapi-export.py",
        ),
        repo_root,
        capture_output=True,
    )
    openapi_path.write_text(result.stdout, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare local SealGate development data."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove local Compose volumes before recreating dev seed data.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    ensure_env_files(repo_root, reset=args.reset)
    if args.reset:
        reset_dev_stack(repo_root)
    run_backend_seed(repo_root)
    generate_openapi(repo_root)
    download_models(repo_root)
    print("Development setup ready.")
    print("Admin: admin / AdminPassword123")
    print(f"Jetson: DOOR_ID={DEV_DOOR_ID} DEVICE_TOKEN={DEV_DEVICE_TOKEN}")


if __name__ == "__main__":
    main()
