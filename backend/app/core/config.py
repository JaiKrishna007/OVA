from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_FILE = (BACKEND_DIR / "app.db").resolve()


class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"
    LLM_PROVIDER: str = "nvidia"
    LLM_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    GEMINI_API_KEY: str = ""
    NVIDIA_API_KEY: str = "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"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    JWT_SECRET: str = "change-me-kernel-prime-fertility-jwt-secret-key-32bytes"
    AS_OF_DATE: str = "2026-06-25"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    UPLOAD_DIR: str = str((BACKEND_DIR / "data" / "uploads").resolve())
    TEXT_EXTRACTOR: str = "default"
    PATIENT_SEES_AI_SUMMARY: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
