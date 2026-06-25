"""
Telegram Keyboards
All inline and reply keyboards for the bot
"""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from database.models import SubscriptionCategory


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🤖 AI Yordam"),
        KeyboardButton(text="📰 Yangiliklar"),
    )
    builder.row(
        KeyboardButton(text="🐙 GitHub Trending"),
        KeyboardButton(text="📚 Habr"),
    )
    builder.row(
        KeyboardButton(text="👤 Profilim"),
        KeyboardButton(text="⚙️ Sozlamalar"),
    )
    builder.row(
        KeyboardButton(text="💡 Yordam"),
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def ai_actions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💬 Savol Berish", callback_data="ai:chat"),
        InlineKeyboardButton(text="🔍 Kod Tahlil", callback_data="ai:review"),
    )
    builder.row(
        InlineKeyboardButton(text="🐛 Xato Tuzatish", callback_data="ai:fix"),
        InlineKeyboardButton(text="✍️ Kod Yozish", callback_data="ai:generate"),
    )
    builder.row(
        InlineKeyboardButton(text="📖 Kod Tushuntirish", callback_data="ai:explain"),
        InlineKeyboardButton(text="⚡ Optimizatsiya", callback_data="ai:optimize"),
    )
    builder.row(
        InlineKeyboardButton(text="🗄️ SQL Yozish", callback_data="ai:sql"),
        InlineKeyboardButton(text="🔒 Security", callback_data="ai:security"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Bosh Menu", callback_data="main:menu"),
    )
    return builder.as_markup()


def news_categories_keyboard(
    current_subs: list[SubscriptionCategory] | None = None,
) -> InlineKeyboardMarkup:
    current_subs = current_subs or []
    builder = InlineKeyboardBuilder()

    categories = [
        ("🤖 AI", SubscriptionCategory.AI),
        ("🐍 Python", SubscriptionCategory.PYTHON),
        ("🎨 Frontend", SubscriptionCategory.FRONTEND),
        ("⚙️ Backend", SubscriptionCategory.BACKEND),
        ("🔒 Security", SubscriptionCategory.SECURITY),
        ("🐳 DevOps", SubscriptionCategory.DEVOPS),
        ("🐙 GitHub", SubscriptionCategory.GITHUB),
        ("📚 Habr", SubscriptionCategory.HABR),
    ]

    for label, cat in categories:
        tick = "✅ " if cat in current_subs else ""
        builder.button(
            text=f"{tick}{label}",
            callback_data=f"news:sub:{cat.value}",
        )

    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="📰 So'nggi Yangiliklar", callback_data="news:latest"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Bosh Menu", callback_data="main:menu"),
    )
    return builder.as_markup()


def github_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🌟 Bugungi Trend", callback_data="github:daily"),
        InlineKeyboardButton(text="📅 Haftalik Trend", callback_data="github:weekly"),
    )
    builder.row(
        InlineKeyboardButton(text="🐍 Python", callback_data="github:lang:python"),
        InlineKeyboardButton(text="⚡ JavaScript", callback_data="github:lang:javascript"),
    )
    builder.row(
        InlineKeyboardButton(text="🦀 Rust", callback_data="github:lang:rust"),
        InlineKeyboardButton(text="🐹 Go", callback_data="github:lang:go"),
    )
    builder.row(
        InlineKeyboardButton(text="📘 TypeScript", callback_data="github:lang:typescript"),
        InlineKeyboardButton(text="☕ Java", callback_data="github:lang:java"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="github:refresh"),
        InlineKeyboardButton(text="🏠 Menu", callback_data="main:menu"),
    )
    return builder.as_markup()


def profile_keyboard(is_premium: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="profile:stats"),
        InlineKeyboardButton(text="🔔 Obunalar", callback_data="profile:subscriptions"),
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Reyting", callback_data="profile:leaderboard"),
        InlineKeyboardButton(text="👥 Referral", callback_data="profile:referral"),
    )
    if not is_premium:
        builder.row(
            InlineKeyboardButton(text="⭐ Premium Olish", callback_data="premium:info"),
        )
    builder.row(
        InlineKeyboardButton(text="🏠 Bosh Menu", callback_data="main:menu"),
    )
    return builder.as_markup()


def settings_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🇺🇿 O'zbekcha" if lang == "uz" else "O'zbekcha",
            callback_data="settings:lang:uz",
        ),
        InlineKeyboardButton(
            text="🇷🇺 Русский" if lang == "ru" else "Русский",
            callback_data="settings:lang:ru",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🇬🇧 English" if lang == "en" else "English",
            callback_data="settings:lang:en",
        ),
    )
    builder.row(
        InlineKeyboardButton(text="🔔 Bildirishnomalar", callback_data="settings:notifications"),
        InlineKeyboardButton(text="🗑️ Sessiyani Tozalash", callback_data="settings:clear_session"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Bosh Menu", callback_data="main:menu"),
    )
    return builder.as_markup()


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats"),
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin:users"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Broadcast", callback_data="admin:broadcast"),
        InlineKeyboardButton(text="📝 Loglar", callback_data="admin:logs"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings"),
        InlineKeyboardButton(text="🔄 Scheduler", callback_data="admin:scheduler"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Bosh Menu", callback_data="main:menu"),
    )
    return builder.as_markup()


def confirmation_keyboard(action: str, item_id: str = "") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm:{action}:{item_id}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm:cancel"),
    )
    return builder.as_markup()


def back_keyboard(callback_data: str = "main:menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Orqaga", callback_data=callback_data),
    )
    return builder.as_markup()


def pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = []
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"{prefix}:page:{current_page - 1}")
        )
    buttons.append(
        InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="noop")
    )
    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"{prefix}:page:{current_page + 1}")
        )
    builder.row(*buttons)
    return builder.as_markup()


def premium_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐ 1 Oy — $9.99", callback_data="premium:buy:30"),
        InlineKeyboardButton(text="💎 3 Oy — $24.99", callback_data="premium:buy:90"),
    )
    builder.row(
        InlineKeyboardButton(text="👑 1 Yil — $79.99", callback_data="premium:buy:365"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Orqaga", callback_data="profile:menu"),
    )
    return builder.as_markup()


def habr_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔥 Top Maqolalar", callback_data="habr:top"),
        InlineKeyboardButton(text="🆕 Yangi", callback_data="habr:new"),
    )
    builder.row(
        InlineKeyboardButton(text="🐍 Python", callback_data="habr:hub:python"),
        InlineKeyboardButton(text="⚡ JavaScript", callback_data="habr:hub:javascript"),
    )
    builder.row(
        InlineKeyboardButton(text="🤖 AI/ML", callback_data="habr:hub:machine_learning"),
        InlineKeyboardButton(text="🔒 Security", callback_data="habr:hub:information_security"),
    )
    builder.row(
        InlineKeyboardButton(text="🐳 DevOps", callback_data="habr:hub:devops"),
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="habr:refresh"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Menu", callback_data="main:menu"),
    )
    return builder.as_markup()
