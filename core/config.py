"""
Core Configuration Module
Enterprise-grade settings management with Pydantic v2
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="botdb")
    POSTGRES_USER: str = Field(default="botuser")
    POSTGRES_PASSWORD: str = Field(default="password")
    DATABASE_URL: Optional[str] = None
    POOL_SIZE: int = Field(default=20)
    MAX_OVERFLOW: int = Field(default=10)
    POOL_TIMEOUT: int = Field(default=30)
    ECHO_SQL: bool = Field(default=False)

    @model_validator(mode="after")
    def build_database_url(self) -> "DatabaseSettings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = Field(default=0)
    REDIS_URL: Optional[str] = None
    REDIS_TTL: int = Field(default=3600)

    @model_validator(mode="after")
    def build_redis_url(self) -> "RedisSettings":
        if not self.REDIS_URL:
            if self.REDIS_PASSWORD:
                self.REDIS_URL = (
                    f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
                )
            else:
                self.REDIS_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return self


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    BOT_TOKEN: str = Field(default="")
    BOT_USERNAME: str = Field(default="mybot")
    WEBHOOK_HOST: Optional[str] = None
    WEBHOOK_PATH: str = Field(default="/webhook")
    WEBHOOK_PORT: int = Field(default=8443)
    USE_WEBHOOK: bool = Field(default=False)


class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4-turbo-preview")
    OPENAI_MAX_TOKENS: int = Field(default=4096)
    OPENAI_TEMPERATURE: float = Field(default=0.7)
    OPENAI_TIMEOUT: int = Field(default=60)


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    SECRET_KEY: str = Field(default="change-this-secret-key-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=60)
    ADMIN_IDS: str = Field(default="")
    RATE_LIMIT_MESSAGES: int = Field(default=30)
    RATE_LIMIT_WINDOW: int = Field(default=60)
    AI_RATE_LIMIT_MESSAGES: int = Field(default=10)
    AI_RATE_LIMIT_WINDOW: int = Field(default=60)

    @property
    def admin_ids_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


class SchedulerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    NEWS_UPDATE_INTERVAL: int = Field(default=15)
    GITHUB_UPDATE_INTERVAL: int = Field(default=60)
    HABR_UPDATE_INTERVAL: int = Field(default=30)


class ChannelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    NEWS_CHANNEL_ID: Optional[int] = None
    GITHUB_CHANNEL_ID: Optional[int] = None
    HABR_CHANNEL_ID: Optional[int] = None


class RabbitMQSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    RABBITMQ_HOST: str = Field(default="localhost")
    RABBITMQ_PORT: int = Field(default=5672)
    RABBITMQ_USER: str = Field(default="guest")
    RABBITMQ_PASSWORD: str = Field(default="guest")
    RABBITMQ_VHOST: str = Field(default="/")
    RABBITMQ_URL: Optional[str] = None
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    @model_validator(mode="after")
    def build_rabbitmq_url(self) -> "RabbitMQSettings":
        if not self.RABBITMQ_URL:
            self.RABBITMQ_URL = (
                f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}"
                f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}{self.RABBITMQ_VHOST}"
            )
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.RABBITMQ_URL
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # App
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="production")
    APP_VERSION: str = Field(default="1.0.0")
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="json")

    # Nested settings (loaded separately for better organization)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    channels: ChannelSettings = Field(default_factory=ChannelSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)

    # Premium
    PREMIUM_PRICE: float = Field(default=9.99)
    REFERRAL_BONUS_DAYS: int = Field(default=7)

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "testing"}
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings instance — use this everywhere."""
    return Settings()


# Convenience alias
settings = get_settings()
