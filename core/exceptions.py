"""
Custom Exception Hierarchy
Domain-specific exceptions for clean error handling
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class BotBaseException(Exception):
    """Base exception for all bot-related errors."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, code={self.code!r})"


# ── Database ──────────────────────────────────────────────
class DatabaseException(BotBaseException):
    """Raised when a database operation fails."""


class RecordNotFoundException(DatabaseException):
    """Raised when a requested record does not exist."""

    def __init__(self, entity: str, identifier: Any) -> None:
        super().__init__(
            message=f"{entity} with id '{identifier}' not found.",
            code="RECORD_NOT_FOUND",
            details={"entity": entity, "identifier": str(identifier)},
        )


class DuplicateRecordException(DatabaseException):
    """Raised on unique-constraint violations."""

    def __init__(self, entity: str, field: str, value: Any) -> None:
        super().__init__(
            message=f"{entity} with {field}='{value}' already exists.",
            code="DUPLICATE_RECORD",
            details={"entity": entity, "field": field, "value": str(value)},
        )


# ── Authentication / Authorization ────────────────────────
class AuthException(BotBaseException):
    """Base auth exception."""


class UnauthorizedException(AuthException):
    """Raised when a user is not authenticated."""

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(message=message, code="UNAUTHORIZED")


class ForbiddenException(AuthException):
    """Raised when a user lacks permission for an action."""

    def __init__(self, message: str = "You don't have permission to do this.") -> None:
        super().__init__(message=message, code="FORBIDDEN")


class AdminRequiredException(ForbiddenException):
    """Raised when an admin-only action is attempted by a regular user."""

    def __init__(self) -> None:
        super().__init__(message="This action requires administrator privileges.")


# ── Rate Limiting ─────────────────────────────────────────
class RateLimitException(BotBaseException):
    """Raised when a user exceeds the request rate limit."""

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__(
            message=f"Too many requests. Please wait {retry_after} seconds.",
            code="RATE_LIMITED",
            details={"retry_after": retry_after},
        )
        self.retry_after = retry_after


# ── External Services ─────────────────────────────────────
class ExternalServiceException(BotBaseException):
    """Raised when an external API call fails."""

    def __init__(self, service: str, message: str) -> None:
        super().__init__(
            message=f"External service error [{service}]: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service},
        )


class OpenAIException(ExternalServiceException):
    """Raised when the OpenAI API call fails."""

    def __init__(self, message: str) -> None:
        super().__init__(service="OpenAI", message=message)


class ScraperException(ExternalServiceException):
    """Raised when web scraping fails."""

    def __init__(self, source: str, message: str) -> None:
        super().__init__(service=f"Scraper:{source}", message=message)


# ── User ──────────────────────────────────────────────────
class UserNotFoundException(RecordNotFoundException):
    def __init__(self, telegram_id: int) -> None:
        super().__init__(entity="User", identifier=telegram_id)


class UserBannedException(ForbiddenException):
    def __init__(self) -> None:
        super().__init__(message="Your account has been banned.")


class PremiumRequiredException(ForbiddenException):
    def __init__(self) -> None:
        super().__init__(message="This feature requires a Premium subscription.")


# ── Validation ────────────────────────────────────────────
class ValidationException(BotBaseException):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(
            message=f"Validation error on field '{field}': {message}",
            code="VALIDATION_ERROR",
            details={"field": field},
        )
