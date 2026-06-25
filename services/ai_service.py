"""
AI Service — OpenAI GPT Integration
Streaming, context management, code analysis, and more
"""
from __future__ import annotations

import re
from typing import Any, AsyncGenerator, Dict, List, Optional

import openai
from openai import AsyncOpenAI

from core.config import settings
from core.exceptions import OpenAIException, PremiumRequiredException, RateLimitException
from core.logging import get_logger
from database.models import AIMessageRole
from database.redis_client import cache

logger = get_logger(__name__)

SYSTEM_PROMPTS: Dict[str, str] = {
    "default": """Sen professional IT dasturlash yordamchisisan. O'zbek, Rus va Ingliz tillarida javob bera olasan.

Imkoniyatlaring:
- Kod yozish va tahlil qilish (Python, JS, TS, React, Vue, Go, Rust, Java, C++, C# va boshqalar)
- Xatolarni topish va tuzatish (debugging)
- Refactoring va optimizatsiya
- SQL so'rovlar yozish
- API dizayni va implementatsiyasi
- Arxitektura maslahatlar
- Algoritmlar va ma'lumotlar tuzilmalari
- DevOps va Docker/Kubernetes
- Security best practices

Qoidalar:
- Kodlarni ```language ... ``` formatida yoz
- Har doim misollar keltir
- Murakkab tushunchalarni sodda tilda tushuntir
- Production-ready kod yaz
- SOLID, DRY, KISS prinsiplariga amal qil""",

    "code_review": """Sen senior software engineer sifatida kod review qilasan.
Quyidagilarni tekshir:
1. Xatolar va buglar
2. Security zaifliklar
3. Performance muammolar
4. Code style va naming
5. SOLID tamoyillariga muvofiqlik
6. Test coverage
7. Dokumentatsiya
Har bir muammoni aniq ko'rsat va yechim taklif qil.""",

    "sql": """Sen senior DBA (Database Administrator) sifatida SQL yordamini berasan.
PostgreSQL, MySQL, SQLite bo'yicha mutaxassissan.
Har doim:
- Optimallashtirilgan so'rovlar yoz
- Index strategiyasini tushuntir
- Query plan haqida ma'lumot ber
- N+1 muammodan qochinish yo'llarini ko'rsat""",

    "security": """Sen cybersecurity mutaxassisisan.
OWASP Top 10, CVE, penetration testing, secure coding bo'yicha yordam berasan.
Faqat qonuniy va etik maqsadlar uchun ma'lumot ber.""",
}


class AIService:
    def __init__(self) -> None:
        if not settings.openai.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured")
            self._client: Optional[AsyncOpenAI] = None
        else:
            self._client = AsyncOpenAI(
                api_key=settings.openai.OPENAI_API_KEY,
                timeout=settings.openai.OPENAI_TIMEOUT,
            )

    @property
    def client(self) -> AsyncOpenAI:
        if not self._client:
            raise OpenAIException("OpenAI API key is not configured.")
        return self._client

    async def check_rate_limit(self, user_id: int, is_premium: bool) -> None:
        """Raise RateLimitException if user exceeds AI rate limit."""
        limit = settings.security.AI_RATE_LIMIT_MESSAGES * (5 if is_premium else 1)
        allowed, remaining = await cache.check_rate_limit(
            user_id=user_id,
            action="ai_query",
            limit=limit,
            window=settings.security.AI_RATE_LIMIT_WINDOW,
        )
        if not allowed:
            raise RateLimitException(retry_after=settings.security.AI_RATE_LIMIT_WINDOW)

    async def chat(
        self,
        user_id: int,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        system_prompt_key: str = "default",
        is_premium: bool = False,
    ) -> str:
        """Send a message to GPT and return the full response."""
        await self.check_rate_limit(user_id, is_premium)

        system_prompt = SYSTEM_PROMPTS.get(system_prompt_key, SYSTEM_PROMPTS["default"])
        messages: List[Any] = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            for msg in conversation_history[-10:]:  # Keep last 10 turns for context
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model=settings.openai.OPENAI_MODEL,
                messages=messages,  # type: ignore
                max_tokens=settings.openai.OPENAI_MAX_TOKENS,
                temperature=settings.openai.OPENAI_TEMPERATURE,
            )
            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0
            logger.info("AI query completed", user_id=user_id, tokens=tokens_used)
            return content
        except openai.RateLimitError:
            raise OpenAIException("OpenAI rate limit reached. Please try again later.")
        except openai.APITimeoutError:
            raise OpenAIException("OpenAI request timed out. Please try again.")
        except openai.APIError as e:
            raise OpenAIException(str(e))

    async def stream_chat(
        self,
        user_id: int,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        system_prompt_key: str = "default",
        is_premium: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream GPT response token by token."""
        await self.check_rate_limit(user_id, is_premium)

        system_prompt = SYSTEM_PROMPTS.get(system_prompt_key, SYSTEM_PROMPTS["default"])
        messages: List[Any] = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": message})

        try:
            async with self.client.chat.completions.stream(
                model=settings.openai.OPENAI_MODEL,
                messages=messages,  # type: ignore
                max_tokens=settings.openai.OPENAI_MAX_TOKENS,
                temperature=settings.openai.OPENAI_TEMPERATURE,
            ) as stream:
                async for text in stream.text_stream:  # type: ignore
                    yield text
        except openai.APIError as e:
            raise OpenAIException(str(e))

    async def analyze_code(self, code: str, language: str, user_id: int) -> str:
        """Perform a detailed code review."""
        prompt = f"""Quyidagi {language} kodini professional code review qil:

```{language}
{code}
```

Quyidagilarni tahlil qil:
1. 🐛 Xatolar va buglar
2. 🔒 Security zaifliklar
3. ⚡ Performance muammolar
4. 📝 Code quality va naming
5. ✅ Yaxshi tomonlari
6. 💡 Yaxshilash takliflari

Har bir topilgan muammo uchun tuzatilgan kod ham keltir."""

        return await self.chat(
            user_id=user_id,
            message=prompt,
            system_prompt_key="code_review",
        )

    async def fix_code(self, code: str, error: str, language: str, user_id: int) -> str:
        """Fix a code error."""
        prompt = f"""Quyidagi {language} kodida xato bor. Xatoni tuzat va tushuntir:

**Kod:**
```{language}
{code}
```

**Xato:**
```
{error}
```

Xatoning sababini tushuntir va to'g'ri kodni yoz."""

        return await self.chat(user_id=user_id, message=prompt)

    async def generate_code(
        self,
        description: str,
        language: str,
        user_id: int,
        framework: Optional[str] = None,
    ) -> str:
        """Generate code from a description."""
        framework_text = f" ({framework} framework bilan)" if framework else ""
        prompt = f"""Quyidagi talabga mos {language}{framework_text} kodi yoz:

{description}

Talablar:
- Production-ready kod yaz
- Error handling qo'sh
- Dokumentatsiya yoz
- Type hints ishlatish (agar imkon bo'lsa)
- Best practices ga amal qil"""

        return await self.chat(user_id=user_id, message=prompt)

    async def explain_code(self, code: str, language: str, user_id: int) -> str:
        """Explain what a piece of code does."""
        prompt = f"""Quyidagi {language} kodini sodda tilda tushuntir:

```{language}
{code}
```

Quyidagilarni tushuntir:
1. Kod nima qiladi
2. Har bir funksiya/klass nima uchun
3. Algoritmning ishlash tartibi
4. Ishlatiladigan design patterns"""

        return await self.chat(user_id=user_id, message=prompt)

    async def optimize_code(self, code: str, language: str, user_id: int) -> str:
        """Optimize code for better performance."""
        prompt = f"""Quyidagi {language} kodini optimallashtir:

```{language}
{code}
```

Quyidagilarni yaxshila:
1. Time complexity
2. Space complexity
3. Keraksiz operatsiyalarni olib tashla
4. Caching imkoniyatlari
5. Parallel/async ishlov berish

Optimallashtirilgan kodni ham keltir va nima o'zgarganini tushuntir."""

        return await self.chat(user_id=user_id, message=prompt)

    @staticmethod
    def extract_code_blocks(text: str) -> List[Dict[str, str]]:
        """Extract all code blocks from a markdown-formatted response."""
        pattern = r"```(\w+)?\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        return [
            {"language": lang or "text", "code": code.strip()}
            for lang, code in matches
        ]

    async def generate_sql(
        self,
        description: str,
        schema: Optional[str],
        user_id: int,
        db_type: str = "PostgreSQL",
    ) -> str:
        """Generate SQL queries from a natural language description."""
        schema_text = f"\n\nDB Schema:\n```sql\n{schema}\n```" if schema else ""
        prompt = f"""Quyidagi talabga mos {db_type} SQL so'rovi yoz:{schema_text}

Talab: {description}

Quyidagilarni qo'sh:
1. To'liq va ishlaydigan SQL
2. Index tavsiyalari
3. Query optimization izohlar
4. Transactions (agar kerak bo'lsa)"""

        return await self.chat(
            user_id=user_id,
            message=prompt,
            system_prompt_key="sql",
        )


# Singleton
ai_service = AIService()
