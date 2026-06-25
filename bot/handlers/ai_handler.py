"""
AI Handler — GPT chat, code review, generation, analysis
Uses FSM for conversation state management
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.exceptions import OpenAIException, PremiumRequiredException, RateLimitException
from core.logging import get_logger
from database.models import User
from database.redis_client import cache
from bot.keyboards.keyboards import ai_actions_keyboard, back_keyboard
from services.ai_service import ai_service
from services.user_service import user_service

router = Router(name="ai")
logger = get_logger(__name__)

SESSION_TTL = 3600  # 1 hour


class AIStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_code = State()
    waiting_for_code_and_error = State()
    waiting_for_generate_description = State()
    waiting_for_sql_description = State()
    waiting_for_explain_code = State()
    waiting_for_optimize_code = State()


async def _get_history(user_id: int) -> List[Dict]:
    cached = await cache.get("ai_history", str(user_id))
    return cached if isinstance(cached, list) else []


async def _save_history(user_id: int, history: List[Dict]) -> None:
    await cache.set("ai_history", str(user_id), value=history[-20:], ttl=SESSION_TTL)


async def _append_to_history(user_id: int, role: str, content: str) -> List[Dict]:
    history = await _get_history(user_id)
    history.append({"role": role, "content": content})
    await _save_history(user_id, history)
    return history


def _truncate(text: str, max_len: int = 4000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n\n... (javob qisqartirildi)"


# ── Entry points ───────────────────────────────────────────────────────────────

@router.message(Command("ai"))
@router.message(F.text == "🤖 AI Yordam")
async def cmd_ai(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🤖 <b>AI Yordamchi</b>\n\nNima qilishni xohlaysiz?",
        reply_markup=ai_actions_keyboard(),
        parse_mode="HTML",
    )


# ── Callback actions ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "ai:chat")
async def cb_ai_chat(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AIStates.waiting_for_message)
    await call.message.edit_text(
        "💬 <b>AI Chat</b>\n\n"
        "Savolingizni yozing. Kontekst saqlanadi — davomli suhbat qilishingiz mumkin.\n\n"
        "❌ Bekor qilish: /cancel",
        reply_markup=None,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "ai:review")
async def cb_ai_review(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AIStates.waiting_for_code)
    await state.update_data(action="review")
    await call.message.edit_text(
        "🔍 <b>Kod Tahlil</b>\n\n"
        "Tahlil qilinishi kerak bo'lgan kodni yuboring.\n"
        "Format: ```language\\nkod\\n```\n\n"
        "❌ Bekor qilish: /cancel",
        reply_markup=None,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "ai:fix")
async def cb_ai_fix(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AIStates.waiting_for_code)
    await state.update_data(action="fix")
    await call.message.edit_text(
        "🐛 <b>Xato Tuzatish</b>\n\n"
        "Kod va xato xabarini yuboring:\n\n"
        "<code>```python\n# Sizning kodingiz\n```\n\nXato: error message here</code>\n\n"
        "❌ Bekor qilish: /cancel",
        reply_markup=None,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "ai:generate")
async def cb_ai_generate(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AIStates.waiting_for_generate_description)
    await call.message.edit_text(
        "✍️ <b>Kod Generatsiya</b>\n\n"
        "Qanday kod kerakligini tasvirlab bering:\n"
        "Misol: <i>FastAPI bilan foydalanuvchi auth tizimi, JWT, PostgreSQL</i>\n\n"
        "❌ Bekor qilish: /cancel",
        reply_markup=None,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "ai:explain")
async def cb_ai_explain(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AIStates.waiting_for_explain_code)
    await call.message.edit_text(
        "📖 <b>Kod Tushuntirish</b>\n\n"
        "Tushuntirish kerak bo'lgan kodni yuboring:\n\n"
        "❌ Bekor qilish: /cancel",
        reply_markup=None,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "ai:optimize")
async def cb_ai_optimize(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AIStates.waiting_for_optimize_code)
    await call.message.edit_text(
        "⚡ <b>Kod Optimizatsiya</b>\n\n"
        "Optimallashtirish kerak bo'lgan kodni yuboring:\n\n"
        "❌ Bekor qilish: /cancel",
        reply_markup=None,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "ai:sql")
async def cb_ai_sql(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AIStates.waiting_for_sql_description)
    await call.message.edit_text(
        "🗄️ <b>SQL Generatsiya</b>\n\n"
        "SQL so'rovi kerakligini tasvirlab bering.\n"
        "Schema ham qo'shishingiz mumkin:\n\n"
        "Misol: <i>users jadvalida 30 kundan beri faol bo'lmagan foydalanuvchilarni toping</i>\n\n"
        "❌ Bekor qilish: /cancel",
        reply_markup=None,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "ai:security")
async def cb_ai_security(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AIStates.waiting_for_message)
    await state.update_data(system_prompt="security")
    await call.message.edit_text(
        "🔒 <b>Security Mode</b>\n\n"
        "Security bo'yicha savolingizni yozing:\n"
        "• Kod xavfsizligi tahlili\n"
        "• Vulnerability qidirish\n"
        "• Secure coding amaliyotlari\n\n"
        "❌ Bekor qilish: /cancel",
        reply_markup=None,
        parse_mode="HTML",
    )
    await call.answer()


# ── State handlers ─────────────────────────────────────────────────────────────

@router.message(AIStates.waiting_for_message)
async def handle_ai_chat(message: Message, state: FSMContext, db_user: User) -> None:
    text = message.text or ""
    if not text.strip():
        await message.answer("❌ Iltimos, matn yuboring.")
        return

    data = await state.get_data()
    system_prompt_key = data.get("system_prompt", "default")

    thinking_msg = await message.answer("🤔 O'ylayapman...")

    try:
        history = await _get_history(message.from_user.id)
        response = await ai_service.chat(
            user_id=message.from_user.id,
            message=text,
            conversation_history=history,
            system_prompt_key=system_prompt_key,
            is_premium=db_user.is_premium,
        )

        await _append_to_history(message.from_user.id, "user", text)
        await _append_to_history(message.from_user.id, "assistant", response)
        await user_service.increment_ai_queries(message.from_user.id)

        await thinking_msg.delete()
        chunks = _split_response(response)
        for i, chunk in enumerate(chunks):
            kb = ai_actions_keyboard() if i == len(chunks) - 1 else None
            await message.answer(chunk, parse_mode="HTML", reply_markup=kb)

    except RateLimitException as e:
        await thinking_msg.edit_text(f"⏱ {e.message}")
    except OpenAIException as e:
        await thinking_msg.edit_text(f"❌ OpenAI xato: {e.message}")
    except Exception as e:
        logger.error("AI chat error", error=str(e))
        await thinking_msg.edit_text("❌ Kutilmagan xato yuz berdi. Qaytadan urinib ko'ring.")


@router.message(AIStates.waiting_for_code)
async def handle_code_action(message: Message, state: FSMContext, db_user: User) -> None:
    text = message.text or ""
    data = await state.get_data()
    action = data.get("action", "review")

    language, code = _extract_code(text)
    if not code:
        code = text
        language = "python"

    thinking_msg = await message.answer("🔍 Tahlil qilinmoqda...")

    try:
        if action == "review":
            response = await ai_service.analyze_code(code, language, message.from_user.id)
        elif action == "fix":
            error_part = _extract_error(text)
            response = await ai_service.fix_code(code, error_part, language, message.from_user.id)
        else:
            response = await ai_service.analyze_code(code, language, message.from_user.id)

        await user_service.increment_ai_queries(message.from_user.id)
        await thinking_msg.delete()
        chunks = _split_response(response)
        for i, chunk in enumerate(chunks):
            kb = ai_actions_keyboard() if i == len(chunks) - 1 else None
            await message.answer(chunk, parse_mode="HTML", reply_markup=kb)

    except RateLimitException as e:
        await thinking_msg.edit_text(f"⏱ {e.message}")
    except OpenAIException as e:
        await thinking_msg.edit_text(f"❌ {e.message}")
    except Exception as e:
        logger.error("Code analysis error", error=str(e))
        await thinking_msg.edit_text("❌ Xato yuz berdi.")


@router.message(AIStates.waiting_for_generate_description)
async def handle_generate(message: Message, state: FSMContext, db_user: User) -> None:
    description = message.text or ""
    thinking_msg = await message.answer("✍️ Kod yozilmoqda...")

    try:
        # Try to detect language from description
        desc_lower = description.lower()
        language = "python"
        framework = None
        for lang in ["typescript", "javascript", "golang", "rust", "java", "python"]:
            if lang in desc_lower:
                language = lang
                break
        for fw in ["fastapi", "django", "react", "vue", "next.js", "nestjs", "spring"]:
            if fw in desc_lower:
                framework = fw
                break

        response = await ai_service.generate_code(
            description=description,
            language=language,
            user_id=message.from_user.id,
            framework=framework,
        )
        await user_service.increment_ai_queries(message.from_user.id)
        await thinking_msg.delete()
        chunks = _split_response(response)
        for i, chunk in enumerate(chunks):
            kb = ai_actions_keyboard() if i == len(chunks) - 1 else None
            await message.answer(chunk, parse_mode="HTML", reply_markup=kb)

    except (RateLimitException, OpenAIException) as e:
        await thinking_msg.edit_text(f"❌ {e.message}")
    except Exception as e:
        logger.error("Code generation error", error=str(e))
        await thinking_msg.edit_text("❌ Xato yuz berdi.")


@router.message(AIStates.waiting_for_explain_code)
async def handle_explain(message: Message, state: FSMContext, db_user: User) -> None:
    text = message.text or ""
    language, code = _extract_code(text)
    if not code:
        code = text
        language = "python"

    thinking_msg = await message.answer("📖 O'rganilmoqda...")
    try:
        response = await ai_service.explain_code(code, language, message.from_user.id)
        await user_service.increment_ai_queries(message.from_user.id)
        await thinking_msg.delete()
        chunks = _split_response(response)
        for i, chunk in enumerate(chunks):
            kb = ai_actions_keyboard() if i == len(chunks) - 1 else None
            await message.answer(chunk, parse_mode="HTML", reply_markup=kb)
    except (RateLimitException, OpenAIException) as e:
        await thinking_msg.edit_text(f"❌ {e.message}")


@router.message(AIStates.waiting_for_optimize_code)
async def handle_optimize(message: Message, state: FSMContext, db_user: User) -> None:
    text = message.text or ""
    language, code = _extract_code(text)
    if not code:
        code = text
        language = "python"

    thinking_msg = await message.answer("⚡ Optimizatsiya qilinmoqda...")
    try:
        response = await ai_service.optimize_code(code, language, message.from_user.id)
        await user_service.increment_ai_queries(message.from_user.id)
        await thinking_msg.delete()
        chunks = _split_response(response)
        for i, chunk in enumerate(chunks):
            kb = ai_actions_keyboard() if i == len(chunks) - 1 else None
            await message.answer(chunk, parse_mode="HTML", reply_markup=kb)
    except (RateLimitException, OpenAIException) as e:
        await thinking_msg.edit_text(f"❌ {e.message}")


@router.message(AIStates.waiting_for_sql_description)
async def handle_sql(message: Message, state: FSMContext, db_user: User) -> None:
    description = message.text or ""
    thinking_msg = await message.answer("🗄️ SQL yozilmoqda...")
    try:
        response = await ai_service.generate_sql(
            description=description,
            schema=None,
            user_id=message.from_user.id,
        )
        await user_service.increment_ai_queries(message.from_user.id)
        await thinking_msg.delete()
        chunks = _split_response(response)
        for i, chunk in enumerate(chunks):
            kb = ai_actions_keyboard() if i == len(chunks) - 1 else None
            await message.answer(chunk, parse_mode="HTML", reply_markup=kb)
    except (RateLimitException, OpenAIException) as e:
        await thinking_msg.edit_text(f"❌ {e.message}")


# ── /cancel ────────────────────────────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=ai_actions_keyboard())
    else:
        await message.answer("Bekor qiladigan narsa yo'q.")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_code(text: str) -> tuple[str, str]:
    """Extract language and code from a markdown code block."""
    import re
    match = re.search(r"```(\w+)?\n(.*?)```", text, re.DOTALL)
    if match:
        lang = match.group(1) or "python"
        code = match.group(2).strip()
        return lang, code
    return "python", ""


def _extract_error(text: str) -> str:
    """Extract error message from text after code block."""
    import re
    # Remove code block, take remaining text as error
    clean = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()
    return clean or "Unknown error"


def _split_response(text: str, max_len: int = 4000) -> List[str]:
    """Split long responses into Telegram-safe chunks."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
