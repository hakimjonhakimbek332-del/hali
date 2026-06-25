"""
ORM Models — All database tables in one place
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, SoftDeleteMixin, TimestampMixin


# ── Enums ──────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"
    BANNED = "banned"


class SubscriptionCategory(str, enum.Enum):
    ALL = "all"
    AI = "ai"
    PYTHON = "python"
    FRONTEND = "frontend"
    BACKEND = "backend"
    SECURITY = "security"
    DEVOPS = "devops"
    GITHUB = "github"
    HABR = "habr"


class NewsSource(str, enum.Enum):
    HACKER_NEWS = "hacker_news"
    DEV_TO = "dev_to"
    GITHUB_TRENDING = "github_trending"
    HABR = "habr"
    STACK_OVERFLOW = "stack_overflow"
    RSS = "rss"


class AIMessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ── User Models ────────────────────────────────────────────────────────────────

class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user ID
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default="uz", nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Stats
    messages_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_queries_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Premium
    premium_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Referral
    referred_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    referral_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)

    # Relationships
    subscriptions: Mapped[List["UserSubscription"]] = relationship(
        "UserSubscription", back_populates="user", cascade="all, delete-orphan"
    )
    ai_sessions: Mapped[List["AISession"]] = relationship(
        "AISession", back_populates="user", cascade="all, delete-orphan"
    )
    referrals: Mapped[List["User"]] = relationship(
        "User", foreign_keys=[referred_by]
    )

    __table_args__ = (
        Index("ix_users_role", "role"),
        Index("ix_users_is_active", "is_active"),
    )

    @property
    def is_premium(self) -> bool:
        if self.role == UserRole.ADMIN:
            return True
        if self.premium_until and self.premium_until > datetime.utcnow():
            return True
        return False

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name


class UserSubscription(Base, TimestampMixin):
    __tablename__ = "user_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    category: Mapped[SubscriptionCategory] = mapped_column(
        Enum(SubscriptionCategory, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_user_subscription"),
        Index("ix_user_subscriptions_user_id", "user_id"),
    )


# ── News Models ────────────────────────────────────────────────────────────────

class NewsItem(Base, TimestampMixin):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[NewsSource] = mapped_column(Enum(NewsSource, values_callable=lambda x: [e.value for e in x]), nullable=False)
    category: Mapped[SubscriptionCategory] = mapped_column(
        Enum(SubscriptionCategory, values_callable=lambda x: [e.value for e in x]), default=SubscriptionCategory.ALL
    )
    score: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    author: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_news_source_category", "source", "category"),
        Index("ix_news_is_sent", "is_sent"),
        Index("ix_news_published_at", "published_at"),
    )


class GithubRepository(Base, TimestampMixin):
    __tablename__ = "github_repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    stars_today: Mapped[int] = mapped_column(Integer, default=0)
    topics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    trending_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_github_language", "language"),
        Index("ix_github_is_sent", "is_sent"),
    )


# ── AI Session Models ──────────────────────────────────────────────────────────

class AISession(Base, TimestampMixin):
    __tablename__ = "ai_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship("User", back_populates="ai_sessions")
    messages: Mapped[List["AIMessage"]] = relationship(
        "AIMessage", back_populates="session", cascade="all, delete-orphan",
        order_by="AIMessage.created_at"
    )

    __table_args__ = (Index("ix_ai_sessions_user_id", "user_id"),)


class AIMessage(Base, TimestampMixin):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_sessions.id"), nullable=False
    )
    role: Mapped[AIMessageRole] = mapped_column(Enum(AIMessageRole, values_callable=lambda x: [e.value for e in x]), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped["AISession"] = relationship("AISession", back_populates="messages")

    __table_args__ = (Index("ix_ai_messages_session_id", "session_id"),)


# ── Admin / Broadcast Models ───────────────────────────────────────────────────

class BroadcastMessage(Base, TimestampMixin):
    __tablename__ = "broadcast_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parse_mode: Mapped[str] = mapped_column(String(16), default="HTML")
    target_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BotStatistics(Base, TimestampMixin):
    __tablename__ = "bot_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, unique=True)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    messages_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_queries: Mapped[int] = mapped_column(Integer, default=0)
    news_sent: Mapped[int] = mapped_column(Integer, default=0)
