"""
Bot Entry Point
Registers routers, middlewares, and starts the bot
"""
from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot.filters.filters import PrivateChatFilter
from bot.handlers.admin_handler import router as admin_router
from bot.handlers.ai_handler import router as ai_router
from bot.handlers.news_handler import router as news_router
from bot.handlers.start_handler import router as start_router
from bot.middlewares.middlewares import (
    BanCheckMiddleware,
    DatabaseMiddleware,
    LoggingMiddleware,
    MessageCountMiddleware,
    RateLimitMiddleware,
)
from core.config import settings
from core.logging import get_logger, setup_logging
from database.connection import check_db_connection, close_engine
from database.redis_client import check_redis_connection, close_redis, get_redis_client
from scheduler.scheduler import create_scheduler

logger = get_logger(__name__)


async def set_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="ai", description="AI Yordamchi"),
        BotCommand(command="news", description="IT Yangiliklar"),
        BotCommand(command="github", description="GitHub Trending"),
        BotCommand(command="habr", description="Habr Maqolalari"),
        BotCommand(command="python", description="Python Yangiliklari"),
        BotCommand(command="frontend", description="Frontend Yangiliklari"),
        BotCommand(command="backend", description="Backend Yangiliklari"),
        BotCommand(command="ai_news", description="AI Yangiliklari"),
        BotCommand(command="security", description="Security Yangiliklari"),
        BotCommand(command="devops", description="DevOps Yangiliklari"),
        BotCommand(command="trending", description="Bugungi Trendlar"),
        BotCommand(command="profile", description="Mening Profilim"),
        BotCommand(command="settings", description="Sozlamalar"),
        BotCommand(command="cancel", description="Bekor Qilish"),
    ]
    await bot.set_my_commands(
        commands, scope=BotCommandScopeAllPrivateChats()
    )
    logger.info("Bot commands registered", count=len(commands))


async def run_migrations() -> None:
    """Run Alembic migrations in a subprocess so it doesn't block or hang."""
    process = await asyncio.create_subprocess_exec(
        "alembic", "upgrade", "head",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode == 0:
        logger.info("Database migrations applied")
    else:
        logger.error("Migration failed", stderr=stderr.decode())


def create_bot() -> Bot:
    return Bot(
        token=settings.bot.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=False,
        ),
    )


def create_dispatcher(bot: Bot) -> Dispatcher:
    redis_client = get_redis_client()
    storage = RedisStorage(redis=redis_client)
    dp = Dispatcher(storage=storage)

    # ── Global middlewares (order matters) ──────────────────────────────────
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())

    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())

    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    dp.message.middleware(MessageCountMiddleware())

    # ── Filters ──────────────────────────────────────────────────────────────
    # Restrict to private chats only (remove if group support is needed)
    # dp.message.filter(PrivateChatFilter())

    # ── Routers (order: specific → general) ─────────────────────────────────
    dp.include_router(admin_router)
    dp.include_router(ai_router)
    dp.include_router(news_router)
    dp.include_router(start_router)

    return dp


async def startup(bot: Bot, dp: Dispatcher) -> None:
    logger.info("Starting bot", version=settings.APP_VERSION, env=settings.ENVIRONMENT)

    # Health checks
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()

    if not db_ok:
        logger.error("Database is not reachable — aborting startup")
        sys.exit(1)
    if not redis_ok:
        logger.error("Redis is not reachable — aborting startup")
        sys.exit(1)

    logger.info("All dependencies healthy", db=db_ok, redis=redis_ok)

    # Migrations
    try:
        await run_migrations()
    except Exception as exc:
        logger.warning("Migration failed (may already be up to date)", error=str(exc))

    # Scheduler
    scheduler = create_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started")

    # Bot commands
    await set_bot_commands(bot)
    logger.info("Bot is ready!")


async def shutdown(bot: Bot) -> None:
    logger.info("Shutting down...")
    scheduler = __import__("scheduler.scheduler", fromlist=["get_scheduler"]).get_scheduler()
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    await close_engine()
    await close_redis()
    await bot.session.close()
    logger.info("Shutdown complete")


async def run_polling() -> None:
    """Run in long-polling mode."""
    bot = create_bot()
    dp = create_dispatcher(bot)

    await startup(bot, dp)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await shutdown(bot)


async def run_webhook() -> None:
    """Run in webhook mode using aiohttp."""
    bot = create_bot()
    dp = create_dispatcher(bot)

    await startup(bot, dp)

    webhook_url = f"{settings.bot.WEBHOOK_HOST}{settings.bot.WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )
    logger.info("Webhook set", url=webhook_url)

    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=settings.bot.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Health endpoint
    async def health(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "version": settings.APP_VERSION})

    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.bot.WEBHOOK_PORT)
    await site.start()
    logger.info("Webhook server started", port=settings.bot.WEBHOOK_PORT)

    # Keep running until signal
    stop_event = asyncio.Event()

    def _handle_stop():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_stop)

    await stop_event.wait()
    await runner.cleanup()
    await shutdown(bot)


def main() -> None:
    setup_logging()
    if settings.bot.USE_WEBHOOK:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
