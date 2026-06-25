"""
Celery Tasks — Background job definitions
"""
from __future__ import annotations

import asyncio
from typing import List

from celery import Celery
from celery.utils.log import get_task_logger

from core.config import settings

app = Celery(
    "it_pro_bot",
    broker=settings.rabbitmq.CELERY_BROKER_URL,
    backend=settings.rabbitmq.CELERY_RESULT_BACKEND,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "fetch-news-every-15min": {
            "task": "tasks.celery_tasks.task_fetch_news",
            "schedule": settings.scheduler.NEWS_UPDATE_INTERVAL * 60,
        },
        "fetch-github-every-hour": {
            "task": "tasks.celery_tasks.task_fetch_github",
            "schedule": settings.scheduler.GITHUB_UPDATE_INTERVAL * 60,
        },
    },
)

logger = get_task_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def task_fetch_news(self):
    """Celery task: fetch and persist news from all sources."""
    try:
        from scheduler.scheduler import job_fetch_and_store_news
        _run_async(job_fetch_and_store_news())
        logger.info("News fetch task completed")
    except Exception as exc:
        logger.error(f"News fetch task failed: {exc}")
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=3, default_retry_delay=120)
def task_fetch_github(self):
    """Celery task: fetch and persist GitHub trending repos."""
    try:
        from scheduler.scheduler import job_fetch_github_trending
        _run_async(job_fetch_github_trending())
        logger.info("GitHub fetch task completed")
    except Exception as exc:
        logger.error(f"GitHub fetch task failed: {exc}")
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=2)
def task_send_broadcast(self, message: str, user_ids: List[int]):
    """Celery task: send a broadcast message to a list of users."""
    try:
        import aiogram
        from core.config import settings

        async def _send():
            bot = aiogram.Bot(token=settings.bot.BOT_TOKEN)
            sent = 0
            for uid in user_ids:
                try:
                    await bot.send_message(uid, message, parse_mode="HTML")
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    pass
            await bot.session.close()
            return sent

        sent = _run_async(_send())
        logger.info(f"Broadcast sent to {sent}/{len(user_ids)} users")
        return {"sent": sent, "total": len(user_ids)}
    except Exception as exc:
        logger.error(f"Broadcast task failed: {exc}")
        raise self.retry(exc=exc)


# Export the celery app for use as `celery_app`
celery_app = app
