from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Endee Atlas"))
    endee_base_url: str = field(
        default_factory=lambda: os.getenv("ENDEE_BASE_URL", "http://localhost:8080/api/v1")
    )
    endee_index_name: str = field(
        default_factory=lambda: os.getenv("ENDEE_INDEX_NAME", "talentforge_hiring")
    )
    endee_auth_token: str = field(default_factory=lambda: os.getenv("ENDEE_AUTH_TOKEN", ""))
    vector_store_backend: str = field(default_factory=lambda: os.getenv("VECTOR_STORE_BACKEND", "auto"))
    embedding_backend: str = field(default_factory=lambda: os.getenv("EMBEDDING_BACKEND", "hash"))
    endee_bootstrap_timeout_seconds: float = field(default_factory=lambda: _float_env("ENDEE_BOOTSTRAP_TIMEOUT_SECONDS", 30.0))
    endee_bootstrap_interval_seconds: float = field(default_factory=lambda: _float_env("ENDEE_BOOTSTRAP_INTERVAL_SECONDS", 1.5))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    )
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    seed_sample_data: bool = field(
        default_factory=lambda: os.getenv("SEED_SAMPLE_DATA", "true").strip().lower() not in {"0", "false", "no"}
    )
    upload_dir: Path = field(default_factory=lambda: Path(os.getenv("UPLOAD_DIR", "runtime/uploads")))


def load_settings() -> Settings:
    return Settings()
