from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TypedDict


class AfkRecord(TypedDict):
    original_nick: Optional[str]
    timestamp: datetime
    reason: Optional[str]


_afk_store: dict[int, AfkRecord] = {}


def set_afk(user_id: int, original_nick: Optional[str], reason: Optional[str] = None) -> None:
    _afk_store[user_id] = {
        "original_nick": original_nick,
        "timestamp": datetime.now(timezone.utc),
        "reason": reason,
    }


def remove_afk(user_id: int) -> Optional[AfkRecord]:
    return _afk_store.pop(user_id, None)


def is_afk(user_id: int) -> bool:
    return user_id in _afk_store


def get_afk(user_id: int) -> Optional[AfkRecord]:
    return _afk_store.get(user_id)


def get_all_afk() -> dict[int, AfkRecord]:
    return dict(_afk_store)


def format_duration(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = now - dt
    total_seconds = int(delta.total_seconds())

    if total_seconds < 60:
        return f"{total_seconds} detik"

    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes} menit"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 24:
        return f"{hours} jam {remaining_minutes} menit"

    days = hours // 24
    remaining_hours = hours % 24
    return f"{days} hari {remaining_hours} jam"
