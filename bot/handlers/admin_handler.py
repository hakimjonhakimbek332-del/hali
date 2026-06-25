"""
Admin Panel Handler
Statistics, broadcast, user management
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.filters.filters import AdminFilter
from bot.keyboards.keyboards import admin_panel_keyboard, back_keyboard, confirmation_keyboard
from core.config import settings
from core.logging import get_logger
from database.models import User
from services.user_service import user_service

router = Router(name="admin")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())
logger = get_logger(__name__)


class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_user_id = State()
    waiting_for_ban_id = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer(
        "👑 <b>Admin Panel</b>",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(call: CallbackQuery) -> None:
    stats = await user_service.get_stats()
    text = (
        "📊 <b>Bot Statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"✅ Bugun aktiv: <b>{stats['active_today']}</b>\n"
        f"🆕 Bugun yangi: <b>{stats['new_today']}</b>\n"
    )
    await call.message.edit_text(text, reply_markup=back_keyboard("admin:menu"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_for_broadcast)
    await call.message.edit_text(
        "📢 <b>Broadcast</b>\n\n"
        "Yubormoqchi bo'lgan xabarni yozing (HTML formatida):\n\n"
        "❌ Bekor: /cancel",
        parse_mode="HTML",
    )
    await call.answer()


@router.message(AdminStates.waiting_for_broadcast)
async def handle_broadcast_message(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("❌ Matn yuboring.")
        return

    await state.update_data(broadcast_text=message.text)
    await message.answer(
        f"📢 <b>Preview:</b>\n\n{message.text}\n\n"
        "Yuborishni tasdiqlaysizmi?",
        reply_markup=confirmation_keyboard("broadcast"),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm:broadcast:")
async def cb_confirm_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()

    if not text:
        await call.answer("❌ Xabar topilmadi.", show_alert=True)
        return

    await call.message.edit_text("📤 Broadcast boshlanmoqda...")

    from database.connection import get_db_session
    from repositories.user_repository import UserRepository

    async with get_db_session() as session:
        repo = UserRepository(session)
        users = await repo.get_all_active(limit=10000)

    sent = 0
    failed = 0
    bot = call.bot

    for user in users:
        try:
            await bot.send_message(user.id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await call.message.edit_text(
        f"✅ Broadcast tugadi!\n\n"
        f"✅ Yuborildi: <b>{sent}</b>\n"
        f"❌ Xato: <b>{failed}</b>",
        reply_markup=back_keyboard("admin:menu"),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm:cancel")
async def cb_cancel_confirmation(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.", reply_markup=admin_panel_keyboard())
    await call.answer()


@router.callback_query(F.data == "admin:users")
async def cb_admin_users(call: CallbackQuery) -> None:
    stats = await user_service.get_stats()
    leaders = await user_service.get_leaderboard(5)
    leader_lines = "\n".join(
        f"• {u.full_name} (@{u.username or 'N/A'}) — {u.rating_points} ball"
        for u in leaders
    )
    text = (
        f"👥 <b>Foydalanuvchilar</b>\n\n"
        f"Jami: <b>{stats['total_users']}</b>\n\n"
        f"🏆 Top 5:\n{leader_lines}"
    )
    await call.message.edit_text(text, reply_markup=back_keyboard("admin:menu"), parse_mode="HTML")
    await call.answer()


@router.message(Command("ban"))
async def cmd_ban(message: Message) -> None:
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Usage: /ban <user_id>")
        return
    try:
        uid = int(args[1])
        user = await user_service.ban_user(uid)
        await message.answer(f"✅ Foydalanuvchi {uid} bloklandi.")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")


@router.message(Command("unban"))
async def cmd_unban(message: Message) -> None:
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Usage: /unban <user_id>")
        return
    try:
        uid = int(args[1])
        user = await user_service.unban_user(uid)
        await message.answer(f"✅ Foydalanuvchi {uid} blokdan chiqarildi.")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")


@router.message(Command("premium"))
async def cmd_grant_premium(message: Message) -> None:
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Usage: /premium <user_id> <days>")
        return
    try:
        uid = int(args[1])
        days = int(args[2])
        user = await user_service.set_premium(uid, days)
        await message.answer(f"⭐ Foydalanuvchi {uid} ga {days} kunlik Premium berildi.")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")


@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "👑 <b>Admin Panel</b>",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()
