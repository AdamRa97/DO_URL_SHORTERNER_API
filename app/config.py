from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://urluser:urlpass@localhost:5432/urlshortener"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-to-a-32-char-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Alias generation
    SHORT_CODE_LENGTH: int = 7
    ALIAS_MAX_LENGTH: int = 50

    # Rate limiting (slowapi format)
    RATE_LIMIT_LINKS_CREATE: str = "20/minute"
    RATE_LIMIT_REDIRECT: str = "200/minute"

    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"


settings = Settings()
