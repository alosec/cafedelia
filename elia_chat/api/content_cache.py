"""
LRU cache for expanded content to improve performance.
"""

import time
from collections import OrderedDict
from typing import Any, Optional

import logging

logger = logging.getLogger(__name__)


class LRUCache:
    """Simple LRU cache implementation for content caching."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time to live for cache entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key not in self.cache:
            self.misses += 1
            return None
        
        value, timestamp = self.cache[key]
        
        # Check if expired
        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[key]
            self.misses += 1
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.hits += 1
        return value
    
    def put(self, key: str, value: Any) -> None:
        """Put value in cache."""
        # Remove if already exists
        if key in self.cache:
            del self.cache[key]
        
        # Add to end
        self.cache[key] = (value, time.time())
        
        # Evict oldest if over capacity
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "ttl_seconds": self.ttl_seconds
        }


# Global content cache
content_cache = LRUCache(max_size=100, ttl_seconds=3600)