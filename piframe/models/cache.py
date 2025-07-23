"""
Centralized cache management for PiFrame application.
Handles all caching logic with TTL, size limits, and cleanup.
"""

import time
import threading
from typing import Any, Dict, Optional, Union, List, Tuple
from dataclasses import dataclass
from collections import OrderedDict

from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata."""
    value: Any
    timestamp: float
    ttl: float
    access_count: int = 0
    last_access: float = None
    
    def __post_init__(self):
        if self.last_access is None:
            self.last_access = self.timestamp
    
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() - self.timestamp > self.ttl
    
    def touch(self) -> None:
        """Update access information."""
        self.access_count += 1
        self.last_access = time.time()


class TTLCache:
    """
    Thread-safe cache with Time-To-Live (TTL) and size limits.
    """
    
    def __init__(self, max_size: int = 100, default_ttl: float = 3600):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum number of entries (LRU eviction when exceeded)
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if key not found or expired
            
        Returns:
            Cached value or default
        """
        with self._lock:
            if key not in self._cache:
                return default
            
            entry = self._cache[key]
            
            if entry.is_expired():
                logger.debug(f"Cache entry expired: {key}")
                del self._cache[key]
                return default
            
            # Move to end (most recently used)
            entry.touch()
            self._cache.move_to_end(key)
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl
        
        with self._lock:
            timestamp = time.time()
            entry = CacheEntry(value, timestamp, ttl)
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            # Enforce size limit
            while len(self._cache) > self.max_size:
                oldest_key = next(iter(self._cache))
                logger.debug(f"Evicting cache entry due to size limit: {oldest_key}")
                del self._cache[oldest_key]
    
    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key existed, False otherwise
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._cache.clear()
            logger.debug("Cache cleared")
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._cache.items():
                if current_time - entry.timestamp > entry.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            entries = list(self._cache.values())
            current_time = time.time()
            
            total_entries = len(entries)
            expired_entries = sum(1 for entry in entries if entry.is_expired())
            total_access_count = sum(entry.access_count for entry in entries)
            
            return {
                'total_entries': total_entries,
                'expired_entries': expired_entries,
                'valid_entries': total_entries - expired_entries,
                'max_size': self.max_size,
                'total_accesses': total_access_count,
                'memory_usage_approx': len(self._cache) * 100  # rough estimate
            }


class CacheManager:
    """
    Central manager for all application caches.
    """
    
    def __init__(self, config=None):
        """Initialize cache manager with configuration."""
        self._caches: Dict[str, TTLCache] = {}
        self._lock = threading.RLock()
        
        # Create caches based on configuration
        if config:
            self._init_from_config(config)
        else:
            self._init_default_caches()
    
    def _init_from_config(self, config) -> None:
        """Initialize caches from configuration."""
        cache_configs = [
            ('weather', config.weather_cache_ttl, 10),
            ('forecast', config.forecast_cache_ttl, 10),
            ('chart', config.chart_cache_ttl, 5),
            ('files', config.files_cache_ttl, 50),
            ('downloads', config.download_cache_ttl, config.download_cache_size),
            ('metadata', 3600, config.metadata_cache_size),  # 1 hour for metadata
        ]
        
        for name, ttl, size in cache_configs:
            self._caches[name] = TTLCache(max_size=size, default_ttl=ttl)
        
        logger.info(f"Initialized {len(self._caches)} caches from configuration")
    
    def _init_default_caches(self) -> None:
        """Initialize caches with default settings."""
        default_configs = [
            ('weather', 600, 10),      # 10 minutes
            ('forecast', 1800, 10),    # 30 minutes
            ('chart', 3600, 5),        # 1 hour
            ('files', 3600, 50),       # 1 hour
            ('downloads', 60, 5),      # 1 minute
            ('metadata', 3600, 20),    # 1 hour
        ]
        
        for name, ttl, size in default_configs:
            self._caches[name] = TTLCache(max_size=size, default_ttl=ttl)
        
        logger.info(f"Initialized {len(self._caches)} caches with defaults")
    
    def get_cache(self, name: str) -> Optional[TTLCache]:
        """Get a named cache instance."""
        return self._caches.get(name)
    
    def get(self, cache_name: str, key: str, default: Any = None) -> Any:
        """Get value from named cache."""
        cache = self.get_cache(cache_name)
        if cache:
            return cache.get(key, default)
        return default
    
    def set(self, cache_name: str, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in named cache."""
        cache = self.get_cache(cache_name)
        if cache:
            cache.set(key, value, ttl)
        else:
            logger.warning(f"Cache not found: {cache_name}")
    
    def delete(self, cache_name: str, key: str) -> bool:
        """Delete entry from named cache."""
        cache = self.get_cache(cache_name)
        if cache:
            return cache.delete(key)
        return False
    
    def clear_cache(self, cache_name: str) -> None:
        """Clear all entries from named cache."""
        cache = self.get_cache(cache_name)
        if cache:
            cache.clear()
    
    def clear_all(self) -> None:
        """Clear all caches."""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()
            logger.info("All caches cleared")
    
    def cleanup_all_expired(self) -> Dict[str, int]:
        """
        Clean up expired entries from all caches.
        
        Returns:
            Dictionary mapping cache names to number of expired entries removed
        """
        cleanup_results = {}
        with self._lock:
            for name, cache in self._caches.items():
                cleanup_results[name] = cache.cleanup_expired()
        
        total_cleaned = sum(cleanup_results.values())
        if total_cleaned > 0:
            logger.info(f"Cleaned up {total_cleaned} expired entries across all caches")
        
        return cleanup_results
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all caches."""
        stats = {}
        with self._lock:
            for name, cache in self._caches.items():
                stats[name] = cache.stats()
        return stats
    
    def log_stats(self) -> None:
        """Log statistics for all caches."""
        all_stats = self.get_all_stats()
        for name, stats in all_stats.items():
            logger.info(f"Cache '{name}': {stats['valid_entries']}/{stats['max_size']} entries, "
                       f"{stats['total_accesses']} accesses")


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None
_cache_manager_lock = threading.Lock()


def get_cache_manager(config=None) -> CacheManager:
    """Get or create the global cache manager instance."""
    global _cache_manager
    
    with _cache_manager_lock:
        if _cache_manager is None:
            _cache_manager = CacheManager(config)
    
    return _cache_manager


def reset_cache_manager() -> None:
    """Reset the global cache manager (mainly for testing)."""
    global _cache_manager
    
    with _cache_manager_lock:
        _cache_manager = None