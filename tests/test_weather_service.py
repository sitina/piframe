"""
Tests for WeatherService class from the new modular architecture.
"""
import unittest
import json
import io
import time
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piframe.services.weather_service import WeatherService
from piframe.config.settings import Config
from piframe.models.cache import CacheManager


class TestWeatherService(unittest.TestCase):
    """Test cases for WeatherService class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = Config(
            weather_api_key="test_api_key_12345",
            weather_location="Prague",
            weather_lat=50.1267,
            weather_lon=14.4936,
            weather_cache_ttl=600,
            forecast_cache_ttl=1800,
            chart_cache_ttl=3600
        )
        
        # Mock cache manager
        self.mock_cache_manager = MagicMock(spec=CacheManager)
        
        # Create service with mocked cache
        self.weather_service = WeatherService(
            config=self.config,
            cache_manager=self.mock_cache_manager
        )

    def tearDown(self):
        """Clean up after tests."""
        self.weather_service.close()

    def test_init(self):
        """Test WeatherService initialization."""
        self.assertEqual(self.weather_service.config, self.config)
        self.assertEqual(self.weather_service.cache_manager, self.mock_cache_manager)
        self.assertIsNone(self.weather_service._session)

    def test_session_property(self):
        """Test session property creates and caches requests session."""
        # First access should create session
        session1 = self.weather_service.session
        self.assertIsNotNone(session1)
        self.assertEqual(session1.headers['User-Agent'], 'PiFrame/0.2.0')
        
        # Second access should return same session
        session2 = self.weather_service.session
        self.assertIs(session1, session2)

    @patch('piframe.services.weather_service.requests.Session')
    def test_get_current_weather_success(self, mock_session_class):
        """Test successful current weather retrieval."""
        # Mock response
        mock_weather_data = {
            'main': {'temp': 293.15, 'feels_like': 290.15},
            'weather': [{'main': 'Clear', 'description': 'clear sky'}]
        }
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_weather_data
        mock_response.raise_for_status.return_value = None
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Mock cache miss
        self.mock_cache_manager.get.return_value = None
        
        # Test
        result = self.weather_service.get_current_weather()
        
        # Verify
        self.assertEqual(result, mock_weather_data)
        self.mock_cache_manager.get.assert_called_with('weather', 'current_Prague')
        self.mock_cache_manager.set.assert_called_with('weather', 'current_Prague', mock_weather_data)
        mock_session.get.assert_called_once()

    def test_get_current_weather_no_api_key(self):
        """Test current weather retrieval without API key."""
        config = Config(weather_api_key="", weather_location="Prague")
        service = WeatherService(config, self.mock_cache_manager)
        
        result = service.get_current_weather()
        
        self.assertIsNone(result)
        self.mock_cache_manager.get.assert_not_called()

    def test_get_current_weather_cached_data(self):
        """Test current weather retrieval with cached data."""
        cached_data = {'main': {'temp': 293.15}, 'weather': [{'main': 'Clear'}]}
        self.mock_cache_manager.get.return_value = cached_data
        
        result = self.weather_service.get_current_weather()
        
        self.assertEqual(result, cached_data)
        self.mock_cache_manager.get.assert_called_with('weather', 'current_Prague')
        self.mock_cache_manager.set.assert_not_called()

    @patch('piframe.services.weather_service.requests.Session')
    def test_get_current_weather_force_refresh(self, mock_session_class):
        """Test current weather retrieval with force refresh."""
        cached_data = {'main': {'temp': 293.15}, 'weather': [{'main': 'Clear'}]}
        
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {'main': {'temp': 295.15}}
        mock_response.raise_for_status.return_value = None
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        result = self.weather_service.get_current_weather(force_refresh=True)
        
        # Should not check cache first when force_refresh=True
        self.mock_cache_manager.get.assert_not_called()
        mock_session.get.assert_called_once()

    @patch('piframe.services.weather_service.requests.Session')
    def test_get_current_weather_api_error_with_fallback(self, mock_session_class):
        """Test current weather API error with cached fallback."""
        # Mock API error
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("API Error")
        mock_session_class.return_value = mock_session
        
        # Mock cache miss on first call, hit on fallback
        cached_data = {'main': {'temp': 293.15}, 'weather': [{'main': 'Clear'}]}
        self.mock_cache_manager.get.side_effect = [None, cached_data]
        
        with patch('piframe.services.weather_service.requests.exceptions.RequestException', Exception):
            result = self.weather_service.get_current_weather()
        
        self.assertEqual(result, cached_data)
        # Should be called twice: once for normal cache check, once for fallback
        self.assertEqual(self.mock_cache_manager.get.call_count, 2)

    @patch('piframe.services.weather_service.requests.Session')
    def test_get_forecast_success(self, mock_session_class):
        """Test successful forecast retrieval."""
        mock_forecast_data = {
            'list': [
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                }
            ]
        }
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_forecast_data
        mock_response.raise_for_status.return_value = None
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Mock cache miss and no file fallback
        self.mock_cache_manager.get.return_value = None
        
        with patch('os.path.exists', return_value=False):
            result = self.weather_service.get_forecast()
        
        self.assertEqual(result, mock_forecast_data)
        self.mock_cache_manager.set.assert_called_with('forecast', 'forecast_Prague', mock_forecast_data)

    @patch('builtins.open', new_callable=mock_open, read_data='{"list": [{"temp": 20}]}')
    @patch('os.path.exists', return_value=True)
    def test_get_forecast_file_fallback(self, mock_exists, mock_file):
        """Test forecast retrieval from file fallback."""
        self.mock_cache_manager.get.return_value = None
        
        result = self.weather_service.get_forecast()
        
        self.assertEqual(result, {"list": [{"temp": 20}]})
        mock_file.assert_called_once()

    def test_to_celsius(self):
        """Test temperature conversion from Kelvin to Celsius."""
        self.assertEqual(self.weather_service.to_celsius(273.15), 0.0)
        self.assertEqual(self.weather_service.to_celsius(293.15), 20.0)
        self.assertEqual(self.weather_service.to_celsius(373.15), 100.0)

    def test_process_forecast_data_success(self):
        """Test successful forecast data processing."""
        forecast_data = {
            'list': [
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                },
                {
                    'main': {'temp': 295.15, 'feels_like': 292.15, 'humidity': 65},
                    'weather': [{'main': 'Clouds', 'icon': '02d'}],
                    'dt_txt': '2023-12-25 15:00:00'
                }
            ]
        }
        
        result = self.weather_service.process_forecast_data(forecast_data)
        
        self.assertEqual(len(result), 2)
        
        # Check first item
        first_item = result[0]
        self.assertEqual(first_item['temp'], 20.0)
        self.assertEqual(first_item['feels_like'], 17.0)
        self.assertEqual(first_item['weather'], 'Clear')
        self.assertEqual(first_item['humidity'], 60)
        self.assertEqual(first_item['time'], '14:00')
        self.assertEqual(first_item['icon'], '/static/images/01d@2x.gif')

    def test_process_forecast_data_empty(self):
        """Test forecast data processing with empty data."""
        self.assertEqual(self.weather_service.process_forecast_data({}), [])
        self.assertEqual(self.weather_service.process_forecast_data(None), [])
        self.assertEqual(self.weather_service.process_forecast_data({'list': []}), [])

    def test_process_forecast_data_invalid_items(self):
        """Test forecast data processing with invalid items."""
        forecast_data = {
            'list': [
                {'invalid': 'data'},  # Missing required fields
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                }
            ]
        }
        
        result = self.weather_service.process_forecast_data(forecast_data)
        
        # Should skip invalid item and process valid one
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['temp'], 20.0)

    def test_generate_forecast_chart_success(self):
        """Test successful forecast chart generation."""
        # Mock cache miss
        self.mock_cache_manager.get.return_value = None
        
        # Mock forecast data
        forecast_data = {
            'list': [
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                }
            ]
        }
        
        with patch.object(self.weather_service, 'get_forecast', return_value=forecast_data):
            result = self.weather_service.generate_forecast_chart()

            self.assertIsInstance(result, bytes)
            self.assertGreater(len(result), 0)
            self.mock_cache_manager.set.assert_called_once()
            cache_name, cache_key, chart_bytes = self.mock_cache_manager.set.call_args[0]
            self.assertEqual(cache_name, 'chart')
            self.assertEqual(cache_key, 'forecast_chart')
            self.assertEqual(chart_bytes, result)

    def test_generate_forecast_chart_cached_data(self):
        """Test forecast chart generation with cached data."""
        cached_chart = b'cached_png_data'
        self.mock_cache_manager.get.return_value = cached_chart
        
        result = self.weather_service.generate_forecast_chart()
        
        self.assertEqual(result, cached_chart)
        self.mock_cache_manager.get.assert_called_with('chart', 'forecast_chart')

    def test_generate_forecast_chart_no_forecast_data(self):
        """Test forecast chart generation with no forecast data."""
        self.mock_cache_manager.get.return_value = None
        
        with patch.object(self.weather_service, 'get_forecast', return_value=None):
            result = self.weather_service.generate_forecast_chart()
            
            self.assertIsNone(result)

    def test_create_forecast_figure_empty_data(self):
        """Test creating forecast figure with empty data."""
        fig = self.weather_service._create_forecast_figure([])
        
        self.assertIsNotNone(fig)
        # Should create a figure even with no data

    def test_create_forecast_figure_with_data(self):
        """Test creating forecast figure with valid data."""
        forecast = [
            {
                'dt': '2023-12-25 14:00:00',
                'temp': 20.0,
                'feels_like': 17.0,
                'weather': 'Clear',
                'humidity': 60,
                'icon': '/static/images/01d@2x.gif',
                'time': '14:00'
            },
            {
                'dt': '2023-12-25 15:00:00',
                'temp': 22.0,
                'feels_like': 19.0,
                'weather': 'Clouds',
                'humidity': 65,
                'icon': '/static/images/02d@2x.gif',
                'time': '15:00'
            }
        ]
        
        fig = self.weather_service._create_forecast_figure(forecast)
        
        self.assertIsNotNone(fig)
        self.assertEqual(len(fig.axes), 1)

    def test_cleanup_expired_cache(self):
        """Test cache cleanup."""
        self.weather_service.cleanup_expired_cache()
        
        self.mock_cache_manager.cleanup_all_expired.assert_called_once()

    def test_close(self):
        """Test service cleanup."""
        # Create a mock session
        mock_session = MagicMock()
        self.weather_service._session = mock_session
        
        self.weather_service.close()
        
        mock_session.close.assert_called_once()
        self.assertIsNone(self.weather_service._session)

    @patch('piframe.services.weather_service.requests.Session')
    def test_get_current_weather_json_decode_error(self, mock_session_class):
        """Test current weather with JSON decode error."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        self.mock_cache_manager.get.return_value = None
        
        result = self.weather_service.get_current_weather()
        
        self.assertIsNone(result)

    @patch('piframe.services.weather_service.requests.Session')
    def test_get_forecast_json_decode_error(self, mock_session_class):
        """Test forecast with JSON decode error."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        self.mock_cache_manager.get.return_value = None
        
        with patch('os.path.exists', return_value=False):
            result = self.weather_service.get_forecast()
        
        self.assertIsNone(result)

    def test_generate_forecast_chart_exception_handling(self):
        """Test forecast chart generation with exception."""
        self.mock_cache_manager.get.return_value = None
        
        with patch.object(self.weather_service, 'get_forecast', side_effect=Exception("Test error")):
            result = self.weather_service.generate_forecast_chart()
            
            self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
