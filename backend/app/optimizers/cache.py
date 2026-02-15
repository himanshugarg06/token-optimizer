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
        # Create stable key from request and config
        key_data = {
            "messages": request.get("messages", []),
            "model": request.get("model"),
            "max_tokens": config.get("max_input_tokens"),
            "keep_n_turns": config.get("keep_last_n_turns")
        }

        key_str = json.dumps(key_data, sort_keys=True)
        hash_obj = hashlib.sha256(key_str.encode())
        return f"opt:cache:{hash_obj.hexdigest()[:16]}"

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
