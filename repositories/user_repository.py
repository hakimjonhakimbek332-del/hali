"""
User Repository
All user-related database operations following the Repository Pattern
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import DuplicateRecordException, UserNotFoundException
from core.logging import get_logger
from database.models import (
    SubscriptionCategory,
    User,
    UserRole,
    UserSubscription,
)

logger = get_logger(__name__)


def _generate_referral_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Create ─────────────────────────────────────────────────────────────────

    async def create(
        self,
        telegram_id: int,
        first_name: str,
        username: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: str = "uz",
        referred_by: Optional[int] = None,
        is_bot: bool = False,
    ) -> User:
        existing = await self.get_by_id(telegram_id)
        if existing:
            raise DuplicateRecordException("User", "telegram_id", telegram_id)

        referral_code = _generate_referral_code()
        # Ensure uniqueness
        while await self.get_by_referral_code(referral_code):
            referral_code = _generate_referral_code()

        user = User(
            id=telegram_id,
            first_name=first_name,
            username=username,
            last_name=last_name,
            language_code=language_code,
            referred_by=referred_by,
            referral_code=referral_code,
            is_bot=is_bot,
        )
        self.session.add(user)
        await self.session.flush()
        logger.info("User created", user_id=telegram_id, username=username)
        return user

    async def get_or_create(
        self,
        telegram_id: int,
        first_name: str,
        username: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: str = "uz",
        referred_by: Optional[int] = None,
    ) -> tuple[User, bool]:
        """Return (user, created). created=True if a new user was made."""
        user = await self.get_by_id(telegram_id)
        if user:
            # Update mutable fields
            user.first_name = first_name
            user.username = username
            user.last_name = last_name
            await self.session.flush()
            return user, False

        user = await self.create(
            telegram_id=telegram_id,
            first_name=first_name,
            username=username,
            last_name=last_name,
            language_code=language_code,
            referred_by=referred_by,
        )
        return user, True

    # ── Read ───────────────────────────────────────────────────────────────────

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(selectinload(User.subscriptions))
        )
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, user_id: int) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(user_id)
        return user

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(
                func.lower(User.username) == username.lower().lstrip("@"),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.referral_code == code.upper())
        )
        return result.scalar_one_or_none()

    async def get_all_active(self, skip: int = 0, limit: int = 100) -> Sequence[User]:
        result = await self.session.execute(
            select(User)
            .where(User.is_active == True, User.deleted_at.is_(None))  # noqa: E712
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_role(self, role: UserRole) -> Sequence[User]:
        result = await self.session.execute(
            select(User).where(User.role == role, User.deleted_at.is_(None))
        )
        return result.scalars().all()

    async def get_admins(self) -> Sequence[User]:
        return await self.get_by_role(UserRole.ADMIN)

    async def count_total(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(User).where(User.deleted_at.is_(None))
        )
        return result.scalar_one()

    async def count_active_today(self) -> int:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count())
            .select_from(User)
            .where(User.updated_at >= today, User.deleted_at.is_(None))
        )
        return result.scalar_one()

    async def count_new_today(self) -> int:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count())
            .select_from(User)
            .where(User.created_at >= today)
        )
        return result.scalar_one()

    # ── Update ─────────────────────────────────────────────────────────────────

    async def update_role(self, user_id: int, role: UserRole) -> User:
        user = await self.get_by_id_or_raise(user_id)
        user.role = role
        await self.session.flush()
        logger.info("User role updated", user_id=user_id, role=role)
        return user

    async def set_premium(self, user_id: int, days: int) -> User:
        user = await self.get_by_id_or_raise(user_id)
        base = user.premium_until or datetime.utcnow()
        user.premium_until = base + timedelta(days=days)
        user.role = UserRole.PREMIUM
        await self.session.flush()
        logger.info("Premium set", user_id=user_id, days=days, until=user.premium_until)
        return user

    async def ban(self, user_id: int) -> User:
        return await self.update_role(user_id, UserRole.BANNED)

    async def unban(self, user_id: int) -> User:
        return await self.update_role(user_id, UserRole.USER)

    async def increment_messages(self, user_id: int) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(messages_count=User.messages_count + 1)
        )

    async def increment_ai_queries(self, user_id: int) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(ai_queries_count=User.ai_queries_count + 1)
        )

    async def add_rating(self, user_id: int, points: int) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(rating_points=User.rating_points + points)
        )

    async def get_leaderboard(self, limit: int = 10) -> Sequence[User]:
        result = await self.session.execute(
            select(User)
            .where(User.deleted_at.is_(None))
            .order_by(User.rating_points.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # ── Subscriptions ──────────────────────────────────────────────────────────

    async def subscribe(
        self, user_id: int, category: SubscriptionCategory
    ) -> UserSubscription:
        result = await self.session.execute(
            select(UserSubscription).where(
                UserSubscription.user_id == user_id,
                UserSubscription.category == category,
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.is_active = True
        else:
            sub = UserSubscription(user_id=user_id, category=category, is_active=True)
            self.session.add(sub)
        await self.session.flush()
        return sub

    async def unsubscribe(self, user_id: int, category: SubscriptionCategory) -> None:
        result = await self.session.execute(
            select(UserSubscription).where(
                UserSubscription.user_id == user_id,
                UserSubscription.category == category,
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.is_active = False
            await self.session.flush()

    async def get_subscriptions(self, user_id: int) -> List[SubscriptionCategory]:
        result = await self.session.execute(
            select(UserSubscription.category).where(
                UserSubscription.user_id == user_id,
                UserSubscription.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def get_subscribed_users(
        self, category: SubscriptionCategory
    ) -> Sequence[int]:
        """Return list of user IDs subscribed to the given category."""
        result = await self.session.execute(
            select(UserSubscription.user_id)
            .join(User, User.id == UserSubscription.user_id)
            .where(
                UserSubscription.category == category,
                UserSubscription.is_active == True,  # noqa: E712
                User.is_active == True,  # noqa: E712
                User.deleted_at.is_(None),
            )
        )
        return result.scalars().all()
