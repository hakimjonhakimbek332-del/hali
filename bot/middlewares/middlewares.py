"""
Bot Middlewares
Authentication, rate limiting, logging, user injection, and anti-flood
"""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update, User

from core.config import settings
from core.exceptions import RateLimitException, UserBannedException
from core.logging import get_logger
from database.redis_client import cache
from services.user_service import user_service

logger = get_logger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """
    Injects user object into handler data.
    Also handles new user registration transparently.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: User | None = data.get("event_from_user")

        if tg_user and not tg_user.is_bot:
            try:
                referral_code: str | None = None

                # Extract referral code from /start payload
                if isinstance(event, Message) and event.text:
                    text = event.text.strip()
                    if text.startswith("/start "):
                        payload = text.split(" ", 1)[1].strip()
                        if payload.startswith("ref_"):
                            referral_code = payload[4:].upper()

                user, is_new = await user_service.register_or_update(
                    tg_user, referral_code=referral_code
                )
                data["db_user"] = user
                data["is_new_user"] = is_new
            except Exception as exc:
                logger.error(
                    "DatabaseMiddleware user load failed",
                    user_id=tg_user.id,
                    error=str(exc),
                )
                data["db_user"] = None
                data["is_new_user"] = False

        return await handler(event, data)


class BanCheckMiddleware(BaseMiddleware):
    """Silently drop messages from banned users."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        db_user = data.get("db_user")
        if db_user:
            from database.models import UserRole
            if db_user.role == UserRole.BANNED:
                logger.warning("Banned user attempted action", user_id=db_user.id)
                if isinstance(event, Message):
                    await event.answer(
                        "❌ Sizning hisobingiz bloklangan. Murojaat uchun: @support"
                    )
                return  # Drop silently
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """Sliding-window rate limiter per user."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: User | None = data.get("event_from_user")
        if not tg_user:
            return await handler(event, data)

        db_user = data.get("db_user")
        from database.models import UserRole
        is_admin = db_user and db_user.role == UserRole.ADMIN

        # Admins bypass rate limiting
        if is_admin:
            return await handler(event, data)

        allowed, remaining = await cache.check_rate_limit(
            user_id=tg_user.id,
            action="message",
            limit=settings.security.RATE_LIMIT_MESSAGES,
            window=settings.security.RATE_LIMIT_WINDOW,
        )

        if not allowed:
            if isinstance(event, Message):
                await event.answer(
                    f"⏱ Juda ko'p xabar! "
                    f"{settings.security.RATE_LIMIT_WINDOW} soniya kuting.",
                    show_alert=False,
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⏱ Juda tez! Biroz kuting.", show_alert=True
                )
            logger.warning(
                "Rate limit exceeded",
                user_id=tg_user.id,
                remaining=remaining,
            )
            return  # Drop the request

        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Structured request logging with timing."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: User | None = data.get("event_from_user")
        start = time.perf_counter()

        event_type = type(event).__name__
        log_data: Dict[str, Any] = {
            "event_type": event_type,
            "user_id": tg_user.id if tg_user else None,
            "username": tg_user.username if tg_user else None,
        }

        if isinstance(event, Message):
            log_data["text"] = (event.text or "")[:100]
            if event.photo:
                log_data["has_photo"] = True
            if event.document:
                log_data["has_document"] = True
        elif isinstance(event, CallbackQuery):
            log_data["callback_data"] = event.data

        try:
            result = await handler(event, data)
            elapsed = (time.perf_counter() - start) * 1000
            log_data["duration_ms"] = round(elapsed, 2)
            logger.info("Request handled", **log_data)
            return result
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            log_data["duration_ms"] = round(elapsed, 2)
            log_data["error"] = str(exc)
            logger.error("Request failed", **log_data)
            raise


class MessageCountMiddleware(BaseMiddleware):
    """Increment user message counter in the background."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        result = await handler(event, data)
        tg_user: User | None = data.get("event_from_user")
        if tg_user and isinstance(event, Message):
            try:
                await user_service.increment_messages(tg_user.id)
            except Exception:
                pass  # Never fail a request over statistics
        return result
