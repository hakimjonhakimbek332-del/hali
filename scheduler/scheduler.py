"""
Scheduler — APScheduler async jobs
Periodic news, GitHub, and Habr fetching + broadcasting
"""
from __future__ import annotations

import asyncio
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.config import settings
from core.logging import get_logger
from database.connection import get_db_session
from database.models import NewsSource, SubscriptionCategory
from repositories.news_repository import GithubRepository_, NewsRepository
from services.news_service import news_aggregator

logger = get_logger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


async def job_fetch_and_store_news() -> None:
    """Fetch all news sources and persist new items to DB."""
    logger.info("Scheduler: fetching news")
    try:
        items = await news_aggregator.fetch_all_news()
        async with get_db_session() as session:
            repo = NewsRepository(session)
            saved = 0
            for item in items:
                result = await repo.add_news(
                    title=item.title,
                    url=item.url,
                    source=item.source,
                    category=item.category,
                    summary=item.summary,
                    score=item.score,
                    comment_count=item.comment_count,
                    author=item.author,
                    image_url=item.image_url,
                    published_at=item.published_at,
                )
                if result:
                    saved += 1
        logger.info("News fetch complete", saved=saved, total=len(items))
    except Exception as exc:
        logger.error("News fetch job failed", error=str(exc))


async def job_fetch_github_trending() -> None:
    """Fetch GitHub trending repos and persist."""
    logger.info("Scheduler: fetching GitHub trending")
    try:
        repos = await news_aggregator.fetch_github_trending()
        async with get_db_session() as session:
            repo_db = GithubRepository_(session)
            for r in repos:
                await repo_db.add_or_update(
                    full_name=r["full_name"],
                    name=r["name"],
                    owner=r["owner"],
                    url=r["url"],
                    description=r.get("description"),
                    language=r.get("language"),
                    stars=r.get("stars", 0),
                    forks=r.get("forks", 0),
                    stars_today=r.get("stars_today", 0),
                    topics=r.get("topics"),
                )
        logger.info("GitHub trending fetch complete", repos=len(repos))
    except Exception as exc:
        logger.error("GitHub trending job failed", error=str(exc))


async def job_broadcast_news(bot) -> None:
    """Broadcast unsent news items to subscribed users."""
    logger.info("Scheduler: broadcasting news")
    try:
        async with get_db_session() as session:
            repo = NewsRepository(session)
            items = await repo.get_unsent(limit=5)
            if not items:
                return

            from repositories.user_repository import UserRepository

            user_repo = UserRepository(session)
            sent_ids = []

            for item in items:
                # Get users subscribed to this category (or ALL)
                subscribers = list(await user_repo.get_subscribed_users(item.category))
                all_subs = list(await user_repo.get_subscribed_users(SubscriptionCategory.ALL))
                recipients = list(set(subscribers + all_subs))

                if not recipients:
                    sent_ids.append(item.id)
                    continue

                source_icons = {
                    NewsSource.HACKER_NEWS: "🔶 Hacker News",
                    NewsSource.DEV_TO: "💻 Dev.to",
                    NewsSource.HABR: "📚 Habr",
                    NewsSource.GITHUB_TRENDING: "🐙 GitHub",
                }
                source_label = source_icons.get(item.source, "📰")
                text = (
                    f"{source_label}\n\n"
                    f"<b>{item.title}</b>\n"
                )
                if item.summary:
                    text += f"\n{item.summary[:200]}...\n"
                text += f"\n🔗 <a href='{item.url}'>O'qish</a>"

                delivered = 0
                for uid in recipients[:200]:  # max 200 per item
                    try:
                        await bot.send_message(uid, text, parse_mode="HTML",
                                               disable_web_page_preview=False)
                        delivered += 1
                        await asyncio.sleep(0.05)  # ~20 msg/sec, stay under TG limit
                    except Exception:
                        pass

                sent_ids.append(item.id)
                logger.info("News broadcast", item_id=item.id, delivered=delivered)

            if sent_ids:
                await repo.mark_sent(sent_ids)

    except Exception as exc:
        logger.error("Broadcast job failed", error=str(exc))


def create_scheduler(bot) -> AsyncIOScheduler:
    """Build and return the scheduler (not yet started)."""
    global _scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        job_fetch_and_store_news,
        trigger=IntervalTrigger(minutes=settings.scheduler.NEWS_UPDATE_INTERVAL),
        id="fetch_news",
        replace_existing=True,
        misfire_grace_time=60,
    )

    scheduler.add_job(
        job_fetch_github_trending,
        trigger=IntervalTrigger(minutes=settings.scheduler.GITHUB_UPDATE_INTERVAL),
        id="fetch_github",
        replace_existing=True,
        misfire_grace_time=120,
    )

    scheduler.add_job(
        job_broadcast_news,
        args=[bot],
        trigger=IntervalTrigger(minutes=settings.scheduler.NEWS_UPDATE_INTERVAL + 5),
        id="broadcast_news",
        replace_existing=True,
        misfire_grace_time=60,
    )

    _scheduler = scheduler
    return scheduler


def get_scheduler() -> Optional[AsyncIOScheduler]:
    return _scheduler
