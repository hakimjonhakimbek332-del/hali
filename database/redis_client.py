"""
Redis Client & Cache Utilities
Async Redis with connection pooling and type-safe helpers
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional, Type, TypeVar, Union

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_pool: Optional[ConnectionPool] = None
_client: Optional[Redis] = None


def get_redis_pool() -> ConnectionPool:
    """Return singleton connection pool."""
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis.REDIS_URL,
            max_connections=50,
            decode_responses=True,
        )
    return _pool


def get_redis_client() -> Redis:
    """Return singleton Redis client."""
    global _client
    if _client is None:
        _client = aioredis.Redis(connection_pool=get_redis_pool())
    return _client


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _client, _pool
    if _client:
        await _client.aclose()
        _client = None
    if _pool:
        await _pool.aclose()
        _pool = None
    logger.info("Redis connection closed")


async def check_redis_connection() -> bool:
    """Health check — returns True if Redis is reachable."""
    try:
        client = get_redis_client()
        await client.ping()
        return True
    except Exception as exc:
        logger.error("Redis health check failed", error=str(exc))
        return False


class CacheManager:
    """
    High-level cache manager with JSON serialization,
    rate limiting, and pub/sub helpers.
    """

    def __init__(self, prefix: str = "bot", ttl: int = settings.redis.REDIS_TTL) -> None:
        self.prefix = prefix
        self.default_ttl = ttl
        self._redis = get_redis_client()

    def _key(self, *parts: str) -> str:
        return f"{self.prefix}:" + ":".join(str(p) for p in parts)

    # ── Basic get / set / delete ───────────────────────────────────────────────

    async def get(self, *key_parts: str) -> Optional[Any]:
        raw = await self._redis.get(self._key(*key_parts))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(
        self,
        *key_parts: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        serialized = json.dumps(value, default=str) if not isinstance(value, str) else value
        return await self._redis.set(
            self._key(*key_parts),
            serialized,
            ex=ttl or self.default_ttl,
        )

    async def delete(self, *key_parts: str) -> int:
        return await self._redis.delete(self._key(*key_parts))

    async def exists(self, *key_parts: str) -> bool:
        return bool(await self._redis.exists(self._key(*key_parts)))

    async def expire(self, *key_parts: str, ttl: int) -> bool:
        return await self._redis.expire(self._key(*key_parts), ttl)

    # ── Rate Limiting ──────────────────────────────────────────────────────────

    async def check_rate_limit(
        self,
        user_id: int,
        action: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int]:
        """
        Sliding-window rate limiter.
        Returns (allowed: bool, remaining: int).
        """
        key = self._key("rate", action, str(user_id))
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        current_count = results[0]
        remaining = max(0, limit - current_count)
        return current_count <= limit, remaining

    # ── Counters ───────────────────────────────────────────────────────────────

    async def increment(self, *key_parts: str, amount: int = 1) -> int:
        return await self._redis.incrby(self._key(*key_parts), amount)

    async def decrement(self, *key_parts: str, amount: int = 1) -> int:
        return await self._redis.decrby(self._key(*key_parts), amount)

    # ── Sets ───────────────────────────────────────────────────────────────────

    async def sadd(self, *key_parts: str, member: str) -> int:
        return await self._redis.sadd(self._key(*key_parts), member)

    async def sismember(self, *key_parts: str, member: str) -> bool:
        return bool(await self._redis.sismember(self._key(*key_parts), member))

    async def smembers(self, *key_parts: str) -> set:
        return await self._redis.smembers(self._key(*key_parts))

    # ── Hash (for session/user state) ──────────────────────────────────────────

    async def hset(self, *key_parts: str, mapping: dict) -> int:
        serialized = {k: json.dumps(v, default=str) for k, v in mapping.items()}
        return await self._redis.hset(self._key(*key_parts), mapping=serialized)

    async def hgetall(self, *key_parts: str) -> dict:
        raw = await self._redis.hgetall(self._key(*key_parts))
        return {k: self._try_json(v) for k, v in raw.items()}

    @staticmethod
    def _try_json(value: str) -> Any:
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    # ── Pub/Sub ────────────────────────────────────────────────────────────────

    async def publish(self, channel: str, message: Any) -> int:
        payload = json.dumps(message, default=str)
        return await self._redis.publish(channel, payload)


# Singleton instances for reuse
cache = CacheManager(prefix="bot")
news_cache = CacheManager(prefix="news", ttl=900)  # 15 min
github_cache = CacheManager(prefix="github", ttl=3600)  # 1 hr
