"""
Tests for main Flask application (refactored architecture)
"""
import unittest
import json
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock, Mock
from flask import Flask, Response

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import PiFrameApp, create_app, main
from piframe.config import Config
from piframe.models import get_cache_manager


class TestPiFrameApp(unittest.TestCase):
    """Test cases for PiFrameApp class"""

    @unittest.skipIf(Flask is None, "Flask not available")
    def setUp(self):
        """Set up test fixtures"""
        # Create a minimal config for testing
        self.config = Config()
        self.config.album_id = "test_album_id"
        self.config.weather_api_key = "test_key"
        self.config.secret_key = "test_secret_key"
        
        # Mock services to avoid actual API calls
        self.mock_weather_service = MagicMock()
        self.mock_drive_service = MagicMock()
        self.mock_image_service = MagicMock()

        with patch('app.create_services') as mock_create_services, \
             patch('app.get_cache_manager'):
            mock_create_services.return_value = (
                self.mock_weather_service,
                self.mock_drive_service,
                self.mock_image_service
            )
            self.app = PiFrameApp(self.config)
            self.app.app.config['TESTING'] = True
            self.client = self.app.app.test_client()

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'app'):
            self.app.close()

    def test_init(self):
        """Test PiFrameApp initialization"""
        self.assertIsNotNone(self.app.app)
        self.assertEqual(self.app.config, self.config)
        self.assertIsNotNone(self.app.weather_service)
        self.assertIsNotNone(self.app.drive_service)
        self.assertIsNotNone(self.app.image_service)

    def test_setup_flask_config(self):
        """Test Flask configuration setup"""
        self.assertEqual(self.app.app.config['SECRET_KEY'], self.config.secret_key)
        self.assertEqual(self.app.app.config['SEND_FILE_MAX_AGE_DEFAULT'], 
                        self.config.flask_file_cache_max_age)

    def test_home_route(self):
        """Test home route redirects to fullscreen"""
        with patch.object(self.app, 'get_fullscreen') as mock_get:
            mock_get.return_value = Response('<html>', status=200)
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
            mock_get.assert_called_once()

    def test_fullscreen_route(self):
        """Test fullscreen route"""
        with patch.object(self.app, 'get_fullscreen') as mock_get:
            mock_get.return_value = Response('<html>', status=200)
            response = self.client.get('/fullscreen')
            self.assertEqual(response.status_code, 200)
            mock_get.assert_called_once()

    def test_get_fullscreen(self):
        """Test get_fullscreen method"""
        with patch('app.render_template') as mock_render:
            mock_render.return_value = "rendered template"
            result = self.app.get_fullscreen()
            mock_render.assert_called_once_with(
                'fullscreen.html',
                refresh_interval=self.config.frontend_refresh_interval
            )

    def test_weather_route(self):
        """Test weather route"""
        with patch.object(self.app, 'get_weather') as mock_get:
            mock_get.return_value = Response('<html>', status=200)
            response = self.client.get('/weather')
            self.assertEqual(response.status_code, 200)
            mock_get.assert_called_once()

    def test_get_weather_success(self):
        """Test get_weather with successful data"""
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
        
        self.app.weather_service.get_current_weather.return_value = mock_weather
        self.app.weather_service.get_forecast.return_value = mock_forecast
        self.app.weather_service.process_forecast_data.return_value = [
            {'temp': 20.0, 'feels_like': 17.0, 'weather': 'Clear', 'time': '14'}
        ]
        self.app.weather_service.to_celsius.return_value = 20.0
        
        with patch('app.render_template') as mock_render:
            mock_render.return_value = "rendered template"
            result = self.app.get_weather()
            mock_render.assert_called_once()
            call_kwargs = mock_render.call_args[1]
            self.assertEqual(call_kwargs['temperature'], 20.0)
            self.assertEqual(call_kwargs['weather_type'], 'Clear')

    def test_get_weather_no_data(self):
        """Test get_weather when weather data is unavailable"""
        self.app.weather_service.get_current_weather.return_value = None

        result = self.app.get_weather()
        # When weather data is unavailable, the app returns a 503 Response
        self.assertEqual(result.status_code, 503)

    def test_picture_route(self):
        """Test picture route"""
        with patch.object(self.app, 'get_picture') as mock_get:
            mock_get.return_value = Response('<html>', status=200)
            response = self.client.get('/picture')
            self.assertEqual(response.status_code, 200)
            mock_get.assert_called_once()

    def test_get_picture_success(self):
        """Test get_picture with successful data"""
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
        
        self.app.weather_service.get_current_weather.return_value = mock_weather
        self.app.weather_service.get_forecast.return_value = mock_forecast
        self.app.weather_service.process_forecast_data.return_value = [
            {'temp': 20.0, 'feels_like': 17.0, 'weather': 'Clear', 'time': '14'}
        ]
        self.app.weather_service.to_celsius.return_value = 20.0
        
        with patch('app.render_template') as mock_render:
            mock_render.return_value = "rendered template"
            result = self.app.get_picture()
            mock_render.assert_called_once()
            call_kwargs = mock_render.call_args[1]
            self.assertEqual(call_kwargs['temperature'], 20.0)
            self.assertEqual(call_kwargs['weather_type'], 'Clear')
            self.assertTrue(call_kwargs['weather_available'])
            self.assertEqual(
                call_kwargs['refresh_interval'],
                self.config.frontend_refresh_interval
            )

    def test_get_picture_no_weather(self):
        """Test get_picture renders without weather data."""
        self.app.weather_service.get_current_weather.return_value = None

        with patch('app.render_template') as mock_render:
            mock_render.return_value = "rendered template"
            result = self.app.get_picture()

            self.assertEqual(result, "rendered template")
            mock_render.assert_called_once()
            call_kwargs = mock_render.call_args[1]
            self.assertFalse(call_kwargs['weather_available'])
            self.assertEqual(call_kwargs['weather_type'], 'Unavailable')
            self.assertEqual(call_kwargs['forecast'], [])
            self.assertEqual(
                call_kwargs['refresh_interval'],
                self.config.frontend_refresh_interval
            )

    def test_get_picture_malformed_weather_falls_back(self):
        """Test malformed weather data does not block the photo view."""
        self.app.weather_service.get_current_weather.return_value = {'main': {}}

        with patch('app.render_template') as mock_render:
            mock_render.return_value = "rendered template"
            result = self.app.get_picture()

            self.assertEqual(result, "rendered template")
            call_kwargs = mock_render.call_args[1]
            self.assertFalse(call_kwargs['weather_available'])
            self.assertEqual(call_kwargs['forecast'], [])

    def test_random_picture_route(self):
        """Test random picture route"""
        mock_response = Response(b'image_data', status=200, mimetype='image/jpeg')
        self.app.image_service.serve_random_image.return_value = mock_response

        response = self.client.get('/random-picture')
        self.assertEqual(response.status_code, 200)
        self.app.image_service.serve_random_image.assert_called_once_with()

    def test_new_random_picture_route(self):
        """Test new random picture route"""
        mock_response = Response(b'image_data', status=200, mimetype='image/jpeg')
        self.app.image_service.serve_random_image.return_value = mock_response

        response = self.client.get('/random-picture/new')
        self.assertEqual(response.status_code, 200)
        self.app.image_service.serve_random_image.assert_called_once_with(force_new=True)

    def test_random_picture_metadata_route(self):
        """Test random picture metadata route"""
        mock_metadata = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45',
            'camera_info': 'Canon EOS R5',
            'dimensions': '4000 x 3000'
        }
        self.app.image_service.get_random_image_metadata.return_value = mock_metadata
        
        response = self.client.get('/random-picture/metadata')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['creation_date'], '25.12.2023')
        self.app.image_service.get_random_image_metadata.assert_called_once()

    def test_synchronized_random_picture_route(self):
        """Test synchronized random picture route"""
        mock_response = Response(b'image_data', status=200, mimetype='image/jpeg')
        self.app.image_service.serve_synchronized_image.return_value = mock_response

        response = self.client.get('/random-picture/synchronized')
        self.assertEqual(response.status_code, 200)
        self.app.image_service.serve_synchronized_image.assert_called_once()

    def test_synchronized_metadata_route(self):
        """Test synchronized metadata route"""
        mock_metadata = {
            'creation_date': '25.12.2023',
            'image_id': 'test_id',
            'is_synchronized': True
        }
        self.app.image_service.get_synchronized_metadata.return_value = mock_metadata
        
        response = self.client.get('/random-picture/synchronized-metadata')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['creation_date'], '25.12.2023')
        self.app.image_service.get_synchronized_metadata.assert_called_once()

    def test_forecast_chart_route_success(self):
        """Test forecast chart route with successful generation"""
        mock_chart_data = b'fake_png_data'
        self.app.weather_service.generate_forecast_chart.return_value = mock_chart_data
        
        response = self.client.get('/weather/forecast.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')
        self.assertEqual(response.data, mock_chart_data)

    def test_forecast_chart_route_failure(self):
        """Test forecast chart route when generation fails"""
        self.app.weather_service.generate_forecast_chart.return_value = None
        
        response = self.client.get('/weather/forecast.png')
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Chart generation failed', response.data)

    def test_status_route(self):
        """Test status route returns safe local diagnostics."""
        self.app.cache_manager.get_all_stats.return_value = {
            'files': {'valid_entries': 1},
            'weather': {'valid_entries': 0},
            'forecast': {'valid_entries': 0},
            'chart': {'valid_entries': 0}
        }

        response = self.client.get('/status')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn(data['status'], ['ready', 'needs_setup'])
        self.assertTrue(data['photos']['album_configured'])
        self.assertFalse(data['weather']['location_configured'])
        self.assertEqual(
            data['config']['frontend_refresh_interval'],
            self.config.frontend_refresh_interval
        )
        self.assertNotIn('weather_api_key', response.get_data(as_text=True))

    def test_start_background_tasks(self):
        """Test starting background tasks"""
        with patch('app.create_standard_tasks') as mock_create:
            mock_manager = MagicMock()
            mock_create.return_value = mock_manager
            
            self.app.start_background_tasks(enabled=True)
            
            mock_create.assert_called_once_with(
                self.app.weather_service,
                self.app.drive_service,
                self.app.image_service,
                self.config
            )
            mock_manager.start_all.assert_called_once()
            self.assertEqual(self.app.task_manager, mock_manager)

    def test_start_background_tasks_disabled(self):
        """Test starting background tasks when disabled"""
        self.app.start_background_tasks(enabled=False)
        self.assertIsNone(self.app.task_manager)

    def test_stop_background_tasks(self):
        """Test stopping background tasks"""
        mock_manager = MagicMock()
        self.app.task_manager = mock_manager
        
        self.app.stop_background_tasks()
        
        mock_manager.stop_all.assert_called_once()

    def test_stop_background_tasks_no_manager(self):
        """Test stopping background tasks when no manager exists"""
        self.app.task_manager = None
        # Should not raise an exception
        self.app.stop_background_tasks()

    def test_close(self):
        """Test application cleanup"""
        mock_manager = MagicMock()
        self.app.task_manager = mock_manager
        
        self.app.weather_service.close = MagicMock()
        self.app.drive_service.close = MagicMock()
        self.app.image_service.close = MagicMock()
        
        self.app.close()
        
        mock_manager.stop_all.assert_called_once()
        self.app.weather_service.close.assert_called_once()
        self.app.drive_service.close.assert_called_once()
        self.app.image_service.close.assert_called_once()

    def test_run(self):
        """Test running the Flask application"""
        with patch.object(self.app.app, 'run') as mock_run:
            self.app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
            mock_run.assert_called_once_with(
                host='127.0.0.1',
                port=5000,
                debug=False,
                threaded=True,
                use_reloader=False
            )

    def test_run_with_defaults(self):
        """Test running with default host/port from config"""
        with patch.object(self.app.app, 'run') as mock_run:
            self.app.run(debug=False, use_reloader=False)
            mock_run.assert_called_once_with(
                host=self.config.default_host,
                port=self.config.default_port,
                debug=False,
                threaded=True,
                use_reloader=False
            )

    def test_run_keyboard_interrupt(self):
        """Test handling KeyboardInterrupt during run"""
        with patch.object(self.app.app, 'run', side_effect=KeyboardInterrupt()):
            with patch.object(self.app, 'close') as mock_close:
                self.app.run(debug=False, use_reloader=False)
                mock_close.assert_called_once()

    def test_run_exception(self):
        """Test handling exceptions during run"""
        test_exception = Exception("Test error")
        with patch.object(self.app.app, 'run', side_effect=test_exception):
            with patch.object(self.app, 'close') as mock_close:
                with self.assertRaises(Exception) as context:
                    self.app.run(debug=False, use_reloader=False)
                self.assertEqual(str(context.exception), "Test error")
                mock_close.assert_called_once()


class TestCreateApp(unittest.TestCase):
    """Test cases for create_app function"""

    @unittest.skipIf(Flask is None, "Flask not available")
    def setUp(self):
        """Set up test fixtures"""
        self.config_path = 'config/config.json'

    @unittest.skipIf(Flask is None, "Flask not available")
    @patch('app.Config')
    @patch('app.setup_logging')
    @patch('app.PiFrameApp')
    def test_create_app_success(self, mock_app_class, mock_setup_logging, mock_config_class):
        """Test successful app creation"""
        mock_config = MagicMock()
        mock_config.log_file = 'logs/piframe.log'
        mock_config_class.load.return_value = mock_config
        
        mock_piframe_app = MagicMock()
        mock_piframe_app.app = Flask(__name__)
        mock_app_class.return_value = mock_piframe_app
        
        app = create_app(self.config_path, start_background_tasks=False)
        
        self.assertIsNotNone(app)
        mock_config_class.load.assert_called_once_with(self.config_path)
        mock_setup_logging.assert_called_once()
        mock_app_class.assert_called_once_with(mock_config)
        mock_piframe_app.start_background_tasks.assert_not_called()

    @unittest.skipIf(Flask is None, "Flask not available")
    @patch('app.Config')
    @patch('app.setup_logging')
    @patch('app.PiFrameApp')
    def test_create_app_with_background_tasks(self, mock_app_class, mock_setup_logging, mock_config_class):
        """Test app creation with background tasks"""
        mock_config = MagicMock()
        mock_config.log_file = 'logs/piframe.log'
        mock_config_class.load.return_value = mock_config
        
        mock_piframe_app = MagicMock()
        mock_piframe_app.app = Flask(__name__)
        mock_app_class.return_value = mock_piframe_app
        
        app = create_app(self.config_path, start_background_tasks=True)
        
        mock_piframe_app.start_background_tasks.assert_called_once_with(enabled=True)

    @unittest.skipIf(Flask is None, "Flask not available")
    @patch('app.Config')
    def test_create_app_config_error(self, mock_config_class):
        """Test app creation with config error"""
        mock_config_class.load.side_effect = Exception("Config error")
        
        with self.assertRaises(Exception):
            create_app(self.config_path)


class TestMainFunction(unittest.TestCase):
    """Test cases for main() function"""

    @unittest.skipIf(Flask is None, "Flask not available")
    @patch('app.argparse.ArgumentParser')
    @patch('app.Config')
    @patch('app.setup_logging')
    @patch('app.PiFrameApp')
    @patch('app.signal.signal')
    def test_main_success(self, mock_signal, mock_app_class, mock_setup_logging, 
                          mock_config_class, mock_parser_class):
        """Test successful main execution"""
        # Setup mocks
        mock_args = MagicMock()
        mock_args.config = 'config/config.json'
        mock_args.port = None
        mock_args.host = None
        mock_args.debug = False
        mock_args.no_background = False
        mock_args.log_level = 'INFO'
        
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        mock_config = MagicMock(spec=Config)
        mock_config.album_id = "test_album"
        mock_config.log_file = 'logs/piframe.log'
        mock_config.default_port = 5001
        mock_config.default_host = "0.0.0.0"
        mock_config.validate.return_value = True
        mock_config_class.load.return_value = mock_config

        mock_piframe_app = MagicMock()
        mock_piframe_app.app = Flask(__name__)
        mock_app_class.return_value = mock_piframe_app

        result = main()

        self.assertEqual(result, 0)
        mock_config_class.load.assert_called_once()
        mock_config.validate.assert_called_once()
        mock_setup_logging.assert_called_once()
        mock_piframe_app.start_background_tasks.assert_called_once_with(enabled=True)
        mock_piframe_app.run.assert_called_once()

    @unittest.skipIf(Flask is None, "Flask not available")
    @patch('app.argparse.ArgumentParser')
    @patch('app.Config')
    @patch('app.setup_logging')
    @patch('app.PiFrameApp')
    def test_main_validation_failure(self, mock_app_class, mock_setup_logging,
                                     mock_config_class, mock_parser_class):
        """Test main stops when configuration validation fails."""
        mock_args = MagicMock()
        mock_args.config = 'config/config.json'

        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser

        mock_config = MagicMock(spec=Config)
        mock_config.validate.return_value = False
        mock_config_class.load.return_value = mock_config

        result = main()

        self.assertEqual(result, 1)
        mock_setup_logging.assert_not_called()
        mock_app_class.assert_not_called()

    @unittest.skipIf(Flask is None, "Flask not available")
    @patch('app.argparse.ArgumentParser')
    @patch('app.Config')
    def test_main_config_error(self, mock_config_class, mock_parser_class):
        """Test main with configuration error"""
        mock_args = MagicMock()
        mock_args.config = 'config/config.json'
        
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        mock_config_class.load.side_effect = Exception("Config error")
        
        with patch('logging.basicConfig'):
            result = main()
            self.assertEqual(result, 1)

    @unittest.skipIf(Flask is None, "Flask not available")
    @patch('app.argparse.ArgumentParser')
    @patch('app.Config')
    @patch('app.setup_logging')
    @patch('app.PiFrameApp')
    @patch('app.signal.signal')
    def test_main_with_custom_port(self, mock_signal, mock_app_class, mock_setup_logging,
                                    mock_config_class, mock_parser_class):
        """Test main with custom port"""
        mock_args = MagicMock()
        mock_args.config = 'config/config.json'
        mock_args.port = 8080
        mock_args.host = None
        mock_args.debug = False
        mock_args.no_background = False
        mock_args.log_level = 'INFO'
        
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        mock_config = MagicMock(spec=Config)
        mock_config.album_id = "test_album"
        mock_config.log_file = 'logs/piframe.log'
        mock_config.default_port = 5001
        mock_config.default_host = "0.0.0.0"
        mock_config.validate.return_value = True
        mock_config_class.load.return_value = mock_config
        
        mock_piframe_app = MagicMock()
        mock_piframe_app.app = Flask(__name__)
        mock_app_class.return_value = mock_piframe_app
        mock_piframe_app.run = MagicMock()
        
        result = main()
        
        self.assertEqual(result, 0)
        self.assertEqual(mock_config.default_port, 8080)

    @unittest.skipIf(Flask is None, "Flask not available")
    @patch('app.argparse.ArgumentParser')
    @patch('app.Config')
    @patch('app.setup_logging')
    @patch('app.PiFrameApp')
    @patch('app.signal.signal')
    def test_main_no_background_tasks(self, mock_signal, mock_app_class, mock_setup_logging,
                                      mock_config_class, mock_parser_class):
        """Test main with background tasks disabled"""
        mock_args = MagicMock()
        mock_args.config = 'config/config.json'
        mock_args.port = None
        mock_args.host = None
        mock_args.debug = False
        mock_args.no_background = True
        mock_args.log_level = 'INFO'
        
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        mock_config = MagicMock(spec=Config)
        mock_config.album_id = "test_album"
        mock_config.log_file = 'logs/piframe.log'
        mock_config.default_port = 5001
        mock_config.default_host = "0.0.0.0"
        mock_config.validate.return_value = True
        mock_config_class.load.return_value = mock_config
        
        mock_piframe_app = MagicMock()
        mock_piframe_app.app = Flask(__name__)
        mock_app_class.return_value = mock_piframe_app
        mock_piframe_app.run = MagicMock()
        
        result = main()
        
        self.assertEqual(result, 0)
        mock_piframe_app.start_background_tasks.assert_called_once_with(enabled=False)


if __name__ == '__main__':
    unittest.main()
