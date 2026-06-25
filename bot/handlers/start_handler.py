"""
Core Handlers — /start, /help, /profile, /settings, callbacks
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.config import settings
from core.logging import get_logger
from database.models import SubscriptionCategory, User
from bot.keyboards.keyboards import (
    main_menu_keyboard,
    profile_keyboard,
    settings_keyboard,
    back_keyboard,
    news_categories_keyboard,
    premium_keyboard,
)
from services.user_service import user_service

router = Router(name="core")
logger = get_logger(__name__)


# ── /start ─────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User | None = None, is_new_user: bool = False) -> None:
    tg_user = message.from_user
    display_name = db_user.full_name if db_user else (tg_user.full_name if tg_user else "Foydalanuvchi")
    referral_code = db_user.referral_code if db_user else "—"

    if is_new_user:
        text = (
            f"👋 Salom, <b>{display_name}</b>!\n\n"
            "🤖 <b>IT Pro Bot</b> ga xush kelibsiz!\n\n"
            "Men sizga quyidagilarda yordam beraman:\n"
            "• 💻 Dasturlash bo'yicha AI yordamchi\n"
            "• 📰 Kunlik IT yangiliklar\n"
            "• 🐙 GitHub Trending repolar\n"
            "• 📚 Habr maqolalari\n"
            "• 🔒 Cybersecurity yangiliklari\n\n"
            f"🎁 Referral kodingiz: <code>ref_{referral_code}</code>\n"
            "Do'stlaringizni taklif qiling — har bir taklif uchun 7 kunlik Premium!\n\n"
            "Quyidagi menyudan boshlang 👇"
        )
    else:
        text = (
            f"👋 Qaytib keldingiz, <b>{display_name}</b>!\n\n"
            "Nima qilmoqchisiz? 👇"
        )

    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


# ── /help ──────────────────────────────────────────────────────────────────────

@router.message(Command("help"))
@router.message(F.text == "💡 Yordam")
async def cmd_help(message: Message) -> None:
    text = (
        "📖 <b>Buyruqlar ro'yxati:</b>\n\n"
        "<b>🤖 AI Yordamchi:</b>\n"
        "/ai — AI bilan suhbat\n\n"
        "<b>📰 Yangiliklar:</b>\n"
        "/news — Barcha yangiliklar\n"
        "/python — Python yangiliklari\n"
        "/frontend — Frontend yangiliklari\n"
        "/backend — Backend yangiliklari\n"
        "/ai_news — AI yangiliklari\n"
        "/security — Cybersecurity\n"
        "/devops — DevOps yangiliklari\n\n"
        "<b>🐙 GitHub:</b>\n"
        "/github — Trending repolar\n"
        "/trending — Bugungi trendlar\n\n"
        "<b>📚 Habr:</b>\n"
        "/habr — Habr maqolalari\n\n"
        "<b>👤 Profil:</b>\n"
        "/profile — Profilim\n"
        "/settings — Sozlamalar\n\n"
        "<b>🔍 Qidiruv:</b>\n"
        "/search [so'rov] — Yangilik qidirish\n\n"
        "🆘 Muammo bo'lsa: @support"
    )
    await message.answer(text, parse_mode="HTML")


# ── /profile ───────────────────────────────────────────────────────────────────

@router.message(Command("profile"))
@router.message(F.text == "👤 Profilim")
async def cmd_profile(message: Message, db_user: User | None = None) -> None:
    if not db_user:
        await message.answer("❌ Profil ma'lumotlari yuklanmadi. Iltimos, /start bosing.")
        return
    subs = await user_service.get_subscriptions(db_user.id)
    sub_icons = {
        SubscriptionCategory.ALL: "🌐",
        SubscriptionCategory.AI: "🤖",
        SubscriptionCategory.PYTHON: "🐍",
        SubscriptionCategory.FRONTEND: "🎨",
        SubscriptionCategory.BACKEND: "⚙️",
        SubscriptionCategory.SECURITY: "🔒",
        SubscriptionCategory.DEVOPS: "🐳",
        SubscriptionCategory.GITHUB: "🐙",
        SubscriptionCategory.HABR: "📚",
    }
    sub_text = " ".join(sub_icons.get(s, "•") for s in subs) if subs else "Yo'q"
    premium_status = (
        f"⭐ Premium — {db_user.premium_until.strftime('%d.%m.%Y')}"
        if db_user.is_premium and db_user.premium_until
        else ("👑 Admin" if db_user.is_admin else "👤 Oddiy")
    )

    text = (
        f"👤 <b>Profilim</b>\n\n"
        f"📛 Ism: <b>{db_user.full_name}</b>\n"
        f"🔖 Username: {'@' + db_user.username if db_user.username else 'Yo\'q'}\n"
        f"🆔 ID: <code>{db_user.id}</code>\n"
        f"🏅 Status: {premium_status}\n\n"
        f"📊 <b>Statistika:</b>\n"
        f"💬 Xabarlar: <b>{db_user.messages_count}</b>\n"
        f"🤖 AI so'rovlar: <b>{db_user.ai_queries_count}</b>\n"
        f"⭐ Reyting: <b>{db_user.rating_points}</b> ball\n\n"
        f"🔔 Obunalar: {sub_text}\n\n"
        f"👥 Referral: <code>ref_{db_user.referral_code}</code>\n"
        f"🗓 Ro'yxatdan o'tgan: <b>{db_user.created_at.strftime('%d.%m.%Y')}</b>"
    )
    await message.answer(
        text,
        reply_markup=profile_keyboard(is_premium=db_user.is_premium),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "profile:referral")
async def cb_referral(call: CallbackQuery, db_user: User) -> None:
    bot_username = settings.bot.BOT_USERNAME
    ref_link = f"https://t.me/{bot_username}?start=ref_{db_user.referral_code}"
    text = (
        f"👥 <b>Referral Tizimi</b>\n\n"
        f"Har bir yangi foydalanuvchi uchun <b>7 kunlik Premium</b> oling!\n\n"
        f"🔗 Sizning havolangiz:\n"
        f"<code>{ref_link}</code>\n\n"
        f"📋 Yoki kod:\n"
        f"<code>ref_{db_user.referral_code}</code>\n\n"
        f"📊 Taklif qilganlar soni: <b>{db_user.rating_points // 50}</b>"
    )
    await call.message.edit_text(text, reply_markup=back_keyboard("profile:menu"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "profile:leaderboard")
async def cb_leaderboard(call: CallbackQuery) -> None:
    leaders = await user_service.get_leaderboard(10)
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = []
    for i, user in enumerate(leaders):
        name = user.full_name[:20]
        lines.append(f"{medals[i]} <b>{name}</b> — {user.rating_points} ball")

    text = "🏆 <b>Reyting Jadvali</b>\n\n" + "\n".join(lines)
    await call.message.edit_text(text, reply_markup=back_keyboard("profile:menu"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "profile:subscriptions")
async def cb_subscriptions(call: CallbackQuery, db_user: User) -> None:
    subs = await user_service.get_subscriptions(db_user.id)
    await call.message.edit_text(
        "🔔 <b>Obunalar</b>\n\nQiziqtirgan kategoriyalarni tanlang:",
        reply_markup=news_categories_keyboard(subs),
        parse_mode="HTML",
    )
    await call.answer()


# ── /settings ─────────────────────────────────────────────────────────────────

@router.message(Command("settings"))
@router.message(F.text == "⚙️ Sozlamalar")
async def cmd_settings(message: Message, db_user: User | None = None) -> None:
    if not db_user:
        await message.answer("❌ Sozlamalar yuklanmadi. Iltimos, /start bosing.")
        return
    text = (
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"🌐 Til: <b>{db_user.language_code.upper()}</b>\n\n"
        "Tilni o'zgartirish uchun tugmani bosing:"
    )
    await message.answer(text, reply_markup=settings_keyboard(db_user.language_code), parse_mode="HTML")


@router.callback_query(F.data.startswith("settings:lang:"))
async def cb_set_language(call: CallbackQuery, db_user: User) -> None:
    lang = call.data.split(":")[-1]
    from database.connection import get_db_session
    from repositories.user_repository import UserRepository

    async with get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(db_user.id)
        if user:
            user.language_code = lang

    lang_names = {"uz": "O'zbekcha 🇺🇿", "ru": "Русский 🇷🇺", "en": "English 🇬🇧"}
    await call.answer(f"✅ Til o'zgartirildi: {lang_names.get(lang, lang)}", show_alert=True)
    await call.message.edit_reply_markup(reply_markup=settings_keyboard(lang))


@router.callback_query(F.data == "settings:clear_session")
async def cb_clear_session(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.answer("✅ Sessiya tozalandi!", show_alert=True)


# ── Premium ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "premium:info")
async def cb_premium_info(call: CallbackQuery) -> None:
    text = (
        "⭐ <b>Premium Obuna</b>\n\n"
        "Premium foydalanuvchilar uchun:\n"
        "• 🤖 GPT-4 bilan cheksiz suhbat\n"
        "• ⚡ 5x tezroq javoblar\n"
        "• 📊 Kengaytirilgan statistika\n"
        "• 🔔 Tezkor yangilik bildirishnomalari\n"
        "• 👑 Premium nishon\n\n"
        "💰 <b>Narxlar:</b>"
    )
    await call.message.edit_text(text, reply_markup=premium_keyboard(), parse_mode="HTML")
    await call.answer()


# ── Main menu callback ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "main:menu")
async def cb_main_menu(call: CallbackQuery, db_user: User) -> None:
    text = f"🏠 Bosh menuga qaytdingiz, <b>{db_user.full_name}</b>!"
    await call.message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await call.message.delete()
    await call.answer()
