"""
User Service — Business Logic Layer
Handles registration, profiles, referrals, subscriptions
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from aiogram.types import User as TelegramUser

from core.config import settings
from core.exceptions import UserBannedException, UserNotFoundException
from core.logging import get_logger
from database.connection import get_db_session
from database.models import SubscriptionCategory, User, UserRole
from database.redis_client import cache
from repositories.user_repository import UserRepository

logger = get_logger(__name__)

CACHE_TTL = 300  # 5 minutes


class UserService:
    """
    Stateless service — creates its own DB sessions per operation.
    """

    async def register_or_update(
        self, tg_user: TelegramUser, referral_code: Optional[str] = None
    ) -> tuple[User, bool]:
        """
        Register a new user or update their info.
        Returns (user, is_new).
        """
        referred_by_id: Optional[int] = None

        if referral_code:
            async with get_db_session() as session:
                repo = UserRepository(session)
                referrer = await repo.get_by_referral_code(referral_code)
                if referrer and referrer.id != tg_user.id:
                    referred_by_id = referrer.id

        async with get_db_session() as session:
            repo = UserRepository(session)
            user, is_new = await repo.get_or_create(
                telegram_id=tg_user.id,
                first_name=tg_user.first_name or "Unknown",
                username=tg_user.username,
                last_name=tg_user.last_name,
                language_code=tg_user.language_code or "uz",
                referred_by=referred_by_id,
            )

            # Referral bonus
            if is_new and referred_by_id:
                referrer_repo = UserRepository(session)
                try:
                    await referrer_repo.set_premium(
                        referred_by_id, settings.REFERRAL_BONUS_DAYS
                    )
                    await referrer_repo.add_rating(referred_by_id, 50)
                    logger.info(
                        "Referral bonus granted",
                        referrer_id=referred_by_id,
                        new_user=tg_user.id,
                    )
                except Exception as exc:
                    logger.error("Referral bonus failed", error=str(exc))

            user_dict = self._user_to_dict(user)

        if is_new:
            # Default subscriptions for new users
            await self.subscribe(tg_user.id, SubscriptionCategory.ALL)
            logger.info("New user registered", user_id=tg_user.id, username=tg_user.username)

        # Cache user
        await cache.set("user", str(tg_user.id), value=user_dict, ttl=CACHE_TTL)
        return user, is_new

    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user from cache first, then DB."""
        cached = await cache.get("user", str(user_id))
        if cached:
            return self._dict_to_user(cached)

        async with get_db_session() as session:
            repo = UserRepository(session)
            user = await repo.get_by_id(user_id)

        if user:
            await cache.set("user", str(user_id), value=self._user_to_dict(user), ttl=CACHE_TTL)
        return user

    async def get_user_or_raise(self, user_id: int) -> User:
        user = await self.get_user(user_id)
        if not user:
            raise UserNotFoundException(user_id)
        return user

    async def check_banned(self, user_id: int) -> None:
        """Raise UserBannedException if the user is banned."""
        user = await self.get_user(user_id)
        if user and user.role == UserRole.BANNED:
            raise UserBannedException()

    async def subscribe(
        self, user_id: int, category: SubscriptionCategory
    ) -> None:
        async with get_db_session() as session:
            repo = UserRepository(session)
            await repo.subscribe(user_id, category)
        await self._invalidate_cache(user_id)

    async def unsubscribe(
        self, user_id: int, category: SubscriptionCategory
    ) -> None:
        async with get_db_session() as session:
            repo = UserRepository(session)
            await repo.unsubscribe(user_id, category)
        await self._invalidate_cache(user_id)

    async def get_subscriptions(self, user_id: int) -> List[SubscriptionCategory]:
        async with get_db_session() as session:
            repo = UserRepository(session)
            return await repo.get_subscriptions(user_id)

    async def increment_messages(self, user_id: int) -> None:
        async with get_db_session() as session:
            repo = UserRepository(session)
            await repo.increment_messages(user_id)
        await self._invalidate_cache(user_id)

    async def increment_ai_queries(self, user_id: int) -> None:
        async with get_db_session() as session:
            repo = UserRepository(session)
            await repo.increment_ai_queries(user_id)
            await repo.add_rating(user_id, 5)
        await self._invalidate_cache(user_id)

    async def get_stats(self) -> Dict:
        """Get overall bot statistics."""
        async with get_db_session() as session:
            repo = UserRepository(session)
            return {
                "total_users": await repo.count_total(),
                "active_today": await repo.count_active_today(),
                "new_today": await repo.count_new_today(),
            }

    async def get_leaderboard(self, limit: int = 10) -> List[User]:
        async with get_db_session() as session:
            repo = UserRepository(session)
            return list(await repo.get_leaderboard(limit))

    async def set_premium(self, user_id: int, days: int) -> User:
        async with get_db_session() as session:
            repo = UserRepository(session)
            user = await repo.set_premium(user_id, days)
        await self._invalidate_cache(user_id)
        return user

    async def ban_user(self, user_id: int) -> User:
        async with get_db_session() as session:
            repo = UserRepository(session)
            user = await repo.ban(user_id)
        await self._invalidate_cache(user_id)
        return user

    async def unban_user(self, user_id: int) -> User:
        async with get_db_session() as session:
            repo = UserRepository(session)
            user = await repo.unban(user_id)
        await self._invalidate_cache(user_id)
        return user

    async def make_admin(self, user_id: int) -> User:
        async with get_db_session() as session:
            repo = UserRepository(session)
            user = await repo.update_role(user_id, UserRole.ADMIN)
        await self._invalidate_cache(user_id)
        return user

    async def get_subscribed_users(
        self, category: SubscriptionCategory
    ) -> List[int]:
        async with get_db_session() as session:
            repo = UserRepository(session)
            return list(await repo.get_subscribed_users(category))

    async def _invalidate_cache(self, user_id: int) -> None:
        await cache.delete("user", str(user_id))

    @staticmethod
    def _user_to_dict(user: User) -> Dict:
        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code,
            "role": user.role.value,
            "is_active": user.is_active,
            "messages_count": user.messages_count,
            "ai_queries_count": user.ai_queries_count,
            "rating_points": user.rating_points,
            "premium_until": user.premium_until.isoformat() if user.premium_until else None,
            "referral_code": user.referral_code,
            "referred_by": user.referred_by,
            "created_at": user.created_at.isoformat(),
        }

    @staticmethod
    def _dict_to_user(data: Dict) -> User:
        """Reconstruct a lightweight User from cached dict (not ORM-managed)."""
        user = User()
        for key, value in data.items():
            if key == "role":
                user.role = UserRole(value)
            elif key in ("premium_until", "created_at") and value:
                setattr(user, key, datetime.fromisoformat(value))
            else:
                setattr(user, key, value)
        return user


# Singleton
user_service = UserService()
