"""
Utility Functions — Shared helpers used across the project
"""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return html.escape(str(text))


def truncate(text: str, max_len: int = 100, suffix: str = "...") -> str:
    """Truncate text to max_len characters."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-")


def format_number(n: int) -> str:
    """Format large numbers with K/M suffixes."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_datetime(dt: datetime, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Format a datetime object to a readable string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime(fmt)


def time_ago(dt: datetime) -> str:
    """Return a human-readable 'time ago' string."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return f"{seconds} soniya oldin"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} daqiqa oldin"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} soat oldin"
    days = hours // 24
    if days < 30:
        return f"{days} kun oldin"
    months = days // 30
    if months < 12:
        return f"{months} oy oldin"
    return f"{days // 365} yil oldin"


def hash_string(text: str) -> str:
    """Return a short SHA-256 hash of a string."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def chunk_list(lst: List[Any], size: int) -> List[List[Any]]:
    """Split a list into chunks of the given size."""
    return [lst[i: i + size] for i in range(0, len(lst), size)]


def flatten(nested: List[List[Any]]) -> List[Any]:
    """Flatten one level of nesting."""
    return [item for sublist in nested for item in sublist]


def safe_int(value: Any, default: int = 0) -> int:
    """Convert value to int safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Build a text-based progress bar."""
    if total == 0:
        return "▱" * length
    filled = int(length * current / total)
    bar = "▰" * filled + "▱" * (length - filled)
    pct = int(100 * current / total)
    return f"{bar} {pct}%"


def extract_urls(text: str) -> List[str]:
    """Extract all URLs from a string."""
    pattern = r"https?://[^\s<>\"']+"
    return re.findall(pattern, text)


def sanitize_input(text: str, max_length: int = 4000) -> str:
    """Strip dangerous characters and enforce length limit."""
    # Remove null bytes
    text = text.replace("\x00", "")
    # Strip excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def validate_url(url: str) -> bool:
    """Basic URL validation."""
    pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(pattern.match(url))
