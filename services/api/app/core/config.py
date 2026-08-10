from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.gemini_config import GeminiNotConfiguredError, get_gemini_api_key

_API_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_API_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="ONFLOW_",
        extra="ignore",
    )

    cors_origins: str = ""  # must be set via ONFLOW_CORS_ORIGINS in production; empty = deny all non-local
    upload_dir: str = "data/uploads"
    # Clip retention for consented users (see app/services/clip_retention.py).
    retention_dir: str = "data/retained"
    # S3-compatible object storage for clip uploads (optional — falls back to local disk).
    s3_bucket: str = ""
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    # When > 0, completed jobs attach an S3 presigned GET ``video_playback_url`` (HTTPS) and skip
    # deleting the blob from object storage so the link stays valid until expiry / lifecycle rules.
    # 0 disables (default): no replay URL derived from uploads; blobs are deleted as today.
    clip_playback_presigned_ttl_seconds: int = 0
    # Redis for ARQ job queue + slowapi rate-limit storage. Required in production/staging.
    redis_url: str = ""
    # SQLite file for users, sessions, and beta feedback (always local).
    database_path: str = "data/onflow.db"
    force_job_failure: bool = False
    enable_dev_force_fail: bool = False

    # deployment: development | production (env var ONFLOW_ENV). Controls auth fail-closed rules.
    env: str = "development"

    # Database URL for clip jobs (Postgres in production). Empty = SQLite at database_path.
    database_url: str = ""

    # Auth (JWT / OAuth — see app/core/auth.py)
    jwt_secret: str = ""
    jwt_expiry_hours: int = 720  # 30 days
    # Comma-separated Google OAuth client IDs (web + iOS) for ID token verification.
    google_client_ids: str = ""
    # Apple Sign In bundle id (aud claim); Railway: ONFLOW_APPLE_BUNDLE_ID
    apple_bundle_id: str = "com.onflow.lite"

    # Comma-separated operator emails auto-promoted to users.is_admin on sign-in.
    # Required in production/staging; admin routes check users.is_admin (see app/deps/admin.py).
    admin_emails: str = ""
    sentry_dsn: str | None = None
    sentry_environment: str = "production"
    sentry_traces_sample_rate: float = 0.1

    # Product quota: max analyses per calendar month (enforced in clip_quota).
    # Free = 3/mo, Pro = 30/mo; Re-Up bonus credits apply after the monthly cap.
    rate_limit_free: int = 3
    rate_limit_pro: int = 30

    # --- Security / abuse throttles (NOT product quota; NOT Gemini tier or model routing) ---
    # Invite email session + claim: per client IP (slowapi).
    auth_rate_limit_per_minute: int = 5
    auth_rate_limit_per_hour: int = 20
    # Google / Apple token exchange: per client IP.
    oauth_rate_limit_per_minute: int = 10
    # Signed-in routes: per authenticated user id.
    feedback_rate_limit_per_minute: int = 10
    beta_event_rate_limit_per_minute: int = 60
    export_rate_limit_per_hour: int = 2
    delete_account_rate_limit_per_day: int = 1
    # Clip uploads: abuse ceiling (rolling windows in usage_limits + slowapi). Independent of
    # monthly free / Pro / bonus product quota in clip_quota.py.
    clip_rate_limit_per_hour: int = 10
    clip_rate_limit_per_day: int = 30
    # Max jobs in pending+processing per user; 0 = disable concurrent guard.
    clip_concurrent_processing_limit_per_user: int = 3
    # Server-side hard ceiling on the actual uploaded clip size (bytes), verified at
    # complete-upload before quota is charged or analysis is enqueued. 0 = disabled.
    # Default 200 MiB is generous headroom for a short high-bitrate clip; tune via
    # ONFLOW_CLIP_MAX_UPLOAD_BYTES.
    clip_max_upload_bytes: int = 200 * 1024 * 1024
    # Abandon pending V1 uploads older than this many hours (no complete-upload).
    # Reaper runs on API startup (best-effort). Minimum effective value is 1 hour.
    clip_pending_reap_hours: int = 24
    # RevenueCat webhook: per IP, lenient; auth header remains mandatory in production.
    webhook_rate_limit_per_minute: int = 120

    # RevenueCat store product IDs (webhook + docs)
    rc_product_reup_pack: str = "onflow_reup_pack_399"
    # Comma-separated Store product IDs that grant Pro (lifetime / yearly / monthly).
    # Unknown products are acknowledged but do not change tier.
    rc_pro_product_ids: str = ""
    # Comma-separated legacy one-time pack IDs that grant +3 bonus (no Pro tier); preserves old credits via webhook.
    rc_legacy_bonus_product_ids: str = ""

    # RevenueCat webhook secret (from RC dashboard → Webhooks → Authorization header)
    rc_webhook_secret: str = ""

    # Gemini — required for completed clip jobs (see gemini_clip_analyzer).
    # Tier selection is centralized in ``app.core.tiers.resolve_gemini_model_for_tier``.
    gemini_api_key: str = ""
    # Legacy single-model override (``ONFLOW_GEMINI_MODEL`` / bare ``GEMINI_MODEL``).
    # Prefer ``gemini_model_free`` / ``gemini_model_pro``; this is only used as a fallback
    # when a tier-specific model string is empty (see tiers.resolve_gemini_model_for_tier).
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = 45.0
    gemini_max_retries: int = 1
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 2048
    gemini_model_free: str = "gemini-2.5-flash-lite"
    gemini_model_pro: str = "gemini-2.5-flash"
    gemini_inline_max_bytes: int = 20 * 1024 * 1024
    # Daily Gemini spend ceiling (USD). 0 = disabled. Enforced via gemini_spend_daily table.
    gemini_daily_spend_cap_usd: float = 0.0

    # Twelve Labs Pegasus — Pro tier main + enrichment analysis.
    twelvelabs_api_key: str = ""
    twelvelabs_model: str = "pegasus1.5"
    twelvelabs_timeout_seconds: float = 90.0
    twelvelabs_max_retries: int = 1
    twelvelabs_max_output_tokens: int = 8192
    # Emergency rollback: Pro tier uses Gemini Flash instead of Pegasus.
    force_gemini_for_pro: bool = False

    # ARQ worker tuning. Bump arq_max_jobs as you add worker replicas / CPU.
    # ONFLOW_ARQ_MAX_JOBS, ONFLOW_ARQ_JOB_TIMEOUT.
    arq_max_jobs: int = 10
    arq_job_timeout: int = 300

    # SQLAlchemy connection pool (Postgres only; ignored for SQLite).
    # Tune in Railway env: ONFLOW_DB_POOL_SIZE, ONFLOW_DB_MAX_OVERFLOW, ONFLOW_DB_POOL_RECYCLE.
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_recycle: int = 1800

    @model_validator(mode="after")
    def _gemini_env_fallback(self) -> "Settings":
        if not self.gemini_api_key:
            try:
                object.__setattr__(self, "gemini_api_key", get_gemini_api_key().strip())
            except GeminiNotConfiguredError:
                pass
        # Legacy bare env var overrides removed — use ONFLOW_GEMINI_* prefixed vars only.
        # If you previously relied on GEMINI_MODEL etc., rename them to ONFLOW_GEMINI_MODEL.
        return self

    @model_validator(mode="after")
    def _production_requires_jwt_secret(self) -> "Settings":
        if self.is_production_or_staging and not (self.jwt_secret or "").strip():
            raise ValueError(
                "ONFLOW_JWT_SECRET must be set when ONFLOW_ENV is "
                "production, prod, or staging."
            )
        if self.is_production and not (self.database_url or "").strip():
            # SQLite cannot handle concurrent writers across API workers + ARQ + webhooks;
            # fail-closed at startup rather than silently routing prod traffic to a file DB.
            raise ValueError(
                "ONFLOW_DATABASE_URL must be set when ONFLOW_ENV is production or prod. "
                "SQLite cannot handle concurrent writers across API workers and ARQ."
            )
        if self.is_production_or_staging and not (self.admin_emails or "").strip():
            raise ValueError(
                "ONFLOW_ADMIN_EMAILS must be set when ONFLOW_ENV is "
                "production, prod, or staging."
            )
        if self.is_production_or_staging and not (self.rc_webhook_secret or "").strip():
            raise ValueError(
                "ONFLOW_RC_WEBHOOK_SECRET must be set when ONFLOW_ENV is "
                "production, prod, or staging."
            )
        if self.is_production_or_staging and not (self.rc_pro_product_ids or "").strip():
            raise ValueError(
                "ONFLOW_RC_PRO_PRODUCT_IDS must be set when ONFLOW_ENV is "
                "production, prod, or staging (comma-separated Store product IDs)."
            )
        if self.is_production_or_staging and (self.cors_origins or "").strip() == "*":
            raise ValueError(
                "ONFLOW_CORS_ORIGINS=* is not allowed when ONFLOW_ENV is "
                "production, prod, or staging. Set explicit origins."
            )
        if (self.admin_emails or "").strip():
            from app.core.admin import parse_admin_emails_strict

            parse_admin_emails_strict(self.admin_emails)
        if self.requires_distributed_rate_limits:
            redis_url = (self.redis_url or "").strip()
            if not redis_url:
                raise ValueError(
                    "ONFLOW_REDIS_URL must be set when ONFLOW_ENV is production, prod, or staging. "
                    "Distributed rate limits require Redis; in-memory slowapi storage is not allowed."
                )
            if not redis_url.startswith(("redis://", "rediss://")):
                raise ValueError(
                    "ONFLOW_REDIS_URL must be a redis:// or rediss:// URL in production/staging."
                )
            if not (self.twelvelabs_api_key or "").strip():
                raise ValueError(
                    "ONFLOW_TWELVELABS_API_KEY must be set when ONFLOW_ENV is "
                    "production, prod, or staging."
                )
            if not (self.gemini_api_key or "").strip():
                raise ValueError(
                    "ONFLOW_GEMINI_API_KEY must be set when ONFLOW_ENV is "
                    "production, prod, or staging (free-tier analysis)."
                )
            if not self.s3_configured:
                raise ValueError(
                    "ONFLOW_S3_BUCKET, ONFLOW_S3_ENDPOINT, ONFLOW_S3_ACCESS_KEY, and "
                    "ONFLOW_S3_SECRET_KEY must be set when ONFLOW_ENV is production, "
                    "prod, or staging. Real-device uploads require object storage."
                )
        return self

    @property
    def is_production(self) -> bool:
        return (self.env or "").strip().lower() in {"production", "prod"}

    @property
    def is_production_or_staging(self) -> bool:
        """Deployed environments where auth/admin config must fail closed at startup."""
        return (self.env or "").strip().lower() in {"production", "prod", "staging"}

    @property
    def requires_distributed_rate_limits(self) -> bool:
        """Production/staging: slowapi + delete-account limits must use shared Redis."""
        return (self.env or "").strip().lower() in {"production", "prod", "staging"}

    @property
    def s3_configured(self) -> bool:
        return bool(
            (self.s3_bucket or "").strip()
            and (self.s3_endpoint or "").strip()
            and (self.s3_access_key or "").strip()
            and (self.s3_secret_key or "").strip()
        )

    @property
    def retention_dir_resolved(self) -> Path:
        raw = (self.retention_dir or "").strip() or "data/retained"
        p = Path(raw)
        if p.is_absolute():
            return p.resolve()
        return (_API_DIR / p).resolve()

    @property
    def gemini_model_resolved(self) -> str:
        """
        Default model when call sites do not pass an account tier — not the main routing path.

        Production clip jobs must use ``resolve_gemini_model_for_tier`` so free users get
        Flash-Lite and paid users get Flash. This property stays for backward-compatible
        callers that omit tier (``legacy`` ``gemini_model`` first, then free-tier model).
        """
        return (self.gemini_model or "").strip() or (self.gemini_model_free or "").strip()

    def get_database_url(self) -> str:
        """URL for clip job storage: explicit DATABASE_URL or SQLite file (dev only)."""
        raw = (self.database_url or "").strip()
        if raw:
            return raw
        if self.is_production:
            # The model_validator above should have caught this at construction —
            # this guard exists in case Settings was built before env was set.
            raise RuntimeError(
                "ONFLOW_DATABASE_URL is not set in production. "
                "SQLite cannot handle concurrent writers; configure Postgres."
            )
        db_path = (_API_DIR / self.database_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
