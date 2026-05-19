from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    SECRET_KEY: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///./jetson_facelock.db"
    DEBUG: bool = False
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    DEFAULT_ADMIN_USERNAME: str | None = None
    DEFAULT_ADMIN_PASSWORD: str | None = None
    DEFAULT_ADMIN_FULL_NAME: str | None = None
    DEFAULT_ADMIN_EMAIL: str | None = None
    FACE_DETECTOR_MODEL: Path = Path("models/face_detection_yunet_2023mar.onnx")
    FACE_RECOGNIZER_MODEL: Path = Path("models/face_recognition_sface_2021dec.onnx")
    COSINE_THRESHOLD: float = 0.363

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY not set or too short (min 32 characters). "
                'Run: python3 -c "import secrets; print(secrets.token_hex(32))" '
                "and set in .env"
            )
        has_admin_username = self.DEFAULT_ADMIN_USERNAME is not None
        has_admin_password = self.DEFAULT_ADMIN_PASSWORD is not None
        if has_admin_username != has_admin_password:
            raise ValueError(
                "DEFAULT_ADMIN_USERNAME and DEFAULT_ADMIN_PASSWORD must be set together"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
