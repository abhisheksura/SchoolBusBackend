from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl, field_validator
from typing import List
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # App
    # -------------------------------------------------------------------------
    APP_NAME: str = "School Bus Tracker API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool
    ENVIRONMENT: str = "development"  # development | staging | production

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    DB_HOST: str | None = None
    DB_PORT: int | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_NAME: str | None = None
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30       # seconds to wait for a connection from pool
    DB_POOL_RECYCLE: int = 1800     # recycle connections every 30 minutes
    DB_POOL_PRE_PING: bool = True   # validate connection before checkout (essential for async pools)
    DB_ECHO: bool = False           # set True in dev to log SQL statements

    @property
    def DATABASE_URL(self) -> str:
        """
        Async DSN for SQLAlchemy + asyncpg.
        Format: postgresql+asyncpg://user:password@host:port/dbname
        """
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # -------------------------------------------------------------------------
    # JWT
    # -------------------------------------------------------------------------
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    BCRYPT_ROUNDS: int = 12

    # GPS Security
    # GPS_DEVICE_API_KEY: str

    # CORS — comma-separated origins in .env, e.g.:
    # ALLOWED_ORIGINS=http://localhost:3000,https://app.example.com
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # -------------------------------------------------------------------------
    # Pagination
    # -------------------------------------------------------------------------
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # -------------------------------------------------------------------------
    # GPS / Trip
    # -------------------------------------------------------------------------
    # GPS_STALE_THRESHOLD_SECONDS: int = 60   # ping older than this = stale
    # GPS_MIN_ACCURACY_METERS: float = 50.0   # filter out low-quality pings


# ---------------------------------------------------------------------------
# Singleton — import `settings` everywhere, never instantiate Settings again.
# ---------------------------------------------------------------------------
settings = Settings()
