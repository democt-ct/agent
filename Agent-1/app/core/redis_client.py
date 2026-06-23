import json
import os
from typing import Any, Optional

import redis

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_URL = os.getenv("REDIS_URL", None)

# Session cache TTL (in seconds) - 24 hours by default
SESSION_CACHE_TTL = int(os.getenv("SESSION_CACHE_TTL", "86400"))

# Redis client singleton
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client singleton."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    
    if REDIS_URL:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    else:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )
    
    # Test connection
    try:
        _redis_client.ping()
    except redis.ConnectionError:
        # If Redis is not available, create a mock client that does nothing
        _redis_client = _MockRedisClient()
    
    return _redis_client


class _MockRedisClient:
    """Mock Redis client for fallback when Redis is not available."""
    
    def __init__(self):
        self._store = {}
    
    def ping(self):
        return True
    
    def get(self, key):
        return self._store.get(key)
    
    def set(self, key, value, ex=None):
        self._store[key] = value
        return True
    
    def delete(self, *keys):
        for key in keys:
            self._store.pop(key, None)
        return len(keys)
    
    def exists(self, key):
        return key in self._store
    
    def expire(self, key, time):
        return True
    
    def keys(self, pattern="*"):
        import fnmatch
        return [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]


def get_session_cache(session_id: str) -> Optional[dict]:
    """Get session data from Redis cache."""
    client = get_redis_client()
    key = f"session:{session_id}"
    data = client.get(key)
    if data:
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def set_session_cache(session_id: str, data: dict, ttl: int = SESSION_CACHE_TTL) -> bool:
    """Set session data in Redis cache."""
    client = get_redis_client()
    key = f"session:{session_id}"
    try:
        serialized = json.dumps(data, ensure_ascii=False, default=str)
        client.set(key, serialized, ex=ttl)
        return True
    except Exception:
        return False


def delete_session_cache(session_id: str) -> bool:
    """Delete session data from Redis cache."""
    client = get_redis_client()
    key = f"session:{session_id}"
    client.delete(key)
    return True


def get_short_term_memory(session_id: str) -> Optional[dict]:
    """Get short-term memory from Redis cache."""
    session_data = get_session_cache(session_id)
    if session_data:
        return session_data.get("short_term_memory")
    return None


def set_short_term_memory(session_id: str, memory: dict, ttl: int = SESSION_CACHE_TTL) -> bool:
    """Set short-term memory in Redis cache."""
    client = get_redis_client()
    key = f"session:{session_id}"
    
    # Get existing session data or create new
    existing = get_session_cache(session_id) or {}
    existing["short_term_memory"] = memory
    
    return set_session_cache(session_id, existing, ttl)


def clear_expired_sessions():
    """Clear expired sessions (optional cleanup task)."""
    client = get_redis_client()
    # Redis handles expiration automatically, but we can add custom cleanup if needed
    return True