"""
News Scraping Service
Fetches IT news from HackerNews, Dev.to, Habr, GitHub Trending via RSS + HTTP
"""
from __future__ import annotations

import asyncio
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup

from core.config import settings
from core.logging import get_logger
from database.models import NewsSource, SubscriptionCategory
from database.redis_client import news_cache, github_cache

logger = get_logger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TelegramBot/1.0; "
        "+https://t.me/your_bot)"
    )
}


class NewsItem:
    __slots__ = (
        "title", "url", "summary", "source",
        "category", "score", "comment_count",
        "author", "image_url", "published_at",
    )

    def __init__(
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
    ) -> None:
        self.title = title
        self.url = url
        self.source = source
        self.category = category
        self.summary = summary
        self.score = score
        self.comment_count = comment_count
        self.author = author
        self.image_url = image_url
        self.published_at = published_at or datetime.utcnow()


class HackerNewsService:
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    ITEM_URL = "https://news.ycombinator.com/item?id="

    async def fetch_top_stories(
        self, session: aiohttp.ClientSession, limit: int = 20
    ) -> List[NewsItem]:
        """Fetch top stories from HN API."""
        cache_key = ("hn", "top_stories")
        cached = await news_cache.get(*cache_key)
        if cached:
            return [NewsItem(**item) for item in cached]

        try:
            async with session.get(f"{self.BASE_URL}/topstories.json") as resp:
                story_ids: List[int] = (await resp.json())[:limit]

            tasks = [self._fetch_item(session, sid) for sid in story_ids]
            items_raw = await asyncio.gather(*tasks, return_exceptions=True)

            news_items: List[NewsItem] = []
            for item in items_raw:
                if isinstance(item, Exception) or item is None:
                    continue
                if isinstance(item, dict):
                    news_item = self._to_news_item(item)
                    if news_item:
                        news_items.append(news_item)

            # Cache
            serialized = [
                {
                    "title": ni.title, "url": ni.url,
                    "source": ni.source.value, "category": ni.category.value,
                    "summary": ni.summary, "score": ni.score,
                    "comment_count": ni.comment_count, "author": ni.author,
                    "image_url": ni.image_url,
                    "published_at": ni.published_at.isoformat() if ni.published_at else None,
                }
                for ni in news_items
            ]
            await news_cache.set(*cache_key, value=serialized, ttl=900)
            return news_items
        except Exception as exc:
            logger.error("HackerNews fetch failed", error=str(exc))
            return []

    async def _fetch_item(
        self, session: aiohttp.ClientSession, item_id: int
    ) -> Optional[Dict]:
        try:
            async with session.get(f"{self.BASE_URL}/item/{item_id}.json") as resp:
                return await resp.json()
        except Exception:
            return None

    def _to_news_item(self, item: Dict) -> Optional[NewsItem]:
        if not item or item.get("type") != "story":
            return None
        url = item.get("url") or f"{self.ITEM_URL}{item.get('id', '')}"
        title = item.get("title", "")
        if not title or not url:
            return None

        category = self._detect_category(title)
        return NewsItem(
            title=title,
            url=url,
            source=NewsSource.HACKER_NEWS,
            category=category,
            score=item.get("score", 0),
            comment_count=item.get("descendants", 0),
            author=item.get("by"),
            published_at=datetime.fromtimestamp(item.get("time", 0))
            if item.get("time")
            else None,
        )

    @staticmethod
    def _detect_category(title: str) -> SubscriptionCategory:
        title_lower = title.lower()
        if any(k in title_lower for k in ["ai", "gpt", "llm", "machine learning", "neural"]):
            return SubscriptionCategory.AI
        if any(k in title_lower for k in ["python", "django", "fastapi", "flask"]):
            return SubscriptionCategory.PYTHON
        if any(k in title_lower for k in ["react", "vue", "css", "html", "frontend", "javascript"]):
            return SubscriptionCategory.FRONTEND
        if any(k in title_lower for k in ["backend", "api", "database", "postgres", "redis"]):
            return SubscriptionCategory.BACKEND
        if any(k in title_lower for k in ["security", "vulnerability", "cve", "hack", "exploit"]):
            return SubscriptionCategory.SECURITY
        if any(k in title_lower for k in ["docker", "kubernetes", "k8s", "devops", "ci/cd"]):
            return SubscriptionCategory.DEVOPS
        return SubscriptionCategory.ALL


class DevToService:
    BASE_URL = "https://dev.to/api"

    async def fetch_articles(
        self, session: aiohttp.ClientSession, tag: Optional[str] = None, limit: int = 10
    ) -> List[NewsItem]:
        params: Dict[str, Any] = {"per_page": limit, "top": 1}
        if tag:
            params["tag"] = tag

        try:
            async with session.get(f"{self.BASE_URL}/articles", params=params) as resp:
                articles = await resp.json()
        except Exception as exc:
            logger.error("Dev.to fetch failed", tag=tag, error=str(exc))
            return []

        items = []
        for article in articles:
            category = self._tag_to_category(article.get("tag_list", []))
            items.append(
                NewsItem(
                    title=article.get("title", ""),
                    url=article.get("url", ""),
                    source=NewsSource.DEV_TO,
                    category=category,
                    summary=article.get("description"),
                    score=article.get("public_reactions_count", 0),
                    comment_count=article.get("comments_count", 0),
                    author=article.get("user", {}).get("username"),
                    image_url=article.get("cover_image"),
                    published_at=datetime.fromisoformat(
                        article["published_at"].replace("Z", "+00:00")
                    )
                    if article.get("published_at")
                    else None,
                )
            )
        return items

    @staticmethod
    def _tag_to_category(tags: List[str]) -> SubscriptionCategory:
        tags_lower = [t.lower() for t in tags]
        if any(t in tags_lower for t in ["ai", "machinelearning", "deeplearning", "llm"]):
            return SubscriptionCategory.AI
        if any(t in tags_lower for t in ["python", "django", "fastapi"]):
            return SubscriptionCategory.PYTHON
        if any(t in tags_lower for t in ["javascript", "react", "vue", "css", "frontend"]):
            return SubscriptionCategory.FRONTEND
        if any(t in tags_lower for t in ["backend", "api", "database"]):
            return SubscriptionCategory.BACKEND
        if any(t in tags_lower for t in ["security", "cybersecurity"]):
            return SubscriptionCategory.SECURITY
        if any(t in tags_lower for t in ["devops", "docker", "kubernetes"]):
            return SubscriptionCategory.DEVOPS
        return SubscriptionCategory.ALL


class HabrService:
    RSS_URL = "https://habr.com/ru/rss/articles/top/?fl=ru"
    HUB_RSS = "https://habr.com/ru/rss/hub/{hub}/articles/?fl=ru"

    HUBS = {
        "python": SubscriptionCategory.PYTHON,
        "javascript": SubscriptionCategory.FRONTEND,
        "reactjs": SubscriptionCategory.FRONTEND,
        "nodejs": SubscriptionCategory.BACKEND,
        "machine_learning": SubscriptionCategory.AI,
        "artificial_intelligence": SubscriptionCategory.AI,
        "information_security": SubscriptionCategory.SECURITY,
        "devops": SubscriptionCategory.DEVOPS,
    }

    async def fetch_top(
        self, session: aiohttp.ClientSession, limit: int = 15
    ) -> List[NewsItem]:
        return await self._fetch_rss(session, self.RSS_URL, SubscriptionCategory.ALL, limit)

    async def fetch_by_hub(
        self, session: aiohttp.ClientSession, hub: str, limit: int = 10
    ) -> List[NewsItem]:
        url = self.HUB_RSS.format(hub=hub)
        category = self.HUBS.get(hub, SubscriptionCategory.ALL)
        return await self._fetch_rss(session, url, category, limit)

    async def fetch_all_hubs(
        self, session: aiohttp.ClientSession
    ) -> List[NewsItem]:
        tasks = [
            self.fetch_by_hub(session, hub)
            for hub in self.HUBS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        items: List[NewsItem] = []
        for result in results:
            if isinstance(result, list):
                items.extend(result)
        return items

    async def _fetch_rss(
        self,
        session: aiohttp.ClientSession,
        url: str,
        category: SubscriptionCategory,
        limit: int,
    ) -> List[NewsItem]:
        try:
            async with session.get(url) as resp:
                text = await resp.text()
        except Exception as exc:
            logger.error("Habr RSS fetch failed", url=url, error=str(exc))
            return []

        items: List[NewsItem] = []
        try:
            root = ET.fromstring(text)
            channel = root.find("channel")
            if channel is None:
                return []

            for entry in channel.findall("item")[:limit]:
                title_el = entry.find("title")
                link_el = entry.find("link")
                desc_el = entry.find("description")
                author_el = entry.find("{https://habr.com}author") or entry.find("author")
                pub_date_el = entry.find("pubDate")

                if title_el is None or link_el is None:
                    continue

                title = (title_el.text or "").strip()
                link = (link_el.text or "").strip()
                if not title or not link:
                    continue

                summary = None
                if desc_el is not None and desc_el.text:
                    soup = BeautifulSoup(desc_el.text, "html.parser")
                    summary = soup.get_text()[:500]

                pub_dt = None
                if pub_date_el is not None and pub_date_el.text:
                    try:
                        from email.utils import parsedate_to_datetime
                        pub_dt = parsedate_to_datetime(pub_date_el.text)
                    except Exception:
                        pass

                items.append(
                    NewsItem(
                        title=title,
                        url=link,
                        source=NewsSource.HABR,
                        category=category,
                        summary=summary,
                        author=author_el.text if author_el is not None else None,
                        published_at=pub_dt,
                    )
                )
        except ET.ParseError as exc:
            logger.error("Habr RSS parse error", error=str(exc))

        return items


class GitHubTrendingService:
    BASE_URL = "https://github.com/trending"

    async def fetch_trending(
        self,
        session: aiohttp.ClientSession,
        language: str = "",
        since: str = "daily",
    ) -> List[Dict]:
        """Scrape GitHub trending page."""
        cache_key = ("gh_trending", language or "all", since)
        cached = await github_cache.get(*cache_key)
        if cached:
            return cached

        url = self.BASE_URL
        params = {"since": since}
        if language:
            url = f"{self.BASE_URL}/{quote(language)}"

        try:
            async with session.get(url, params=params) as resp:
                html = await resp.text()
        except Exception as exc:
            logger.error("GitHub trending fetch failed", error=str(exc))
            return []

        repos = self._parse_trending(html)
        await github_cache.set(*cache_key, value=repos, ttl=3600)
        return repos

    def _parse_trending(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        repos = []

        for article in soup.select("article.Box-row"):
            try:
                h2 = article.select_one("h2")
                if not h2:
                    continue

                full_name_parts = [
                    a.text.strip() for a in h2.select("a span")
                    if a.text.strip()
                ]
                if len(full_name_parts) < 2:
                    link = h2.select_one("a")
                    if not link:
                        continue
                    href = link.get("href", "").strip("/")
                    parts = href.split("/")
                    if len(parts) < 2:
                        continue
                    owner, name = parts[0], parts[1]
                else:
                    owner = full_name_parts[0]
                    name = full_name_parts[-1]

                full_name = f"{owner}/{name}"
                url = f"https://github.com/{full_name}"

                desc_el = article.select_one("p")
                description = desc_el.text.strip() if desc_el else ""

                lang_el = article.select_one('[itemprop="programmingLanguage"]')
                language = lang_el.text.strip() if lang_el else ""

                stars_el = article.select_one('a[href$="/stargazers"]')
                stars_text = stars_el.text.strip().replace(",", "") if stars_el else "0"
                try:
                    stars = int(stars_text.replace("k", "000").replace(".", ""))
                except ValueError:
                    stars = 0

                forks_el = article.select_one('a[href$="/forks"]')
                forks_text = forks_el.text.strip().replace(",", "") if forks_el else "0"
                try:
                    forks = int(forks_text)
                except ValueError:
                    forks = 0

                stars_today_el = article.select_one("span.d-inline-block.float-sm-right")
                stars_today = 0
                if stars_today_el:
                    import re
                    match = re.search(r"([\d,]+)", stars_today_el.text)
                    if match:
                        stars_today = int(match.group(1).replace(",", ""))

                topics_els = article.select("a.topic-tag")
                topics = json.dumps([t.text.strip() for t in topics_els])

                repos.append({
                    "full_name": full_name,
                    "name": name,
                    "owner": owner,
                    "url": url,
                    "description": description,
                    "language": language,
                    "stars": stars,
                    "forks": forks,
                    "stars_today": stars_today,
                    "topics": topics,
                })
            except Exception as exc:
                logger.debug("Error parsing repo", error=str(exc))
                continue

        return repos

    async def fetch_multiple_languages(
        self,
        session: aiohttp.ClientSession,
        languages: Optional[List[str]] = None,
    ) -> List[Dict]:
        if languages is None:
            languages = ["python", "javascript", "typescript", "go", "rust"]

        tasks = [
            self.fetch_trending(session, lang)
            for lang in [""] + languages
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        seen: set = set()
        all_repos: List[Dict] = []
        for result in results:
            if isinstance(result, list):
                for repo in result:
                    if repo["full_name"] not in seen:
                        seen.add(repo["full_name"])
                        all_repos.append(repo)
        return all_repos


class NewsAggregatorService:
    """Orchestrates all scrapers and saves results to the database."""

    def __init__(self) -> None:
        self.hn = HackerNewsService()
        self.devto = DevToService()
        self.habr = HabrService()
        self.github = GitHubTrendingService()

    async def fetch_all_news(self) -> List[NewsItem]:
        """Fetch from all sources concurrently."""
        async with aiohttp.ClientSession(
            timeout=TIMEOUT, headers=HEADERS
        ) as session:
            results = await asyncio.gather(
                self.hn.fetch_top_stories(session, limit=20),
                self.devto.fetch_articles(session, limit=15),
                self.habr.fetch_top(session, limit=15),
                self.habr.fetch_all_hubs(session),
                return_exceptions=True,
            )

        items: List[NewsItem] = []
        for result in results:
            if isinstance(result, list):
                items.extend(result)
        logger.info("News aggregation complete", total_items=len(items))
        return items

    async def fetch_github_trending(self) -> List[Dict]:
        """Fetch GitHub trending repos."""
        async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
            return await self.github.fetch_multiple_languages(session)


# Singletons
news_aggregator = NewsAggregatorService()
