from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "ContractMind AI"
    database_url: str = "sqlite:///./contractmind.db"

    # Gemini LLM configuration
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    # MongoDB persistence layer
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "contractmind"

    # Hindsight organizational memory configuration
    hindsight_path: str | None = None
    hindsight_base_url: str | None = None
    hindsight_api_key: str | None = None
    hindsight_bank_id: str | None = "contractmind-org"

    # Organization scoping
    organization_id: str = "default-org"

    # Legacy / optional keys
    groq_api_key: str | None = None
    openai_api_key: str | None = None

    api_prefix: str = "/api"
    pdf_max_size_mb: int = 10
    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT


def get_settings() -> Settings:
    return Settings(_env_file=PROJECT_ROOT / ".env")
