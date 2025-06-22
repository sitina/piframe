"""
Tests for main Flask application
"""
import unittest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


class TestApp(unittest.TestCase):
    """Test cases for Flask application"""

    def setUp(self):
        """Set up test fixtures"""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        
        # Reset global variables
        app.config['DEBUG'] = False

    def tearDown(self):
        """Clean up after tests"""
        pass

    def test_home_route(self):
        """Test home route redirects to fullscreen"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_fullscreen_route(self):
        """Test fullscreen route"""
        response = self.client.get('/fullscreen')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'iframe', response.data)

    @patch('app.get_weather')
    @patch('app.get_forecast')
    def test_weather_route_success(self, mock_get_forecast, mock_get_weather):
        """Test weather route with successful data"""
        # Mock weather data
        mock_weather = {
            'main': {'temp': 293.15, 'feels_like': 290.15},
            'weather': [{'main': 'Clear'}]
        }
        mock_get_weather.return_value = mock_weather
        
        # Mock forecast data
        mock_forecast = {
            'list': [
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                }
            ]
        }
        mock_get_forecast.return_value = mock_forecast
        
        response = self.client.get('/weather')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Clear', response.data)

    @patch('app.get_weather')
    def test_weather_route_no_data(self, mock_get_weather):
        """Test weather route with no weather data"""
        mock_get_weather.return_value = None
        
        response = self.client.get('/weather')
        self.assertEqual(response.status_code, 503)

    @patch('app.get_weather')
    @patch('app.get_forecast')
    @patch('app.drive_pictures.serve_random_image')
    def test_picture_route_success(self, mock_serve_image, mock_get_forecast, mock_get_weather):
        """Test picture route with successful data"""
        # Mock weather data
        mock_weather = {
            'main': {'temp': 293.15, 'feels_like': 290.15},
            'weather': [{'main': 'Clear'}]
        }
        mock_get_weather.return_value = mock_weather
        
        # Mock forecast data
        mock_forecast = {
            'list': [
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                }
            ]
        }
        mock_get_forecast.return_value = mock_forecast
        
        # Mock image response
        mock_response = MagicMock()
        mock_response.headers = {
            'X-Image-Date': '25.12.2023',
            'X-Image-Time': '14:30:45',
            'X-Camera-Info': 'Canon EOS R5',
            'X-Image-Dimensions': '4000 x 3000'
        }
        mock_serve_image.return_value = mock_response
        
        response = self.client.get('/picture')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'25.12.2023', response.data)

    @patch('app.get_weather')
    @patch('app.get_forecast')
    @patch('app.drive_pictures.serve_random_image')
    def test_picture_route_with_timestamp(self, mock_serve_image, mock_get_forecast, mock_get_weather):
        """Test picture route with timestamp parameter"""
        # Mock weather data
        mock_weather = {
            'main': {'temp': 293.15, 'feels_like': 290.15},
            'weather': [{'main': 'Clear'}]
        }
        mock_get_weather.return_value = mock_weather
        
        # Mock forecast data
        mock_forecast = {
            'list': [
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                }
            ]
        }
        mock_get_forecast.return_value = mock_forecast
        
        # Mock image response
        mock_response = MagicMock()
        mock_response.headers = {
            'X-Image-Date': '25.12.2023',
            'X-Image-Time': '14:30:45',
            'X-Camera-Info': 'Canon EOS R5',
            'X-Image-Dimensions': '4000 x 3000'
        }
        mock_serve_image.return_value = mock_response
        
        response = self.client.get('/picture?t=1234567890')
        self.assertEqual(response.status_code, 200)
        # Should use /random-picture/new route
        mock_serve_image.assert_called_with(force_new=True, include_metadata=True)

    @patch('app.get_weather')
    def test_picture_route_no_weather(self, mock_get_weather):
        """Test picture route with no weather data"""
        mock_get_weather.return_value = None
        
        response = self.client.get('/picture')
        self.assertEqual(response.status_code, 503)

    @patch('app.drive_pictures.serve_random_image')
    def test_random_picture_route(self, mock_serve_image):
        """Test random picture route"""
        mock_response = MagicMock()
        mock_serve_image.return_value = mock_response
        
        with app.test_request_context():
            response = self.client.get('/random-picture')
            self.assertEqual(response.status_code, 200)

    @patch('app.drive_pictures.serve_random_image')
    def test_random_picture_new_route(self, mock_serve_image):
        """Test random picture new route"""
        mock_response = MagicMock()
        mock_serve_image.return_value = mock_response
        
        with app.test_request_context():
            response = self.client.get('/random-picture/new')
            self.assertEqual(response.status_code, 200)
            mock_serve_image.assert_called_with(force_new=True)

    @patch('app.drive_pictures.serve_random_image')
    def test_random_picture_metadata_route(self, mock_serve_image):
        """Test random picture metadata route"""
        mock_response = MagicMock()
        mock_response.headers = {
            'X-Image-Date': '25.12.2023',
            'X-Image-Time': '14:30:45',
            'X-Camera-Info': 'Canon EOS R5',
            'X-Image-Dimensions': '4000 x 3000'
        }
        mock_serve_image.return_value = mock_response
        
        response = self.client.get('/random-picture/metadata')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['creation_date'], '25.12.2023')
        self.assertEqual(data['creation_time'], '14:30:45')
        self.assertEqual(data['camera_info'], 'Canon EOS R5')

    @patch('app.get_forecast')
    @patch('app.create_figure')
    def test_forecast_chart_route(self, mock_create_figure, mock_get_forecast):
        """Test forecast chart route"""
        # Mock forecast data with more complete data
        mock_forecast = {
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
                },
                {
                    'main': {'temp': 297.15, 'feels_like': 294.15, 'humidity': 70},
                    'weather': [{'main': 'Rain', 'icon': '10d'}],
                    'dt_txt': '2023-12-25 16:00:00'
                }
            ]
        }
        mock_get_forecast.return_value = mock_forecast
        
        # Mock the entire chart generation process
        with patch('app.FigureCanvas') as mock_canvas_class:
            mock_canvas = MagicMock()
            mock_canvas.print_png.return_value = b'fake_png_data'
            mock_canvas_class.return_value = mock_canvas
            
            # Mock figure
            mock_fig = MagicMock()
            mock_create_figure.return_value = mock_fig
            
            response = self.client.get('/weather/forecast.png')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'image/png')

    def test_to_celsius(self):
        """Test temperature conversion to Celsius"""
        from app import to_celsius
        
        # Test conversion
        self.assertEqual(to_celsius(273.15), 0.0)  # 0°C
        self.assertEqual(to_celsius(293.15), 20.0)  # 20°C
        self.assertEqual(to_celsius(373.15), 100.0)  # 100°C

    def test_process_forecast(self):
        """Test forecast data processing"""
        from app import process_forecast
        
        forecast_data = {
            'list': [
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                }
            ]
        }
        
        result = process_forecast(forecast_data)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['temp'], 20.0)
        self.assertEqual(result[0]['feels_like'], 17.0)
        self.assertEqual(result[0]['weather'], 'Clear')
        self.assertEqual(result[0]['time'], '14')

    def test_process_forecast_empty_data(self):
        """Test forecast processing with empty data"""
        from app import process_forecast
        
        result = process_forecast({})
        self.assertEqual(result, [])
        
        result = process_forecast(None)
        self.assertEqual(result, [])

    @patch('app.weather_api_key', 'test_key')
    @patch('app.weather_location', 'Prague')
    @patch('app.requests.get')
    def test_get_weather_with_cache(self, mock_get):
        """Test weather retrieval with cache"""
        from app import get_weather, weather_cache
        
        # Reset cache
        weather_cache['ts'] = 0
        weather_cache['data'] = None
        
        # Mock successful weather data
        mock_weather = {
            'main': {'temp': 293.15, 'feels_like': 290.15},
            'weather': [{'main': 'Clear'}]
        }
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_weather
        mock_get.return_value = mock_response
        
        # First call should fetch from API
        result = get_weather()
        self.assertEqual(result, mock_weather)
        
        # Second call should use cache
        result = get_weather()
        self.assertEqual(result, mock_weather)
        
        # Should only call API once
        mock_get.assert_called_once()

    @patch('app.weather_api_key', 'test_key')
    @patch('app.requests.get')
    def test_get_forecast_with_cache(self, mock_get):
        """Test forecast retrieval with cache"""
        from app import get_forecast, weather_cache
        
        # Reset cache
        weather_cache['forecast_ts'] = 0
        weather_cache['forecast'] = None
        
        # Mock successful forecast data
        mock_forecast = {
            'list': [
                {
                    'main': {'temp': 293.15, 'feels_like': 290.15, 'humidity': 60},
                    'weather': [{'main': 'Clear', 'icon': '01d'}],
                    'dt_txt': '2023-12-25 14:00:00'
                }
            ]
        }
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_forecast
        mock_get.return_value = mock_response
        
        # First call should fetch from API
        result = get_forecast()
        self.assertEqual(result, mock_forecast)
        
        # Second call should use cache
        result = get_forecast()
        self.assertEqual(result, mock_forecast)
        
        # Should only call API once
        mock_get.assert_called_once()


if __name__ == '__main__':
    unittest.main() 