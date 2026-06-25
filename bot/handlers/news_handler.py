"""
News Handler — IT news, GitHub, Habr
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from core.logging import get_logger
from database.models import SubscriptionCategory, User
from bot.keyboards.keyboards import (
    news_categories_keyboard,
    github_keyboard,
    habr_keyboard,
    back_keyboard,
)
from services.news_service import news_aggregator
from services.user_service import user_service

router = Router(name="news")
logger = get_logger(__name__)


def _format_news_item(item, idx: int) -> str:
    score_text = f"⭐ {item.score}" if item.score else ""
    comments_text = f"💬 {item.comment_count}" if item.comment_count else ""
    meta = " | ".join(filter(None, [score_text, comments_text]))
    return (
        f"{idx}. <a href='{item.url}'>{item.title[:80]}</a>\n"
        f"   {meta}"
    )


@router.message(Command("news"))
@router.message(F.text == "📰 Yangiliklar")
async def cmd_news(message: Message, db_user: User) -> None:
    subs = await user_service.get_subscriptions(db_user.id)
    await message.answer(
        "📰 <b>IT Yangiliklar</b>\n\nKategoriyani tanlang yoki obunalarni boshqaring:",
        reply_markup=news_categories_keyboard(subs),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "news:latest")
async def cb_news_latest(call: CallbackQuery) -> None:
    await call.answer("⏳ Yangiliklar yuklanmoqda...")
    msg = await call.message.edit_text("⏳ Yangiliklar olinmoqda...")

    try:
        items = await news_aggregator.fetch_all_news()
        if not items:
            await msg.edit_text("❌ Hozircha yangilik yo'q.", reply_markup=back_keyboard("news:menu"))
            return

        top_items = sorted(items, key=lambda x: x.score, reverse=True)[:10]
        lines = [f"📰 <b>So'nggi IT Yangiliklar</b>\n"]
        for i, item in enumerate(top_items, 1):
            lines.append(_format_news_item(item, i))

        await msg.edit_text(
            "\n".join(lines),
            reply_markup=back_keyboard("news:menu"),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error("News fetch error", error=str(e))
        await msg.edit_text("❌ Xato yuz berdi.", reply_markup=back_keyboard("news:menu"))


@router.callback_query(F.data.startswith("news:sub:"))
async def cb_toggle_subscription(call: CallbackQuery, db_user: User) -> None:
    cat_value = call.data.split(":")[-1]
    try:
        category = SubscriptionCategory(cat_value)
    except ValueError:
        await call.answer("❌ Noto'g'ri kategoriya", show_alert=True)
        return

    subs = await user_service.get_subscriptions(db_user.id)
    if category in subs:
        await user_service.unsubscribe(db_user.id, category)
        await call.answer(f"🔕 {category.value.title()} obunasidan chiqildi")
    else:
        await user_service.subscribe(db_user.id, category)
        await call.answer(f"🔔 {category.value.title()} ga obuna bo'lindi")

    new_subs = await user_service.get_subscriptions(db_user.id)
    await call.message.edit_reply_markup(reply_markup=news_categories_keyboard(new_subs))


# ── GitHub ─────────────────────────────────────────────────────────────────────

@router.message(Command("github"))
@router.message(F.text == "🐙 GitHub Trending")
async def cmd_github(message: Message) -> None:
    await message.answer(
        "🐙 <b>GitHub Trending</b>\n\nTil yoki period tanlang:",
        reply_markup=github_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "github:daily")
async def cb_github_daily(call: CallbackQuery) -> None:
    await _send_github_trending(call, since="daily")


@router.callback_query(F.data == "github:weekly")
async def cb_github_weekly(call: CallbackQuery) -> None:
    await _send_github_trending(call, since="weekly")


@router.callback_query(F.data.startswith("github:lang:"))
async def cb_github_language(call: CallbackQuery) -> None:
    language = call.data.split(":")[-1]
    await _send_github_trending(call, language=language)


async def _send_github_trending(
    call: CallbackQuery,
    language: str = "",
    since: str = "daily",
) -> None:
    import aiohttp
    from services.news_service import GitHubTrendingService, TIMEOUT, HEADERS

    await call.answer("⏳ GitHub trend yuklanmoqda...")
    msg = await call.message.edit_text("⏳ GitHub Trending olinmoqda...")

    try:
        svc = GitHubTrendingService()
        async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
            repos = await svc.fetch_trending(session, language=language, since=since)

        if not repos:
            await msg.edit_text("❌ Hozircha repo yo'q.", reply_markup=github_keyboard())
            return

        lang_label = language.capitalize() if language else "Barcha tillar"
        lines = [f"🐙 <b>GitHub Trending — {lang_label}</b>\n"]

        for i, repo in enumerate(repos[:8], 1):
            stars = f"⭐ {repo['stars']:,}"
            stars_today = f"+{repo['stars_today']}" if repo['stars_today'] else ""
            lang_badge = f"[{repo['language']}]" if repo['language'] else ""
            desc = (repo['description'] or "")[:60]
            lines.append(
                f"{i}. <a href='{repo['url']}'>{repo['full_name']}</a> {lang_badge}\n"
                f"   {stars} {stars_today} | {desc}"
            )

        await msg.edit_text(
            "\n".join(lines),
            reply_markup=github_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error("GitHub trending error", error=str(e))
        await msg.edit_text("❌ Xato yuz berdi.", reply_markup=github_keyboard())


@router.callback_query(F.data == "github:refresh")
async def cb_github_refresh(call: CallbackQuery) -> None:
    from database.redis_client import github_cache
    # Invalidate all github caches
    await call.answer("🔄 Yangilanmoqda...")
    await _send_github_trending(call)


# ── Habr ───────────────────────────────────────────────────────────────────────

@router.message(Command("habr"))
@router.message(F.text == "📚 Habr")
async def cmd_habr(message: Message) -> None:
    await message.answer(
        "📚 <b>Habr</b>\n\nKategoriyani tanlang:",
        reply_markup=habr_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "habr:top")
async def cb_habr_top(call: CallbackQuery) -> None:
    await _send_habr_articles(call)


@router.callback_query(F.data.startswith("habr:hub:"))
async def cb_habr_hub(call: CallbackQuery) -> None:
    hub = call.data.split(":")[-1]
    await _send_habr_articles(call, hub=hub)


async def _send_habr_articles(
    call: CallbackQuery, hub: str = ""
) -> None:
    import aiohttp
    from services.news_service import HabrService, TIMEOUT, HEADERS

    await call.answer("⏳ Habr yuklanmoqda...")
    msg = await call.message.edit_text("⏳ Habr maqolalari olinmoqda...")

    try:
        svc = HabrService()
        async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
            if hub:
                articles = await svc.fetch_by_hub(session, hub=hub)
            else:
                articles = await svc.fetch_top(session)

        if not articles:
            await msg.edit_text("❌ Hozircha maqola yo'q.", reply_markup=habr_keyboard())
            return

        hub_label = hub.replace("_", " ").title() if hub else "Top Maqolalar"
        lines = [f"📚 <b>Habr — {hub_label}</b>\n"]

        for i, article in enumerate(articles[:10], 1):
            author = f"✍️ {article.author}" if article.author else ""
            lines.append(
                f"{i}. <a href='{article.url}'>{article.title[:70]}</a>\n"
                f"   {author}"
            )

        await msg.edit_text(
            "\n".join(lines),
            reply_markup=habr_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error("Habr fetch error", error=str(e))
        await msg.edit_text("❌ Xato yuz berdi.", reply_markup=habr_keyboard())


# ── Category shortcuts ─────────────────────────────────────────────────────────

async def _send_category_news(message: Message, category: str) -> None:
    import aiohttp
    from services.news_service import DevToService, TIMEOUT, HEADERS

    msg = await message.answer(f"⏳ {category} yangiliklari olinmoqda...")
    try:
        svc = DevToService()
        async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
            articles = await svc.fetch_articles(session, tag=category, limit=10)

        if not articles:
            await msg.edit_text(f"❌ {category} bo'yicha yangilik topilmadi.")
            return

        lines = [f"📰 <b>{category.upper()} Yangiliklari</b>\n"]
        for i, a in enumerate(articles[:8], 1):
            lines.append(_format_news_item(a, i))

        await msg.edit_text(
            "\n".join(lines), parse_mode="HTML", disable_web_page_preview=True
        )
    except Exception as e:
        await msg.edit_text("❌ Xato yuz berdi.")


@router.message(Command("python"))
async def cmd_python(message: Message) -> None:
    await _send_category_news(message, "python")


@router.message(Command("frontend"))
async def cmd_frontend(message: Message) -> None:
    await _send_category_news(message, "webdev")


@router.message(Command("backend"))
async def cmd_backend(message: Message) -> None:
    await _send_category_news(message, "backend")


@router.message(Command("ai_news"))
async def cmd_ai_news(message: Message) -> None:
    await _send_category_news(message, "ai")


@router.message(Command("security"))
async def cmd_security(message: Message) -> None:
    await _send_category_news(message, "security")


@router.message(Command("devops"))
async def cmd_devops(message: Message) -> None:
    await _send_category_news(message, "devops")


@router.message(Command("trending"))
async def cmd_trending(message: Message) -> None:
    await message.answer(
        "🔥 <b>Bugungi Trendlar</b>",
        reply_markup=github_keyboard(),
        parse_mode="HTML",
    )
