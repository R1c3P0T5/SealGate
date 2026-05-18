import pytest

from src.core.config import Settings, get_settings


def test_settings_requires_secret_key_with_minimum_length() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY not set or too short"):
        Settings(SECRET_KEY="short")


def test_get_settings_returns_cached_settings_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.SECRET_KEY == "a" * 32
    assert settings.DATABASE_URL == "sqlite+aiosqlite:///./test.db"
    assert get_settings() is settings


def test_settings_defaults_without_env_file() -> None:
    settings = Settings(SECRET_KEY="b" * 32, _env_file=None)  # type: ignore[call-arg]

    assert settings.DEBUG is False
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_EXPIRATION_HOURS == 24
    assert settings.DEFAULT_ADMIN_USERNAME is None
    assert settings.DEFAULT_ADMIN_PASSWORD is None
    assert settings.DEFAULT_ADMIN_FULL_NAME is None
    assert settings.DEFAULT_ADMIN_EMAIL is None


def test_settings_cosine_threshold_default() -> None:
    settings = Settings(SECRET_KEY="a" * 32, DEBUG=False, _env_file=None)  # type: ignore[call-arg]

    assert settings.COSINE_THRESHOLD == pytest.approx(0.363)


def test_settings_face_model_paths_contain_expected_filenames() -> None:
    settings = Settings(SECRET_KEY="a" * 32, DEBUG=False, _env_file=None)  # type: ignore[call-arg]

    assert "face_detection_yunet" in str(settings.FACE_DETECTOR_MODEL)
    assert "face_recognition_sface" in str(settings.FACE_RECOGNIZER_MODEL)
    assert str(settings.FACE_DETECTOR_MODEL).startswith("models/")
    assert str(settings.FACE_RECOGNIZER_MODEL).startswith("models/")


def test_settings_accepts_default_admin_username_and_password_only() -> None:
    settings = Settings(
        SECRET_KEY="c" * 32,
        DEFAULT_ADMIN_USERNAME="admin",
        DEFAULT_ADMIN_PASSWORD="AdminPassword123",
    )

    assert settings.DEFAULT_ADMIN_USERNAME == "admin"
    assert settings.DEFAULT_ADMIN_PASSWORD == "AdminPassword123"
    assert settings.DEFAULT_ADMIN_FULL_NAME is None
    assert settings.DEFAULT_ADMIN_EMAIL is None


def test_settings_requires_default_admin_username_and_password_together() -> None:
    with pytest.raises(
        ValueError,
        match="DEFAULT_ADMIN_USERNAME and DEFAULT_ADMIN_PASSWORD must be set together",
    ):
        Settings(SECRET_KEY="d" * 32, DEFAULT_ADMIN_USERNAME="admin", _env_file=None)  # type: ignore[call-arg]

    with pytest.raises(
        ValueError,
        match="DEFAULT_ADMIN_USERNAME and DEFAULT_ADMIN_PASSWORD must be set together",
    ):
        Settings(
            SECRET_KEY="e" * 32,
            DEFAULT_ADMIN_PASSWORD="AdminPassword123",
            _env_file=None,  # type: ignore[call-arg]
        )
