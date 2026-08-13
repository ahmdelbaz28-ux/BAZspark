"""
Redis client module for backend services.
Provides Redis connection and utility functions.
"""
from typing import Any

import redis.asyncio as redis

from ..config import Config


async def get_redis_client() -> redis.Redis:  # noqa: S7503 — async for redis.asynci compatibility
    """
    Get a Redis client instance.

    Returns:
        redis.Redis: Redis client instance
    """
    redis_client = redis.Redis(
        host=Config.REDIS_HOST or "localhost",
        port=Config.REDIS_PORT,
        password=Config.REDIS_PASSWORD,
        decode_responses=False,  # Keep as bytes for consistency
        health_check_interval=30
    )
    return redis_client


async def get_value(key: str) -> Any | None:
    """
    Get a value from Redis by key.

    Args:
        key: The key to retrieve

    Returns:
        The value if found, None otherwise
    """
    redis_client = await get_redis_client()
    try:
        value = await redis_client.get(key)
        return value
    except Exception:
        return None


async def set_value(key: str, value: Any, expire: int | None = 3600) -> bool:
    """
    Set a value in Redis with optional expiration.

    Args:
        key: The key to set
        value: The value to store
        expire: Expiration time in seconds (default: 3600)

    Returns:
        True if successful, False otherwise
    """
    redis_client = await get_redis_client()
    try:
        await redis_client.set(key, value, ex=expire)
        return True
    except Exception:
        return False


async def delete_key(key: str) -> bool:
    """
    Delete a key from Redis.

    Args:
        key: The key to delete

    Returns:
        True if successful, False otherwise
    """
    redis_client = await get_redis_client()
    try:
        result = await redis_client.delete(key)
        return result > 0
    except Exception:
        return False
