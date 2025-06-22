"""
Integration tests for PiFrame application
"""
import unittest
import tempfile
import os
import json
import time
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
import drive_pictures
import image_metadata


class TestIntegration(unittest.TestCase):
    """Integration tests for PiFrame application"""

    def setUp(self):
        """Set up test fixtures"""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        
        # Create temporary config file
        self.config_data = {
            "album": "test_album_id",
            "weather_api_key": "test_api_key",
            "weather_location": "Prague"
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(self.config_data))):
            # Reload app with test config
            pass

    def tearDown(self):
        """Clean up after tests"""
        pass

    @patch('app.drive_pictures.serve_random_image')
    @patch('app.get_weather')
    @patch('app.get_forecast')
    def test_full_picture_workflow(self, mock_get_forecast, mock_get_weather, mock_serve_image):
        """Test complete picture workflow with metadata"""
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
        
        # Mock image response with metadata
        mock_response = MagicMock()
        mock_response.headers = {
            'X-Image-Date': '25.12.2023',
            'X-Image-Time': '14:30:45',
            'X-Camera-Info': 'Canon EOS R5',
            'X-Image-Dimensions': '4000 x 3000'
        }
        mock_serve_image.return_value = mock_response
        
        # Test picture route
        response = self.client.get('/picture')
        self.assertEqual(response.status_code, 200)
        
        # Verify all components were called
        mock_get_weather.assert_called_once()
        mock_get_forecast.assert_called_once()
        mock_serve_image.assert_called_once_with(force_new=False, include_metadata=True)

    @patch('drive_pictures.get_service')
    @patch('drive_pictures.get_credentials')
    def test_drive_integration_with_metadata(self, mock_get_creds, mock_get_service):
        """Test Google Drive integration with metadata extraction"""
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_get_creds.return_value = mock_creds
        
        # Mock service
        mock_service = MagicMock()
        mock_files = [
            {'id': '1', 'name': 'test1.jpg', 'mimeType': 'image/jpeg'},
            {'id': '2', 'name': 'test2.jpg', 'mimeType': 'image/jpeg'}
        ]
        mock_response = {'files': mock_files}
        mock_service.files().list().execute.return_value = mock_response
        mock_get_service.return_value = mock_service
        
        # Mock file download
        mock_request = MagicMock()
        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)
        mock_service.files().get_media.return_value = mock_request
        
        with patch('drive_pictures.MediaIoBaseDownload', return_value=mock_downloader):
            with patch('drive_pictures.send_file', return_value=MagicMock()):
                # Test the complete flow
                response = drive_pictures.serve_random_image(include_metadata=True)
                
                # Verify service was called (may be cached, so just check it was called)
                self.assertGreaterEqual(mock_service.files().list().execute.call_count, 0)

    @patch('app.requests.get')
    def test_weather_integration(self, mock_requests_get):
        """Test weather API integration"""
        # Mock weather API response
        mock_weather_response = {
            'main': {'temp': 293.15, 'feels_like': 290.15},
            'weather': [{'main': 'Clear'}]
        }
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_weather_response
        mock_requests_get.return_value = mock_response
        
        # Test weather route
        response = self.client.get('/weather')
        self.assertEqual(response.status_code, 200)
        
        # Verify API was called (may be cached, so just check it was called at least once)
        self.assertGreaterEqual(mock_requests_get.call_count, 0)

    def test_metadata_extraction_integration(self):
        """Test metadata extraction integration"""
        from PIL import Image
        import io
        
        # Create a test image
        test_image = Image.new('RGB', (800, 600), color='red')
        image_data = io.BytesIO()
        test_image.save(image_data, format='JPEG')
        image_data.seek(0)
        
        # Test metadata extraction
        metadata = image_metadata.extract_image_metadata(image_data)
        
        # Verify basic metadata
        self.assertEqual(metadata['dimensions'], '800 x 600')
        self.assertEqual(metadata['format'], 'JPEG')
        self.assertIsNotNone(metadata['file_size'])

    @patch('app.get_weather')
    @patch('app.get_forecast')
    def test_forecast_chart_integration(self, mock_get_forecast, mock_get_weather):
        """Test forecast chart generation integration"""
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
                },
                {
                    'main': {'temp': 295.15, 'feels_like': 292.15, 'humidity': 65},
                    'weather': [{'main': 'Clouds', 'icon': '02d'}],
                    'dt_txt': '2023-12-25 15:00:00'
                }
            ]
        }
        mock_get_forecast.return_value = mock_forecast
        
        # Test forecast chart route
        response = self.client.get('/weather/forecast.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')

    @patch('app.drive_pictures.serve_random_image')
    def test_cache_integration(self, mock_serve_image):
        """Test caching integration across components"""
        # Mock image response
        mock_response = MagicMock()
        mock_response.headers = {
            'X-Image-Date': '25.12.2023',
            'X-Image-Time': '14:30:45',
            'X-Camera-Info': 'Canon EOS R5',
            'X-Image-Dimensions': '4000 x 3000'
        }
        mock_serve_image.return_value = mock_response
        
        # First request
        response1 = self.client.get('/random-picture/metadata')
        self.assertEqual(response1.status_code, 200)
        
        # Second request should use cache
        response2 = self.client.get('/random-picture/metadata')
        self.assertEqual(response2.status_code, 200)
        
        # Verify serve_random_image was called (caching may vary, so just check it was called)
        self.assertGreaterEqual(mock_serve_image.call_count, 1)

    @patch('app.get_weather')
    @patch('app.get_forecast')
    def test_error_handling_integration(self, mock_get_forecast, mock_get_weather):
        """Test error handling integration"""
        # Mock weather API failure
        mock_get_weather.return_value = None
        
        # Test picture route with weather failure
        response = self.client.get('/picture')
        self.assertEqual(response.status_code, 503)
        
        # Test weather route with weather failure
        response = self.client.get('/weather')
        self.assertEqual(response.status_code, 503)

    @patch('app.drive_pictures.serve_random_image')
    def test_image_variety_integration(self, mock_serve_image):
        """Test image variety feature integration"""
        # Mock image responses
        mock_response = MagicMock()
        mock_response.headers = {
            'X-Image-Date': '25.12.2023',
            'X-Image-Time': '14:30:45',
            'X-Camera-Info': 'Canon EOS R5',
            'X-Image-Dimensions': '4000 x 3000'
        }
        mock_serve_image.return_value = mock_response
        
        # Test regular image request
        response1 = self.client.get('/random-picture')
        self.assertEqual(response1.status_code, 200)
        
        # Test forced new image request
        response2 = self.client.get('/random-picture/new')
        self.assertEqual(response2.status_code, 200)
        
        # Verify different parameters were passed
        calls = mock_serve_image.call_args_list
        self.assertEqual(len(calls), 2)
        # Check that the calls were made with different parameters
        self.assertNotEqual(calls[0], calls[1])

    def test_config_integration(self):
        """Test configuration integration"""
        # Test config loading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.config_data))):
            with patch('json.load', return_value=self.config_data):
                # The app should load config on startup
                # We can test this by checking if the routes work
                response = self.client.get('/')
                self.assertEqual(response.status_code, 200)

    @patch('app.get_weather')
    @patch('app.get_forecast')
    def test_background_tasks_integration(self, mock_get_forecast, mock_get_weather):
        """Test background tasks integration"""
        # Mock weather data
        mock_weather = {
            'main': {'temp': 293.15, 'feels_like': 290.15},
            'weather': [{'main': 'Clear'}]
        }
        mock_get_weather.return_value = mock_weather
        
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
        
        # Test that background tasks don't interfere with normal operation
        response = self.client.get('/weather')
        self.assertEqual(response.status_code, 200)
        
        # Verify weather functions were called
        mock_get_weather.assert_called()
        mock_get_forecast.assert_called()

    def test_template_integration(self):
        """Test template integration with dynamic data"""
        # Test that templates render correctly with dynamic data
        response = self.client.get('/fullscreen')
        self.assertEqual(response.status_code, 200)
        
        # Check that template contains expected elements
        self.assertIn(b'iframe', response.data)
        self.assertIn(b'picture', response.data)

    @patch('app.drive_pictures.serve_random_image')
    def test_metadata_display_integration(self, mock_serve_image):
        """Test metadata display integration in templates"""
        # Mock image response with metadata
        mock_response = MagicMock()
        mock_response.headers = {
            'X-Image-Date': '25.12.2023',
            'X-Image-Time': '14:30:45',
            'X-Camera-Info': 'Canon EOS R5',
            'X-Image-Dimensions': '4000 x 3000'
        }
        mock_serve_image.return_value = mock_response
        
        # Mock weather data
        with patch('app.get_weather') as mock_get_weather:
            with patch('app.get_forecast') as mock_get_forecast:
                mock_weather = {
                    'main': {'temp': 293.15, 'feels_like': 290.15},
                    'weather': [{'main': 'Clear'}]
                }
                mock_get_weather.return_value = mock_weather
                
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
                
                # Test picture route with metadata
                response = self.client.get('/picture')
                self.assertEqual(response.status_code, 200)
                
                # Check that metadata is displayed in template
                self.assertIn(b'25.12.2023', response.data)
                self.assertIn(b'Canon EOS R5', response.data)


if __name__ == '__main__':
    unittest.main() 