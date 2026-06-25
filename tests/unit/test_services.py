"""
Unit Tests — User Service & Repository
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.models import SubscriptionCategory, User, UserRole
from services.user_service import UserService


@pytest.fixture
def mock_user() -> User:
    user = MagicMock(spec=User)
    user.id = 123456789
    user.username = "testuser"
    user.first_name = "Test"
    user.last_name = "User"
    user.language_code = "uz"
    user.role = UserRole.USER
    user.is_active = True
    user.messages_count = 0
    user.ai_queries_count = 0
    user.rating_points = 0
    user.premium_until = None
    user.referral_code = "TESTCODE"
    user.referred_by = None
    user.is_premium = False
    user.is_admin = False
    user.full_name = "Test User"
    from datetime import datetime
    user.created_at = datetime(2025, 1, 1)
    return user


@pytest.fixture
def mock_tg_user():
    tg = MagicMock()
    tg.id = 123456789
    tg.username = "testuser"
    tg.first_name = "Test"
    tg.last_name = "User"
    tg.language_code = "uz"
    tg.is_bot = False
    return tg


class TestUserService:
    @pytest.mark.asyncio
    async def test_register_new_user(self, mock_tg_user, mock_user):
        service = UserService()
        with (
            patch("services.user_service.get_db_session") as mock_session_ctx,
            patch("services.user_service.cache") as mock_cache,
        ):
            mock_repo = AsyncMock()
            mock_repo.get_or_create.return_value = (mock_user, True)
            mock_repo.get_subscriptions.return_value = []

            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_ctx.return_value = mock_session

            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)
            mock_cache.delete = AsyncMock(return_value=1)

            with patch("services.user_service.UserRepository", return_value=mock_repo):
                user, is_new = await service.register_or_update(mock_tg_user)

            assert is_new is True
            assert user.id == mock_tg_user.id

    @pytest.mark.asyncio
    async def test_get_user_from_cache(self, mock_user):
        service = UserService()
        cached_data = {
            "id": 123456789,
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "language_code": "uz",
            "role": "user",
            "is_active": True,
            "messages_count": 5,
            "ai_queries_count": 2,
            "rating_points": 10,
            "premium_until": None,
            "referral_code": "TESTCODE",
            "referred_by": None,
            "created_at": "2025-01-01T00:00:00",
        }
        with patch("services.user_service.cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=cached_data)
            user = await service.get_user(123456789)

        assert user is not None
        assert user.id == 123456789
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_check_banned_raises(self, mock_user):
        mock_user.role = UserRole.BANNED
        service = UserService()
        cached_data = {
            "id": 123456789, "username": "x", "first_name": "X",
            "last_name": None, "language_code": "uz", "role": "banned",
            "is_active": False, "messages_count": 0, "ai_queries_count": 0,
            "rating_points": 0, "premium_until": None, "referral_code": "X",
            "referred_by": None, "created_at": "2025-01-01T00:00:00",
        }
        from core.exceptions import UserBannedException
        with patch("services.user_service.cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=cached_data)
            with pytest.raises(UserBannedException):
                await service.check_banned(123456789)


class TestCacheManager:
    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_limit(self):
        from database.redis_client import CacheManager
        mgr = CacheManager(prefix="test")
        with patch.object(mgr, "_redis") as mock_redis:
            mock_redis.pipeline = MagicMock()
            mock_pipe = AsyncMock()
            mock_pipe.execute = AsyncMock(return_value=[5, True])
            mock_redis.pipeline.return_value = mock_pipe

            allowed, remaining = await mgr.check_rate_limit(
                user_id=1, action="msg", limit=30, window=60
            )
            assert allowed is True
            assert remaining == 25

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_over_limit(self):
        from database.redis_client import CacheManager
        mgr = CacheManager(prefix="test")
        with patch.object(mgr, "_redis") as mock_redis:
            mock_redis.pipeline = MagicMock()
            mock_pipe = AsyncMock()
            mock_pipe.execute = AsyncMock(return_value=[35, True])
            mock_redis.pipeline.return_value = mock_pipe

            allowed, remaining = await mgr.check_rate_limit(
                user_id=1, action="msg", limit=30, window=60
            )
            assert allowed is False
            assert remaining == 0


class TestNewsService:
    @pytest.mark.asyncio
    async def test_detect_category_ai(self):
        from services.news_service import HackerNewsService
        svc = HackerNewsService()
        from database.models import SubscriptionCategory
        cat = svc._detect_category("New GPT-5 model released by OpenAI")
        assert cat == SubscriptionCategory.AI

    @pytest.mark.asyncio
    async def test_detect_category_security(self):
        from services.news_service import HackerNewsService
        svc = HackerNewsService()
        cat = svc._detect_category("Critical vulnerability CVE-2025-0001 in nginx")
        assert cat == SubscriptionCategory.SECURITY

    @pytest.mark.asyncio
    async def test_detect_category_python(self):
        from services.news_service import HackerNewsService
        svc = HackerNewsService()
        cat = svc._detect_category("Python 3.13 released with new features")
        assert cat == SubscriptionCategory.PYTHON
