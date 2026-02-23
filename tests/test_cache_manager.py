"""
Tests for cache management system from the new modular architecture.
"""
import unittest
import time
import threading
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piframe.models.cache import CacheEntry, TTLCache, CacheManager, get_cache_manager, reset_cache_manager
from piframe.config.settings import Config


class TestCacheEntry(unittest.TestCase):
    """Test cases for CacheEntry class."""

    def test_init(self):
        """Test CacheEntry initialization."""
        value = "test_value"
        timestamp = time.time()
        ttl = 60.0
        
        entry = CacheEntry(value, timestamp, ttl)
        
        self.assertEqual(entry.value, value)
        self.assertEqual(entry.timestamp, timestamp)
        self.assertEqual(entry.ttl, ttl)
        self.assertEqual(entry.access_count, 0)
        self.assertEqual(entry.last_access, timestamp)

    def test_post_init_sets_last_access(self):
        """Test that __post_init__ sets last_access if None."""
        timestamp = time.time()
        entry = CacheEntry("value", timestamp, 60.0, last_access=None)
        
        self.assertEqual(entry.last_access, timestamp)

    def test_is_expired_not_expired(self):
        """Test is_expired for non-expired entry."""
        timestamp = time.time()
        entry = CacheEntry("value", timestamp, 60.0)
        
        self.assertFalse(entry.is_expired())

    def test_is_expired_expired(self):
        """Test is_expired for expired entry."""
        timestamp = time.time() - 120  # 2 minutes ago
        entry = CacheEntry("value", timestamp, 60.0)  # 1 minute TTL
        
        self.assertTrue(entry.is_expired())

    def test_touch_updates_access_info(self):
        """Test touch method updates access count and time."""
        entry = CacheEntry("value", time.time(), 60.0)
        original_access_count = entry.access_count
        original_last_access = entry.last_access
        
        time.sleep(0.01)  # Small delay to ensure time difference
        entry.touch()
        
        self.assertEqual(entry.access_count, original_access_count + 1)
        self.assertGreater(entry.last_access, original_last_access)


class TestTTLCache(unittest.TestCase):
    """Test cases for TTLCache class."""

    def setUp(self):
        """Set up test fixtures."""
        self.cache = TTLCache(max_size=3, default_ttl=60.0)

    def test_init(self):
        """Test TTLCache initialization."""
        self.assertEqual(self.cache.max_size, 3)
        self.assertEqual(self.cache.default_ttl, 60.0)
        self.assertEqual(len(self.cache._cache), 0)

    def test_set_and_get_basic(self):
        """Test basic set and get operations."""
        self.cache.set("key1", "value1")
        
        result = self.cache.get("key1")
        self.assertEqual(result, "value1")

    def test_get_nonexistent_key(self):
        """Test getting nonexistent key returns default."""
        result = self.cache.get("nonexistent")
        self.assertIsNone(result)
        
        result = self.cache.get("nonexistent", "default")
        self.assertEqual(result, "default")

    def test_set_with_custom_ttl(self):
        """Test setting value with custom TTL."""
        self.cache.set("key1", "value1", ttl=30.0)
        
        entry = self.cache._cache["key1"]
        self.assertEqual(entry.ttl, 30.0)

    def test_get_expired_entry(self):
        """Test getting expired entry returns default."""
        # Set entry with very short TTL
        self.cache.set("key1", "value1", ttl=0.01)
        
        # Wait for expiration
        time.sleep(0.02)
        
        result = self.cache.get("key1")
        self.assertIsNone(result)
        
        # Entry should be removed from cache
        self.assertNotIn("key1", self.cache._cache)

    def test_lru_eviction(self):
        """Test LRU eviction when max_size is exceeded."""
        # Fill cache to max capacity
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")
        
        # Add one more entry, should evict oldest (key1)
        self.cache.set("key4", "value4")
        
        self.assertEqual(len(self.cache._cache), 3)
        self.assertNotIn("key1", self.cache._cache)
        self.assertIn("key2", self.cache._cache)
        self.assertIn("key3", self.cache._cache)
        self.assertIn("key4", self.cache._cache)

    def test_get_updates_lru_order(self):
        """Test that getting a value updates LRU order."""
        # Fill cache
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")
        
        # Access key1 to make it most recently used
        self.cache.get("key1")
        
        # Add new entry, should evict key2 (least recently used)
        self.cache.set("key4", "value4")
        
        self.assertIn("key1", self.cache._cache)  # Should still be there
        self.assertNotIn("key2", self.cache._cache)  # Should be evicted
        self.assertIn("key3", self.cache._cache)
        self.assertIn("key4", self.cache._cache)

    def test_delete_existing_key(self):
        """Test deleting existing key."""
        self.cache.set("key1", "value1")
        
        result = self.cache.delete("key1")
        
        self.assertTrue(result)
        self.assertNotIn("key1", self.cache._cache)

    def test_delete_nonexistent_key(self):
        """Test deleting nonexistent key."""
        result = self.cache.delete("nonexistent")
        
        self.assertFalse(result)

    def test_clear(self):
        """Test clearing all entries."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        self.cache.clear()
        
        self.assertEqual(len(self.cache._cache), 0)

    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        # Set entries with different TTLs
        self.cache.set("valid", "value1", ttl=60.0)
        self.cache.set("expired1", "value2", ttl=0.01)
        self.cache.set("expired2", "value3", ttl=0.01)
        
        # Wait for expiration
        time.sleep(0.02)
        
        removed_count = self.cache.cleanup_expired()
        
        self.assertEqual(removed_count, 2)
        self.assertIn("valid", self.cache._cache)
        self.assertNotIn("expired1", self.cache._cache)
        self.assertNotIn("expired2", self.cache._cache)

    def test_stats(self):
        """Test cache statistics."""
        # Add some entries
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2", ttl=0.01)  # Will expire
        
        # Access one entry multiple times
        self.cache.get("key1")
        self.cache.get("key1")
        
        # Wait for one to expire
        time.sleep(0.02)
        
        stats = self.cache.stats()
        
        self.assertEqual(stats['total_entries'], 2)
        self.assertEqual(stats['expired_entries'], 1)
        self.assertEqual(stats['valid_entries'], 1)
        self.assertEqual(stats['max_size'], 3)
        self.assertGreater(stats['total_accesses'], 0)
        self.assertIsInstance(stats['entry_count'], int)

    def test_thread_safety(self):
        """Test thread safety of cache operations."""
        def worker(worker_id):
            for i in range(10):
                key = f"worker_{worker_id}_key_{i}"
                value = f"worker_{worker_id}_value_{i}"
                self.cache.set(key, value)
                retrieved = self.cache.get(key)
                self.assertEqual(retrieved, value)
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Cache should have entries (exact count depends on eviction)
        self.assertGreater(len(self.cache._cache), 0)


class TestCacheManager(unittest.TestCase):
    """Test cases for CacheManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.cache_manager = CacheManager()

    def test_init_default_caches(self):
        """Test initialization with default caches."""
        expected_caches = ['weather', 'forecast', 'chart', 'files', 'downloads', 'metadata']
        
        for cache_name in expected_caches:
            self.assertIn(cache_name, self.cache_manager._caches)
            self.assertIsInstance(self.cache_manager._caches[cache_name], TTLCache)

    def test_init_from_config(self):
        """Test initialization from configuration."""
        config = Config(
            weather_cache_ttl=300,
            forecast_cache_ttl=900,
            chart_cache_ttl=1800,
            files_cache_ttl=1800,
            download_cache_ttl=30,
            download_cache_size=10,
            metadata_cache_size=50
        )
        
        cache_manager = CacheManager(config)
        
        weather_cache = cache_manager.get_cache('weather')
        self.assertEqual(weather_cache.default_ttl, 300)
        
        downloads_cache = cache_manager.get_cache('downloads')
        self.assertEqual(downloads_cache.max_size, 10)

    def test_get_cache_existing(self):
        """Test getting existing cache."""
        cache = self.cache_manager.get_cache('weather')
        
        self.assertIsInstance(cache, TTLCache)

    def test_get_cache_nonexistent(self):
        """Test getting nonexistent cache."""
        cache = self.cache_manager.get_cache('nonexistent')
        
        self.assertIsNone(cache)

    def test_get_set_delete_operations(self):
        """Test get, set, and delete operations on named caches."""
        # Set value
        self.cache_manager.set('weather', 'test_key', 'test_value')
        
        # Get value
        result = self.cache_manager.get('weather', 'test_key')
        self.assertEqual(result, 'test_value')
        
        # Delete value
        deleted = self.cache_manager.delete('weather', 'test_key')
        self.assertTrue(deleted)
        
        # Verify deletion
        result = self.cache_manager.get('weather', 'test_key')
        self.assertIsNone(result)

    def test_operations_on_nonexistent_cache(self):
        """Test operations on nonexistent cache."""
        # Get from nonexistent cache
        result = self.cache_manager.get('nonexistent', 'key', 'default')
        self.assertEqual(result, 'default')
        
        # Set on nonexistent cache (should log warning but not crash)
        self.cache_manager.set('nonexistent', 'key', 'value')
        
        # Delete from nonexistent cache
        deleted = self.cache_manager.delete('nonexistent', 'key')
        self.assertFalse(deleted)

    def test_clear_cache(self):
        """Test clearing specific cache."""
        # Add entries to multiple caches
        self.cache_manager.set('weather', 'key1', 'value1')
        self.cache_manager.set('forecast', 'key2', 'value2')
        
        # Clear one cache
        self.cache_manager.clear_cache('weather')
        
        # Weather cache should be empty, forecast should still have data
        self.assertIsNone(self.cache_manager.get('weather', 'key1'))
        self.assertEqual(self.cache_manager.get('forecast', 'key2'), 'value2')

    def test_clear_all(self):
        """Test clearing all caches."""
        # Add entries to multiple caches
        self.cache_manager.set('weather', 'key1', 'value1')
        self.cache_manager.set('forecast', 'key2', 'value2')
        
        # Clear all caches
        self.cache_manager.clear_all()
        
        # All caches should be empty
        self.assertIsNone(self.cache_manager.get('weather', 'key1'))
        self.assertIsNone(self.cache_manager.get('forecast', 'key2'))

    def test_cleanup_all_expired(self):
        """Test cleanup of expired entries across all caches."""
        # Add entries with short TTLs
        self.cache_manager.set('weather', 'expired', 'value1', ttl=0.01)
        self.cache_manager.set('forecast', 'expired', 'value2', ttl=0.01)
        self.cache_manager.set('weather', 'valid', 'value3', ttl=60)
        
        # Wait for expiration
        time.sleep(0.02)
        
        cleanup_results = self.cache_manager.cleanup_all_expired()
        
        # Should have cleaned up expired entries
        self.assertGreater(cleanup_results.get('weather', 0), 0)
        self.assertGreater(cleanup_results.get('forecast', 0), 0)
        
        # Valid entry should still be there
        self.assertEqual(self.cache_manager.get('weather', 'valid'), 'value3')

    def test_get_all_stats(self):
        """Test getting statistics for all caches."""
        # Add some data
        self.cache_manager.set('weather', 'key1', 'value1')
        self.cache_manager.set('forecast', 'key2', 'value2')
        
        # Access some data
        self.cache_manager.get('weather', 'key1')
        
        stats = self.cache_manager.get_all_stats()
        
        # Should have stats for all cache types
        self.assertIn('weather', stats)
        self.assertIn('forecast', stats)
        
        # Weather cache should show the entry
        weather_stats = stats['weather']
        self.assertEqual(weather_stats['total_entries'], 1)
        self.assertGreater(weather_stats['total_accesses'], 0)

    def test_log_stats(self):
        """Test logging statistics."""
        # Add some data
        self.cache_manager.set('weather', 'key1', 'value1')
        
        # This should not raise an exception
        self.cache_manager.log_stats()


class TestGlobalCacheManager(unittest.TestCase):
    """Test cases for global cache manager functions."""

    def setUp(self):
        """Set up test fixtures."""
        reset_cache_manager()

    def tearDown(self):
        """Clean up after tests."""
        reset_cache_manager()

    def test_get_cache_manager_creates_instance(self):
        """Test that get_cache_manager creates instance."""
        manager = get_cache_manager()
        
        self.assertIsInstance(manager, CacheManager)

    def test_get_cache_manager_returns_same_instance(self):
        """Test that get_cache_manager returns same instance."""
        manager1 = get_cache_manager()
        manager2 = get_cache_manager()
        
        self.assertIs(manager1, manager2)

    def test_get_cache_manager_with_config(self):
        """Test get_cache_manager with configuration."""
        config = Config(weather_cache_ttl=300)
        
        manager = get_cache_manager(config)
        
        weather_cache = manager.get_cache('weather')
        self.assertEqual(weather_cache.default_ttl, 300)

    def test_reset_cache_manager(self):
        """Test resetting cache manager."""
        manager1 = get_cache_manager()
        
        reset_cache_manager()
        
        manager2 = get_cache_manager()
        
        self.assertIsNot(manager1, manager2)

    def test_thread_safety_global_manager(self):
        """Test thread safety of global cache manager access."""
        managers = []
        
        def get_manager():
            managers.append(get_cache_manager())
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=get_manager)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should get the same manager instance
        first_manager = managers[0]
        for manager in managers[1:]:
            self.assertIs(manager, first_manager)


class TestCacheIntegration(unittest.TestCase):
    """Integration tests for cache system."""

    def setUp(self):
        """Set up test fixtures."""
        reset_cache_manager()
        self.config = Config(
            weather_cache_ttl=60,
            download_cache_size=3
        )
        self.cache_manager = get_cache_manager(self.config)

    def tearDown(self):
        """Clean up after tests."""
        reset_cache_manager()

    def test_realistic_usage_scenario(self):
        """Test realistic usage scenario with multiple cache types."""
        # Simulate weather data caching
        weather_data = {'temp': 25.0, 'condition': 'sunny'}
        self.cache_manager.set('weather', 'current_prague', weather_data)
        
        # Simulate file listing caching
        files_data = [{'id': '1', 'name': 'photo1.jpg'}, {'id': '2', 'name': 'photo2.jpg'}]
        self.cache_manager.set('files', 'folder_123', files_data)
        
        # Simulate download caching
        image_data = b'fake image data'
        self.cache_manager.set('downloads', 'image_1', image_data)
        
        # Verify all data can be retrieved
        self.assertEqual(self.cache_manager.get('weather', 'current_prague'), weather_data)
        self.assertEqual(self.cache_manager.get('files', 'folder_123'), files_data)
        self.assertEqual(self.cache_manager.get('downloads', 'image_1'), image_data)
        
        # Check statistics
        stats = self.cache_manager.get_all_stats()
        self.assertEqual(stats['weather']['total_entries'], 1)
        self.assertEqual(stats['files']['total_entries'], 1)
        self.assertEqual(stats['downloads']['total_entries'], 1)

    def test_cache_eviction_and_expiration(self):
        """Test cache eviction and expiration in realistic scenario."""
        # Fill download cache beyond capacity (max_size=3)
        for i in range(5):
            self.cache_manager.set('downloads', f'image_{i}', f'data_{i}')
        
        # Should only have 3 entries due to LRU eviction
        downloads_cache = self.cache_manager.get_cache('downloads')
        self.assertEqual(len(downloads_cache._cache), 3)
        
        # Oldest entries should be evicted
        self.assertIsNone(self.cache_manager.get('downloads', 'image_0'))
        self.assertIsNone(self.cache_manager.get('downloads', 'image_1'))
        
        # Add expiring entries
        self.cache_manager.set('weather', 'expiring', 'data', ttl=0.01)
        
        # Wait for expiration
        time.sleep(0.02)
        
        # Cleanup expired entries
        cleanup_results = self.cache_manager.cleanup_all_expired()
        
        # Should have cleaned up the expired weather entry
        self.assertGreater(cleanup_results.get('weather', 0), 0)
        self.assertIsNone(self.cache_manager.get('weather', 'expiring'))


if __name__ == '__main__':
    unittest.main()