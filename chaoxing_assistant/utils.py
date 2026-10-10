from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path


LOCAL_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def now_local() -> datetime:
    return datetime.now(tz=LOCAL_TZ)


def timestamp() -> str:
    return now_local().isoformat(timespec="seconds")


def sanitize_filename(value: str, max_length: int = 90) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    if not cleaned:
        cleaned = "未命名"
    return cleaned[:max_length].rstrip(" ._") or "未命名"


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def redact_secret(value: str, visible_prefix: int = 8) -> str:
    if not value:
        return "<empty>"
    if len(value) <= visible_prefix:
        return "***"
    return value[:visible_prefix] + "***"
