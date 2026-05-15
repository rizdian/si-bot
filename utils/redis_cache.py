import hashlib
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    REDIS_DB,
    CACHE_TTL_STREAM,
    CACHE_TTL_META,
)

logger = logging.getLogger("bot")

_pool: Optional[aioredis.Redis] = None


def _is_available() -> bool:
    return _pool is not None


def _serialize_safe(obj):
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _serialize_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_safe(item) for item in obj]
    return str(obj)


def _generate_key(query: str) -> str:
    normalized = query.strip().lower()
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"yt:{digest}"


def _generate_meta_key(video_id: str) -> str:
    return f"yt:meta:{video_id}"


async def init_redis() -> bool:
    global _pool
    try:
        _pool = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD or None,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        await _pool.ping()
        logger.info(
            "Redis connected: %s:%s db=%s", REDIS_HOST, REDIS_PORT, REDIS_DB,
        )
        return True
    except Exception as e:
        logger.warning("Redis unavailable, caching disabled: %s", e)
        _pool = None
        return False


async def close_redis() -> None:
    global _pool
    if _pool:
        try:
            await _pool.aclose()
            logger.info("Redis connection closed.")
        except Exception as e:
            logger.warning("Error closing Redis: %s", e)
        _pool = None


async def get_cached(query: str) -> Optional[dict]:
    if not _is_available():
        return None
    try:
        key = _generate_key(query)
        raw = await _pool.get(key)
        if raw is None:
            logger.debug("Cache MISS: %s", key)
            return None
        logger.debug("Cache HIT: %s", key)
        return json.loads(raw)
    except Exception as e:
        logger.warning("Redis get error: %s", e)
        return None


async def set_cached(query: str, data: dict) -> None:
    if not _is_available():
        return
    try:
        key = _generate_key(query)
        safe = _serialize_safe(data)
        payload = json.dumps(safe, ensure_ascii=False)
        await _pool.set(key, payload, ex=CACHE_TTL_STREAM)
        logger.debug("Cache SET: %s (TTL=%ds)", key, CACHE_TTL_STREAM)
    except Exception as e:
        logger.warning("Redis set error: %s", e)


async def get_meta(video_id: str) -> Optional[dict]:
    if not _is_available() or not video_id:
        return None
    try:
        key = _generate_meta_key(video_id)
        raw = await _pool.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning("Redis meta get error: %s", e)
        return None


async def set_meta(video_id: str, data: dict) -> None:
    if not _is_available() or not video_id:
        return
    try:
        key = _generate_meta_key(video_id)
        meta_fields = {
            "id": data.get("id"),
            "title": data.get("title"),
            "duration": data.get("duration"),
            "thumbnail": data.get("thumbnail"),
            "webpage_url": data.get("webpage_url"),
            "channel": data.get("channel"),
            "uploader": data.get("uploader"),
            "description": data.get("description"),
        }
        related = data.get("related_videos")
        if related and isinstance(related, list):
            meta_fields["related_videos"] = _serialize_safe(related[:10])
        payload = json.dumps(meta_fields, ensure_ascii=False)
        await _pool.set(key, payload, ex=CACHE_TTL_META)
        logger.debug("Meta SET: %s (TTL=%ds)", key, CACHE_TTL_META)
    except Exception as e:
        logger.warning("Redis meta set error: %s", e)


async def invalidate(query: str) -> None:
    if not _is_available():
        return
    try:
        key = _generate_key(query)
        await _pool.delete(key)
        logger.debug("Cache INVALIDATE: %s", key)
    except Exception as e:
        logger.warning("Redis invalidate error: %s", e)


async def invalidate_by_video_id(video_id: str) -> None:
    if not _is_available() or not video_id:
        return
    try:
        key = _generate_meta_key(video_id)
        await _pool.delete(key)
        logger.debug("Meta INVALIDATE: %s", key)
    except Exception as e:
        logger.warning("Redis meta invalidate error: %s", e)
