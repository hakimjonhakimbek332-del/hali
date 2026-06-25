"""
News Repository
Database operations for news items and GitHub repositories
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from database.models import (
    GithubRepository,
    NewsItem,
    NewsSource,
    SubscriptionCategory,
)

logger = get_logger(__name__)


class NewsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_news(
        self,
        title: str,
        url: str,
        source: NewsSource,
        category: SubscriptionCategory = SubscriptionCategory.ALL,
        summary: Optional[str] = None,
        score: int = 0,
        comment_count: int = 0,
        author: Optional[str] = None,
        image_url: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ) -> Optional[NewsItem]:
        # Avoid duplicates by URL
        exists = await self.session.execute(
            select(NewsItem).where(NewsItem.url == url)
        )
        if exists.scalar_one_or_none():
            return None

        item = NewsItem(
            title=title,
            url=url,
            source=source,
            category=category,
            summary=summary,
            score=score,
            comment_count=comment_count,
            author=author,
            image_url=image_url,
            published_at=published_at or datetime.utcnow(),
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_unsent(
        self,
        source: Optional[NewsSource] = None,
        category: Optional[SubscriptionCategory] = None,
        limit: int = 10,
    ) -> Sequence[NewsItem]:
        stmt = select(NewsItem).where(NewsItem.is_sent == False)  # noqa: E712
        if source:
            stmt = stmt.where(NewsItem.source == source)
        if category:
            stmt = stmt.where(NewsItem.category == category)
        stmt = stmt.order_by(NewsItem.score.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_sent(self, item_ids: List[int]) -> None:
        await self.session.execute(
            update(NewsItem)
            .where(NewsItem.id.in_(item_ids))
            .values(is_sent=True)
        )

    async def get_recent(
        self,
        hours: int = 24,
        category: Optional[SubscriptionCategory] = None,
        limit: int = 20,
    ) -> Sequence[NewsItem]:
        since = datetime.utcnow() - timedelta(hours=hours)
        stmt = (
            select(NewsItem)
            .where(NewsItem.created_at >= since)
        )
        if category:
            stmt = stmt.where(NewsItem.category == category)
        stmt = stmt.order_by(NewsItem.score.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def url_exists(self, url: str) -> bool:
        result = await self.session.execute(
            select(NewsItem.id).where(NewsItem.url == url)
        )
        return result.scalar_one_or_none() is not None


class GithubRepository_:
    """Repository for GitHub trending data (named with _ to avoid clash)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_or_update(
        self,
        full_name: str,
        name: str,
        owner: str,
        url: str,
        description: Optional[str] = None,
        language: Optional[str] = None,
        stars: int = 0,
        forks: int = 0,
        stars_today: int = 0,
        topics: Optional[str] = None,
    ) -> GithubRepository:
        result = await self.session.execute(
            select(GithubRepository).where(GithubRepository.full_name == full_name)
        )
        repo = result.scalar_one_or_none()
        if repo:
            repo.stars = stars
            repo.forks = forks
            repo.stars_today = stars_today
            repo.description = description
            repo.is_sent = False
        else:
            repo = GithubRepository(
                full_name=full_name,
                name=name,
                owner=owner,
                url=url,
                description=description,
                language=language,
                stars=stars,
                forks=forks,
                stars_today=stars_today,
                topics=topics,
            )
            self.session.add(repo)
        await self.session.flush()
        return repo

    async def get_unsent(self, limit: int = 5) -> Sequence[GithubRepository]:
        result = await self.session.execute(
            select(GithubRepository)
            .where(GithubRepository.is_sent == False)  # noqa: E712
            .order_by(GithubRepository.stars_today.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def mark_sent(self, repo_ids: List[int]) -> None:
        await self.session.execute(
            update(GithubRepository)
            .where(GithubRepository.id.in_(repo_ids))
            .values(is_sent=True)
        )

    async def get_by_language(self, language: str, limit: int = 10) -> Sequence[GithubRepository]:
        result = await self.session.execute(
            select(GithubRepository)
            .where(GithubRepository.language.ilike(language))
            .order_by(GithubRepository.stars.desc())
            .limit(limit)
        )
        return result.scalars().all()
