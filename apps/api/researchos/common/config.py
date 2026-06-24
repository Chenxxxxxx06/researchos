"""Application configuration.

A single ``Settings`` object is loaded from environment variables (and an
optional ``.env`` file) and shared by both the API and the Celery worker. This
keeps configuration DRY and ensures the two processes agree on infrastructure
endpoints.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "staging", "production"]


class Settings(BaseSettings):
    """Typed application settings.

    Field names map to UPPER_SNAKE_CASE environment variables, e.g.
    ``postgres_dsn`` <- ``POSTGRES_DSN``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General -------------------------------------------------------------
    environment: Environment = "local"
    debug: bool = False

    # --- Logging -------------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool = True

    # --- API server ----------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Comma-separated list of allowed CORS origins.
    cors_origins: str = "http://localhost:3000"

    # --- Auth / sessions / CSRF ----------------------------------------------
    # Secret used to sign CSRF tokens (itsdangerous). MUST be overridden in
    # production via the SECRET_KEY environment variable.
    secret_key: str = "dev-insecure-secret-change-me"
    session_cookie_name: str = "ros_session"
    csrf_cookie_name: str = "ros_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    # Sliding session lifetime, in seconds (default 7 days).
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    # When None, derived from environment (Secure only in production).
    session_cookie_secure: bool | None = None
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    # --- PostgreSQL ----------------------------------------------------------
    postgres_dsn: str = "postgresql+asyncpg://researchos:researchos@localhost:5432/researchos"
    # Use a non-pooling engine. Recommended for the test suite (each test runs
    # in its own event loop) and for some serverless deployments.
    db_use_nullpool: bool = False

    # --- Redis / Celery ------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # --- Object storage (S3 / MinIO) ----------------------------------------
    s3_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key: str = "researchos"
    s3_secret_key: str = "researchos"
    s3_bucket: str = "researchos"

    # --- LLM provider --------------------------------------------------------
    # "mock" (default, no external calls), "anthropic", or future providers.
    llm_provider: str = "mock"
    # Model identifier passed to the provider. Intentionally NOT a hardcoded
    # vendor model id; supply a real model via the LLM_MODEL env var when using
    # a real provider. The mock provider ignores this value.
    llm_model: str = "mock-model"
    anthropic_api_key: str = ""

    # --- Paper search provider ----------------------------------------------
    paper_provider: str = "arxiv"
    arxiv_api_base: str = "http://export.arxiv.org/api/query"
    arxiv_timeout_seconds: float = 10.0
    paper_search_max_results: int = 25

    # --- Workspace (IDE) -----------------------------------------------------
    # Base directory holding per-project workspaces: <workspace_root>/<project_id>.
    workspace_root: str = "/data/workspaces"
    workspace_max_file_bytes: int = 1_000_000
    workspace_max_tree_entries: int = 5000
    workspace_max_tree_depth: int = 12

    # --- Agent runtime -------------------------------------------------------
    agent_max_tool_calls: int = 4
    agent_run_timeout_seconds: int = 120
    # Simple per-user rate limits (Redis sliding window).
    rate_limit_agent_runs_per_minute: int = 30
    rate_limit_paper_search_per_minute: int = 60

    # --- Derived values ------------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cookie_secure(self) -> bool:
        """Whether auth cookies set the ``Secure`` flag.

        Defaults to ``True`` only in production so local HTTP development works.
        Can be forced via the ``SESSION_COOKIE_SECURE`` environment variable.
        """

        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.environment == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @computed_field  # type: ignore[prop-decorator]
    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""

    return Settings()


# Convenient module-level handle for non-DI call sites (workers, scripts).
settings = get_settings()
