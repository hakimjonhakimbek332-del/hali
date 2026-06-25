# ============================================================
# Production Dockerfile — Multi-stage build
# ============================================================
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Builder stage ──────────────────────────────────────────
FROM base AS builder

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ── Final stage ────────────────────────────────────────────
FROM base AS final

# Non-root user
RUN useradd --create-home --shell /bin/bash botuser
USER botuser
ENV PATH=/home/botuser/.local/bin:$PATH

# Copy installed packages to botuser home
COPY --from=builder --chown=botuser:botuser /root/.local /home/botuser/.local

WORKDIR /home/botuser/app

# Copy application code
COPY --chown=botuser:botuser . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080 8443

CMD ["python", "-m", "bot.main"]
