"""
Integration tests for PiFrame application (refactored architecture)
"""
import unittest
import tempfile
import os
import json
import time
import io
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, Response
from app import PiFrameApp
from piframe.config import Config


class TestIntegration(unittest.TestCase):
    """Integration tests for PiFrame application"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a config for testing
        self.config = Config()
        self.config.album_id = "test_album_id"
        self.config.weather_api_key = "test_api_key"
        self.config.weather_location = "Prague"
        self.config.secret_key = "test_secret_key"

        # Create temporary config data
        self.config_data = {
            "album": "test_album_id",
            "weather_api_key": "test_api_key",
            "weather_location": "Prague"
        }

        # Create app with mocked services
        with patch('app.WeatherService'), \
             patch('app.DriveService'), \
             patch('app.ImageService'), \
             patch('app.get_cache_manager'):
            self.piframe_app = PiFrameApp(self.config)
            self.piframe_app.app.config['TESTING'] = True
            self.client = self.piframe_app.app.test_client()

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'piframe_app'):
            self.piframe_app.close()

    def test_home_route_integration(self):
        """Test home route redirects to fullscreen"""
        with patch.object(self.piframe_app, 'get_fullscreen') as mock_get:
            mock_get.return_value = Response('<html>', status=200)
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)

    def test_fullscreen_route_integration(self):
        """Test fullscreen route renders correctly"""
        with patch.object(self.piframe_app, 'get_fullscreen') as mock_get:
            mock_get.return_value = Response('<html><iframe></iframe></html>', status=200)
            response = self.client.get('/fullscreen')
            self.assertEqual(response.status_code, 200)

    def test_weather_route_integration(self):
        """Test weather route with mocked service"""
        mock_weather = {
            'main': {'temp': 293.15, 'feels_like': 290.15},
            'weather': [{'main': 'Clear'}]
        }
        mock_forecast = {
            'list': [
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                }
            ]
        }

        self.piframe_app.weather_service.get_current_weather.return_value = mock_weather
        self.piframe_app.weather_service.get_forecast.return_value = mock_forecast
        self.piframe_app.weather_service.process_forecast_data.return_value = [
            {'temp': 20.0, 'feels_like': 17.0, 'weather': 'Clear', 'time': '14'}
        ]
        self.piframe_app.weather_service.to_celsius.return_value = 20.0

        with patch('app.render_template') as mock_render:
            mock_render.return_value = '<html>Weather</html>'
            response = self.client.get('/weather')
            self.assertEqual(response.status_code, 200)

    def test_random_picture_route_integration(self):
        """Test random picture route with mocked image service"""
        mock_response = Response(b'image_data', status=200, mimetype='image/jpeg')
        self.piframe_app.image_service.serve_random_image.return_value = mock_response

        response = self.client.get('/random-picture')
        self.assertEqual(response.status_code, 200)
        self.piframe_app.image_service.serve_random_image.assert_called_once_with()

    def test_new_random_picture_route_integration(self):
        """Test new random picture route forces new image"""
        mock_response = Response(b'image_data', status=200, mimetype='image/jpeg')
        self.piframe_app.image_service.serve_random_image.return_value = mock_response

        response = self.client.get('/random-picture/new')
        self.assertEqual(response.status_code, 200)
        self.piframe_app.image_service.serve_random_image.assert_called_once_with(force_new=True)

    def test_metadata_route_integration(self):
        """Test metadata route returns JSON"""
        mock_metadata = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45',
            'camera_info': 'Canon EOS R5',
            'dimensions': '4000 x 3000'
        }
        self.piframe_app.image_service.get_random_image_metadata.return_value = mock_metadata

        response = self.client.get('/random-picture/metadata')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['creation_date'], '25.12.2023')
        self.assertEqual(data['camera_info'], 'Canon EOS R5')

    def test_synchronized_route_integration(self):
        """Test synchronized picture route"""
        mock_response = Response(b'image_data', status=200, mimetype='image/jpeg')
        self.piframe_app.image_service.serve_synchronized_image.return_value = mock_response

        response = self.client.get('/random-picture/synchronized')
        self.assertEqual(response.status_code, 200)

    def test_synchronized_metadata_route_integration(self):
        """Test synchronized metadata route"""
        mock_metadata = {
            'creation_date': '25.12.2023',
            'image_id': 'test_id',
            'is_synchronized': True
        }
        self.piframe_app.image_service.get_synchronized_metadata.return_value = mock_metadata

        response = self.client.get('/random-picture/synchronized-metadata')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['image_id'], 'test_id')

    def test_forecast_chart_route_integration(self):
        """Test forecast chart generation"""
        mock_chart = io.BytesIO(b'PNG_DATA')
        self.piframe_app.weather_service.generate_forecast_chart.return_value = mock_chart

        response = self.client.get('/weather/forecast.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')

    def test_error_handling_weather_unavailable(self):
        """Test error handling when weather is unavailable"""
        self.piframe_app.weather_service.get_current_weather.return_value = None

        response = self.client.get('/weather')
        self.assertEqual(response.status_code, 503)

    def test_error_handling_picture_weather_unavailable(self):
        """Test picture route renders when optional weather is unavailable."""
        self.piframe_app.weather_service.get_current_weather.return_value = None

        response = self.client.get('/picture')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Random photo', response.data)


class TestConfigIntegration(unittest.TestCase):
    """Integration tests for configuration"""

    def test_config_loading(self):
        """Test configuration loading and validation"""
        config = Config()
        config.album_id = "test_album"
        config.weather_api_key = "test_key"

        # Config should validate successfully with required fields
        try:
            config.validate()
        except Exception as e:
            self.fail(f"Config validation failed: {e}")

    def test_config_environment_variables(self):
        """Test configuration from environment variables"""
        with patch.dict(os.environ, {'PIFRAME_ALBUM_ID': 'env_album_id'}):
            config = Config.load()
            # Environment variable should override default
            self.assertEqual(config.album_id, 'env_album_id')


if __name__ == '__main__':
    unittest.main()
