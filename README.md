# 🤖 IT Pro Bot — Enterprise Telegram AI Assistant

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Redis](https://img.shields.io/badge/Redis-7-red)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![License](https://img.shields.io/badge/License-MIT-green)

Production-ready, enterprise-grade Telegram bot — shaxsiy AI dasturlash yordamchisi va IT yangiliklar agregatori.

---

## ✨ Imkoniyatlar

### 🤖 AI Yordamchi (GPT-4)
- Kod yozish, tahlil, tuzatish, optimizatsiya
- Kod tushuntirish va refactoring
- SQL generatsiya
- Security tahlil
- Davomli suhbat konteksti (Redis)

### 📰 IT Yangiliklar (har 15 daqiqada)
- Hacker News, Dev.to, Habr, GitHub Trending
- Kategoriyalar: AI, Python, Frontend, Backend, Security, DevOps
- Foydalanuvchi obuna tizimi

### 🐙 GitHub Trending
- Kunlik/haftalik trend repolar
- Til bo'yicha filtrlash
- Avtomatik broadcast

### 👤 Foydalanuvchi Tizimi
- Ro'yxatdan o'tish, profil
- Premium obuna
- Referral tizimi (7 kunlik bonus)
- Reyting tizimi

### 👑 Admin Panel
- Bot statistikasi
- Broadcast xabar
- Foydalanuvchi boshqaruvi (ban/unban/premium)

---

## 🏗️ Arxitektura

```
Clean Architecture + Repository Pattern + Service Layer
├── Handlers      — Telegram event handlers (Controllers)
├── Services      — Business logic
├── Repositories  — Database operations
├── Models        — SQLAlchemy ORM models
├── Middlewares   — Auth, rate limit, logging
└── Scheduler     — APScheduler background jobs
```

---

## 🚀 Ishga Tushirish

### 1. Talablar
- Docker & Docker Compose
- Telegram Bot Token (`@BotFather`)
- OpenAI API Key

### 2. O'rnatish

```bash
git clone https://github.com/yourname/it-pro-bot.git
cd it-pro-bot

cp .env.example .env
# .env faylni tahrirlang — BOT_TOKEN va OPENAI_API_KEY qo'shing
nano .env
```

### 3. Ishga tushirish

```bash
# Barcha servislari bilan ishga tushirish
docker compose up -d

# Loglarni ko'rish
docker compose logs -f bot

# To'xtatish
docker compose down
```

### 4. Ma'lumotlar bazasi migratsiyasi

```bash
# Docker ichida
docker compose exec bot alembic upgrade head

# Lokal
alembic upgrade head
```

---

## 🔧 Lokal Ishlab Chiqish

```bash
# Virtual muhit
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Kutubxonalar
pip install -r requirements.txt

# .env sozlash
cp .env.example .env

# Migratsiya
alembic upgrade head

# Botni ishga tushirish
python -m bot.main
```

---

## 🧪 Testlar

```bash
# Barcha testlar
pytest

# Faqat unit testlar
pytest tests/unit/ -v

# Coverage bilan
pytest --cov=. --cov-report=html
```

---

## 📊 Monitoring

| Xizmat | URL | Parol |
|--------|-----|-------|
| Grafana | http://localhost:3000 | `GRAFANA_PASSWORD` |
| Prometheus | http://localhost:9090 | — |
| API Health | http://localhost:8080/health | — |
| API Metrics | http://localhost:8080/metrics | — |
| RabbitMQ UI | http://localhost:15672 | `RABBITMQ_PASSWORD` |

---

## 🤖 Bot Buyruqlari

| Buyruq | Tavsif |
|--------|--------|
| `/start` | Botni boshlash |
| `/help` | Yordam |
| `/ai` | AI Yordamchi |
| `/news` | IT Yangiliklar |
| `/github` | GitHub Trending |
| `/habr` | Habr Maqolalari |
| `/python` | Python yangiliklari |
| `/frontend` | Frontend yangiliklari |
| `/backend` | Backend yangiliklari |
| `/security` | Security yangiliklari |
| `/devops` | DevOps yangiliklari |
| `/trending` | Bugungi trendlar |
| `/profile` | Profilim |
| `/settings` | Sozlamalar |
| `/cancel` | Bekor qilish |

### Admin Buyruqlar
| Buyruq | Tavsif |
|--------|--------|
| `/admin` | Admin panel |
| `/ban <id>` | Foydalanuvchini bloklash |
| `/unban <id>` | Blokdan chiqarish |
| `/premium <id> <kun>` | Premium berish |

---

## 📁 Loyiha Strukturasi

```
project/
├── bot/
│   ├── handlers/       # Telegram handlers
│   ├── keyboards/      # Inline & reply keyboards
│   ├── middlewares/    # Auth, rate limit, logging
│   ├── filters/        # Custom aiogram filters
│   └── main.py         # Bot entry point
├── api/
│   └── app.py          # FastAPI health/metrics/admin
├── core/
│   ├── config.py       # Pydantic settings
│   ├── exceptions.py   # Custom exceptions
│   └── logging.py      # Structlog setup
├── database/
│   ├── base.py         # SQLAlchemy base
│   ├── models.py       # ORM models
│   ├── connection.py   # Engine & sessions
│   ├── redis_client.py # Redis cache manager
│   └── migrations/     # Alembic migrations
├── services/
│   ├── ai_service.py   # OpenAI GPT integration
│   ├── news_service.py # News scraping
│   └── user_service.py # User business logic
├── repositories/
│   ├── user_repository.py
│   └── news_repository.py
├── scheduler/
│   └── scheduler.py    # APScheduler jobs
├── tasks/
│   └── celery_tasks.py # Celery background tasks
├── utils/
│   └── helpers.py      # Utility functions
├── tests/
│   └── unit/           # Unit tests
├── nginx/nginx.conf     # Nginx config
├── monitoring/          # Prometheus & Grafana
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── alembic.ini
```

---

## 🔒 Xavfsizlik

- **Rate Limiting** — Foydalanuvchi bazasida sliding-window
- **Ban tizimi** — Avtomatik bloklash imkoniyati
- **Input Sanitization** — Barcha kirishlar tozalanadi
- **SQL Injection** — SQLAlchemy ORM himoyasi
- **Secret Management** — `.env` fayli orqali
- **Non-root Docker** — Konteynerda `botuser` bilan ishlaydi
- **Nginx** — Reverse proxy + SSL + security headers

---

## 🚀 CI/CD

GitHub Actions orqali avtomatik:
1. **Lint** — Ruff + Black formatlash tekshiruvi
2. **Test** — Pytest + coverage
3. **Build** — Docker image build + GHCR ga push
4. **Deploy** — SSH orqali serverga deploy

---

## 📄 Litsenziya

MIT License — erkin foydalaning!

---

## 👨‍💻 Muallif

IT Pro Bot — Enterprise Telegram AI Assistant
