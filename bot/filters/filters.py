"""
Custom Aiogram Filters
Admin check, premium check, and more
"""
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery, TelegramObject

from core.config import settings
from database.models import User, UserRole


class AdminFilter(BaseFilter):
    """Passes only messages/callbacks from admin users."""

    async def __call__(self, event: TelegramObject, db_user: User | None = None) -> bool:
        if db_user is None:
            return False
        if db_user.role == UserRole.ADMIN:
            return True
        # Also check hardcoded admin IDs from config
        return db_user.id in settings.security.admin_ids_list


class PremiumFilter(BaseFilter):
    """Passes only messages from premium (or admin) users."""

    async def __call__(self, event: TelegramObject, db_user: User | None = None) -> bool:
        if db_user is None:
            return False
        return db_user.is_premium or db_user.is_admin


class ActiveUserFilter(BaseFilter):
    """Passes only non-banned active users."""

    async def __call__(self, event: TelegramObject, db_user: User | None = None) -> bool:
        if db_user is None:
            return False
        return db_user.role != UserRole.BANNED and db_user.is_active


class PrivateChatFilter(BaseFilter):
    """Passes only private chats (not groups or channels)."""

    async def __call__(self, event: Message) -> bool:
        return event.chat.type == "private"
