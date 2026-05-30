import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


def _load_dev_setup_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dev_setup.py"
    spec = importlib.util.spec_from_file_location("dev_setup", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_ensure_env_files_creates_development_defaults(tmp_path: Path) -> None:
    dev_setup = _load_dev_setup_module()
    _write(tmp_path / ".env.example", "CLOUDFLARE_TUNNEL_TOKEN=\n")
    _write(
        tmp_path / "backend" / ".env.example",
        "\n".join(
            [
                "SECRET_KEY=<generate-32-byte-random-string-with-openssl-rand-hex-32>",
                "DATABASE_URL=sqlite+aiosqlite:////app/data/sealgate.db",
                "DEBUG=False",
                "DEFAULT_ADMIN_USERNAME=admin",
                "DEFAULT_ADMIN_PASSWORD=<set-a-strong-password>",
            ]
        ),
    )
    _write(
        tmp_path / "jetson" / ".env.example",
        "\n".join(
            [
                "BACKEND_URL=http://backend:8000",
                "BACKEND_WS_URL=ws://backend:8000",
                "DOOR_ID=<uuid-from-web-ui-door-page>",
                "DEVICE_TOKEN=<one-time-token-from-device-create-or-rotate>",
            ]
        ),
    )

    dev_setup.ensure_env_files(tmp_path)

    backend_env = (tmp_path / "backend" / ".env").read_text(encoding="utf-8")
    jetson_env = (tmp_path / "jetson" / ".env").read_text(encoding="utf-8")
    assert not (tmp_path / ".env").exists()
    assert "SECRET_KEY=<generate" not in backend_env
    assert "DEBUG=True" in backend_env
    assert "DEFAULT_ADMIN_PASSWORD=AdminPassword123" in backend_env
    assert "DOOR_ID=00000000-0000-4000-8000-000000000001" in jetson_env
    assert "DEVICE_TOKEN=dev-device-token" in jetson_env


def test_ensure_env_files_preserves_existing_custom_values(tmp_path: Path) -> None:
    dev_setup = _load_dev_setup_module()
    _write(tmp_path / ".env.example", "CLOUDFLARE_TUNNEL_TOKEN=\n")
    _write(tmp_path / "backend" / ".env.example", "SECRET_KEY=<generate>\n")
    _write(
        tmp_path / "jetson" / ".env.example", "DOOR_ID=<uuid>\nDEVICE_TOKEN=<token>\n"
    )
    _write(
        tmp_path / "backend" / ".env",
        "SECRET_KEY=" + ("b" * 64) + "\nDEFAULT_ADMIN_PASSWORD=CustomPass123\n",
    )
    _write(
        tmp_path / "jetson" / ".env",
        "DOOR_ID=11111111-1111-4111-8111-111111111111\nDEVICE_TOKEN=custom-token\n",
    )

    dev_setup.ensure_env_files(tmp_path)

    assert "DEFAULT_ADMIN_PASSWORD=CustomPass123" in (
        tmp_path / "backend" / ".env"
    ).read_text(encoding="utf-8")
    jetson_env = (tmp_path / "jetson" / ".env").read_text(encoding="utf-8")
    assert "DOOR_ID=11111111-1111-4111-8111-111111111111" in jetson_env
    assert "DEVICE_TOKEN=custom-token" in jetson_env


def test_ensure_env_files_preserves_existing_debug_false(tmp_path: Path) -> None:
    dev_setup = _load_dev_setup_module()
    _write(tmp_path / ".env.example", "CLOUDFLARE_TUNNEL_TOKEN=\n")
    _write(tmp_path / "backend" / ".env.example", "SECRET_KEY=<generate>\n")
    _write(
        tmp_path / "jetson" / ".env.example", "DOOR_ID=<uuid>\nDEVICE_TOKEN=<token>\n"
    )
    _write(
        tmp_path / "backend" / ".env", "SECRET_KEY=" + ("b" * 64) + "\nDEBUG=False\n"
    )

    dev_setup.ensure_env_files(tmp_path)

    assert "DEBUG=False" in (tmp_path / "backend" / ".env").read_text(encoding="utf-8")


def test_ensure_env_files_reset_rewrites_dev_jetson_identity(tmp_path: Path) -> None:
    dev_setup = _load_dev_setup_module()
    _write(tmp_path / ".env.example", "CLOUDFLARE_TUNNEL_TOKEN=\n")
    _write(tmp_path / "backend" / ".env.example", "SECRET_KEY=<generate>\n")
    _write(
        tmp_path / "jetson" / ".env.example", "DOOR_ID=<uuid>\nDEVICE_TOKEN=<token>\n"
    )
    _write(
        tmp_path / "jetson" / ".env",
        "DOOR_ID=11111111-1111-4111-8111-111111111111\nDEVICE_TOKEN=custom-token\n",
    )

    dev_setup.ensure_env_files(tmp_path, reset=True)

    jetson_env = (tmp_path / "jetson" / ".env").read_text(encoding="utf-8")
    assert "DOOR_ID=00000000-0000-4000-8000-000000000001" in jetson_env
    assert "DEVICE_TOKEN=dev-device-token" in jetson_env


def test_reset_dev_stack_uses_dev_compose_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dev_setup = _load_dev_setup_module()
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(dev_setup.subprocess, "run", fake_run)

    dev_setup.reset_dev_stack(tmp_path)

    assert calls == [["docker", "compose", "-p", "sealgate-dev", "down", "-v"]]


def test_run_backend_seed_passes_env_values_and_syncs_returned_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dev_setup = _load_dev_setup_module()
    _write(tmp_path / "backend" / ".env", "DEFAULT_ADMIN_USERNAME=owner\n")
    _write(
        tmp_path / "jetson" / ".env",
        "DOOR_ID=11111111-1111-4111-8111-111111111111\nDEVICE_TOKEN=custom-token\n",
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        stdout = json.dumps(
            {
                "door_id": "22222222-2222-4222-8222-222222222222",
                "device_token": "custom-token",
            }
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout)

    monkeypatch.setattr(dev_setup.subprocess, "run", fake_run)

    dev_setup.run_backend_seed(tmp_path)

    assert calls == [
        [
            "docker",
            "compose",
            "-p",
            "sealgate-dev",
            "--profile",
            "server",
            "run",
            "--rm",
            "-e",
            "DEFAULT_ADMIN_USERNAME=owner",
            "-e",
            "DEV_DOOR_ID=11111111-1111-4111-8111-111111111111",
            "-e",
            "DEV_DEVICE_TOKEN=custom-token",
            "backend",
            "python",
            "-m",
            "scripts.dev_seed",
        ]
    ]
    jetson_env = (tmp_path / "jetson" / ".env").read_text(encoding="utf-8")
    assert "DOOR_ID=22222222-2222-4222-8222-222222222222" in jetson_env
    assert "DEVICE_TOKEN=custom-token" in jetson_env
