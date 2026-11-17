import unittest
from unittest.mock import Mock, patch
import requests
from piframe.config import Config
from piframe.models.cache import CacheManager, TTLCache
from piframe.services.weather_service import WeatherService
from piframe.services.drive_service import DriveService


class TestStaleCache(unittest.TestCase):
    def test_freshness_retention_and_explicit_age_limit(self):
        cache = TTLCache(default_ttl=10, retention_ttl=30, max_bytes=8)
        with patch('piframe.models.cache.time.monotonic', return_value=100) as clock:
            cache.set('photo', b'1234')
            clock.return_value = 111
            self.assertIsNone(cache.get('photo'))
            self.assertEqual(cache.cleanup_expired(), 0)
            self.assertEqual(cache.get_stale('photo', max_age=20), b'1234')
            clock.return_value = 121
            self.assertIsNone(cache.get_stale('photo', max_age=20))
            self.assertEqual(cache.get_stale('photo', max_age=30), b'1234')
            # Reads never renew the original timestamp or extend retention.
            clock.return_value = 130
            self.assertIsNone(cache.get_stale('photo', max_age=999))
            self.assertEqual(cache.stats()['retained_bytes'], 0)

    def test_stale_entries_still_obey_payload_and_count_budgets(self):
        cache = TTLCache(max_size=2, default_ttl=1, retention_ttl=30, max_bytes=6)
        with patch('piframe.models.cache.time.monotonic', return_value=100) as clock:
            cache.set('a', b'1234')
            clock.return_value = 105
            cache.set('b', b'5678')
            self.assertIsNone(cache.get_stale('a', 30))
            self.assertLessEqual(cache.stats()['retained_bytes'], 6)
        with self.assertRaises(ValueError):
            cache.get_stale('a', float('inf'))
        with self.assertRaises(ValueError):
            cache.set('bad', b'x', ttl=float('nan'))

    def test_weather_and_forecast_outage_use_bounded_retained_data(self):
        config = Config(weather_api_key='fixture', weather_location='fixture',
                        weather_cache_ttl=10, forecast_cache_ttl=10,
                        weather_stale_max_age=30, forecast_stale_max_age=30,
                        weather_file_fallback='/nonexistent-fixture-forecast.json')
        cache = CacheManager(config)
        service = WeatherService(config, cache)
        self.addCleanup(service.close)
        service._session = Mock()
        service._session.get.side_effect = requests.Timeout('offline fixture')
        data = {'fixture': 'last-success'}
        with patch('piframe.models.cache.time.monotonic', return_value=100) as clock:
            cache.set('weather', 'current_fixture', data)
            cache.set('forecast', 'forecast_fixture', data)
            clock.return_value = 111
            self.assertEqual(service.get_current_weather(), data)
            self.assertEqual(service.get_forecast(), data)
            count = service._session.get.call_count
            self.assertEqual(service.get_current_weather(cache_only=True), data)
            self.assertEqual(service.get_forecast(cache_only=True), data)
            self.assertEqual(service._session.get.call_count, count)
            clock.return_value = 131
            self.assertIsNone(service.get_current_weather(cache_only=True))
            self.assertIsNone(service.get_forecast(cache_only=True))

    def test_drive_outage_uses_list_only_within_retention(self):
        config = Config(album_id='fixture', files_cache_ttl=10, files_stale_max_age=30)
        cache = CacheManager(config)
        service = DriveService(config, cache)
        self.addCleanup(service.close)
        service._service = Mock()
        service._service.files.return_value.list.return_value.execute.side_effect = RuntimeError('fixture offline')
        data = [{'id': 'previous-photo'}]
        with patch('piframe.models.cache.time.monotonic', return_value=100) as clock:
            cache.set('files', 'files_fixture', data)
            clock.return_value = 111
            self.assertEqual(service.list_images_in_folder(max_retries=1), data)
            clock.return_value = 131
            self.assertEqual(service.list_images_in_folder(max_retries=1), [])
