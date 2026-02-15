"""Redis caching for optimization results."""

import redis
import json
import hashlib
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages Redis caching for optimization results."""

    def __init__(self, redis_url: str):
        """
        Initialize cache manager.

        Args:
            redis_url: Redis connection URL
        """
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()  # Test connection
            self.available = True
            logger.info("Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis cache unavailable: {e}")
            self.redis = None
            self.available = False

    def generate_cache_key(self, request: Dict[str, Any], config: Dict[str, Any]) -> str:
        """
        Generate cache key from request + config.

        Args:
            request: Request dict
            config: Config dict

        Returns:
            SHA256 hash of request + config
        """
        # Create stable key from request inputs that affect canonicalization + config.
        # Important: include tools/rag_context/tool_outputs fingerprints; otherwise cache
        # hits can return incorrect optimizations for different retrieval contexts.
        def _fingerprint(obj: Any) -> str:
            try:
                s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            except TypeError:
                # Best-effort fallback for non-JSON-serializable objects.
                s = repr(obj)
            return hashlib.sha256(s.encode()).hexdigest()

        key_data = {
            "messages_fp": _fingerprint(request.get("messages", [])),
            "tools_fp": _fingerprint(request.get("tools")),
            "rag_fp": _fingerprint(request.get("rag_context")),
            "tool_outputs_fp": _fingerprint(request.get("tool_outputs")),
            "model": request.get("model"),
            # Config: include full config fingerprint, not just a subset.
            "config_fp": _fingerprint(config),
        }

        key_str = json.dumps(key_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return f"opt:cache:{hashlib.sha256(key_str.encode()).hexdigest()[:16]}"

    def get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached optimization result.

        Args:
            key: Cache key

        Returns:
            Cached result dict or None
        """
        if not self.available:
            return None

        try:
            cached_data = self.redis.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    def set_cached(self, key: str, value: Dict[str, Any], ttl: int = 600):
        """
        Store optimization result in cache.

        Args:
            key: Cache key
            value: Result dict to cache
            ttl: Time to live in seconds (default 10 minutes)
        """
        if not self.available:
            return

        try:
            cached_data = json.dumps(value)
            self.redis.setex(key, ttl, cached_data)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    def invalidate(self, key: str):
        """
        Invalidate a cached result.

        Args:
            key: Cache key
        """
        if not self.available:
            return

        try:
            self.redis.delete(key)
        except Exception as e:
            logger.warning(f"Cache invalidate failed: {e}")
