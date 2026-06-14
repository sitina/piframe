"""
Refactored PiFrame Flask application.
Clean separation of concerns using service architecture.
"""

import argparse
import os
import signal
import sys
from typing import Optional

from flask import Flask, Response, render_template, jsonify

from piframe.config import Config
from piframe.utils import setup_logging, get_logger
from piframe.services import WeatherService, DriveService, ImageService
from piframe.models import get_cache_manager
from piframe.background import BackgroundTaskManager
from piframe.background.tasks import create_standard_tasks


class PiFrameApp:
    """Main PiFrame application class."""

    # Number of forecast time-slots to show in the weather overlay
    FORECAST_DISPLAY_SLOTS = 6
    
    def __init__(self, config: Config):
        """Initialize the application with configuration."""
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize Flask app
        self.app = Flask(__name__, static_folder='static')
        self._setup_flask_config()
        
        # Initialize services
        self.cache_manager = get_cache_manager(config)
        self.weather_service = WeatherService(config, self.cache_manager)
        self.drive_service = DriveService(config, self.cache_manager)
        self.image_service = ImageService(config, self.drive_service, self.cache_manager)
        
        # Background task manager (will be initialized later)
        self.task_manager: Optional[BackgroundTaskManager] = None
        
        # Register routes
        self._register_routes()
        
        self.logger.info("PiFrame application initialized")
    
    def _setup_flask_config(self) -> None:
        """Configure Flask application settings."""
        self.app.config['SECRET_KEY'] = self.config.secret_key
        self.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = self.config.flask_file_cache_max_age
        self.app.config['TEMPLATES_AUTO_RELOAD'] = False
    
    def _register_routes(self) -> None:
        """Register all Flask routes."""
        
        @self.app.route("/")
        def home():
            """Home page - redirects to fullscreen."""
            return self.get_fullscreen()
        
        @self.app.route("/fullscreen")
        def fullscreen():
            """Fullscreen photo display."""
            return self.get_fullscreen()
        
        @self.app.route("/weather")
        def weather():
            """Weather information only."""
            return self.get_weather()
        
        @self.app.route("/picture")
        def picture():
            """Photo display with weather overlay."""
            return self.get_picture()
        
        @self.app.route("/random-picture")
        def random_picture():
            """Serve a random image."""
            return self.image_service.serve_random_image()
        
        @self.app.route("/random-picture/new")
        def new_random_picture():
            """Force a new random image."""
            return self.image_service.serve_random_image(force_new=True)
        
        @self.app.route("/random-picture/metadata")
        def random_picture_metadata():
            """Get metadata for a random picture."""
            metadata = self.image_service.get_random_image_metadata()
            return jsonify(metadata)
        
        @self.app.route("/random-picture/synchronized")
        def synchronized_random_picture():
            """Get synchronized random picture (for metadata consistency)."""
            return self.image_service.serve_synchronized_image()
        
        @self.app.route("/random-picture/synchronized-metadata")
        def synchronized_metadata():
            """Get synchronized image and metadata in atomic operation."""
            return jsonify(self.image_service.get_synchronized_metadata())
        
        @self.app.route("/weather/forecast.png")
        def forecast_chart():
            """Weather forecast chart."""
            chart_data = self.weather_service.generate_forecast_chart()
            if chart_data:
                return Response(chart_data, mimetype='image/png')
            else:
                return Response("Chart generation failed", status=500, mimetype='text/plain')

        @self.app.route("/status")
        def status():
            """Local status endpoint for setup and runtime diagnostics."""
            return jsonify(self.get_status())
    
    def get_fullscreen(self):
        """Render fullscreen template."""
        return render_template('fullscreen.html',
                               refresh_interval=self.config.frontend_refresh_interval)

    def _empty_weather_context(self):
        """Return a weather context that lets the photo frame render without weather."""
        return {
            'weather_available': False,
            'temperature': None,
            'feels_like': None,
            'weather_type': 'Unavailable',
            'forecast': []
        }

    def _get_weather_context(self, require_weather: bool = True):
        """
        Get weather context data for templates.

        Args:
            require_weather: If True, return an error when weather is unavailable.
                If False, return an empty weather context so photos can still render.

        Returns:
            tuple: (context_dict, error_response) - context_dict if successful, error_response if failed
        """
        weather_data = self.weather_service.get_current_weather()
        if not weather_data:
            if not require_weather:
                return self._empty_weather_context(), None
            return None, Response("Weather data unavailable", status=503, mimetype='text/plain')

        forecast_data = self.weather_service.get_forecast()
        forecast = self.weather_service.process_forecast_data(forecast_data) if forecast_data else []

        try:
            context = {
                'weather_available': True,
                'temperature': self.weather_service.to_celsius(weather_data['main']['temp']),
                'feels_like': self.weather_service.to_celsius(weather_data['main']['feels_like']),
                'weather_type': weather_data['weather'][0]['main'],
                'forecast': forecast[:self.FORECAST_DISPLAY_SLOTS]
            }
        except (KeyError, IndexError, TypeError) as e:
            self.logger.error(f"Weather data has unexpected shape: {e}", exc_info=True)
            if not require_weather:
                return self._empty_weather_context(), None
            return None, Response("Weather data unavailable", status=503, mimetype='text/plain')

        return context, None

    def get_weather(self):
        """Render weather template."""
        context, error = self._get_weather_context(require_weather=True)
        if error:
            return error
        return render_template('weather.html', **context)

    def get_picture(self):
        """Render picture template with weather overlay."""
        context, error = self._get_weather_context(require_weather=False)
        if error:
            return error
        context['refresh_interval'] = self.config.frontend_refresh_interval
        return render_template('picture.html', **context)

    def get_status(self):
        """Return a safe local diagnostics snapshot without external network calls."""
        cache_stats = self.cache_manager.get_all_stats()
        background_tasks = []
        background_enabled = False

        if self.task_manager:
            background_enabled = self.task_manager.is_enabled()
            background_tasks = self.task_manager.get_task_status()

        photos_ready = bool(self.config.album_id) and os.path.exists(
            self.config.drive_credentials_file
        )

        return {
            'status': 'ready' if photos_ready else 'needs_setup',
            'photos': {
                'album_configured': bool(self.config.album_id),
                'drive_credentials_file_present': os.path.exists(
                    self.config.drive_credentials_file
                ),
                'drive_token_file_present': os.path.exists(
                    self.config.drive_token_file
                ),
                'cache': cache_stats.get('files', {})
            },
            'weather': {
                'configured': bool(self.config.weather_api_key),
                'location_configured': bool(self.config.weather_location),
                'current_cache': cache_stats.get('weather', {}),
                'forecast_cache': cache_stats.get('forecast', {}),
                'chart_cache': cache_stats.get('chart', {})
            },
            'background_tasks': {
                'enabled': background_enabled,
                'tasks': background_tasks
            },
            'cache': cache_stats,
            'config': {
                'frontend_refresh_interval': self.config.frontend_refresh_interval,
                'default_port': self.config.default_port
            }
        }
    
    def start_background_tasks(self, enabled: bool = True) -> None:
        """Start background tasks."""
        if enabled:
            self.task_manager = create_standard_tasks(
                self.weather_service,
                self.drive_service,
                self.image_service,
                self.config
            )
            self.task_manager.start_all()
            self.logger.info("Background tasks started")
        else:
            self.logger.info("Background tasks disabled")
    
    def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        if self.task_manager:
            self.task_manager.stop_all()
            self.logger.info("Background tasks stopped")
    
    def close(self) -> None:
        """Clean up application resources."""
        self.stop_background_tasks()
        self.weather_service.close()
        self.drive_service.close()
        self.image_service.close()
        self.logger.info("Application closed")
    
    def run(self, host: str = None, port: int = None, debug: bool = False, 
            use_reloader: bool = False) -> None:
        """Run the Flask application."""
        if host is None:
            host = self.config.default_host
        if port is None:
            port = self.config.default_port
        
        try:
            self.logger.info(f"Starting Flask server on {host}:{port} (debug: {debug})")
            self.app.run(
                host=host,
                port=port,
                debug=debug,
                threaded=True,
                use_reloader=use_reloader
            )
        except KeyboardInterrupt:
            self.logger.info("Application stopped by user")
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            raise
        finally:
            self.close()


def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='PiFrame - Digital Photo Frame with Weather')
    parser.add_argument('--config', type=str, default='config/config.json',
                       help='Configuration file path (default: config/config.json)')
    parser.add_argument('--port', type=int, help='Port to run on (overrides config)')
    parser.add_argument('--host', type=str, help='Host to bind to (overrides config)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-background', action='store_true', 
                       help='Disable background tasks')
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = Config.load(args.config)
        if not config.validate():
            return 1
    except Exception as e:
        # Logger may not be set up yet, fall back to basic logging
        import logging as _logging
        _logging.basicConfig(level=_logging.ERROR)
        _logging.error(f"Configuration error: {e}")
        return 1
    
    # Setup logging
    setup_logging(
        log_file=config.log_file,
        log_level=args.log_level,
        enable_console=True
    )
    
    logger = get_logger(__name__)
    logger.info("Starting PiFrame application")
    logger.info("Optimized modular architecture")
    
    # Override config with command line args
    if args.port:
        config.default_port = args.port
    if args.host:
        config.default_host = args.host
    
    # Create and configure application
    app = PiFrameApp(config)
    
    # Configure Flask for debug/production
    if args.debug:
        app.app.config['DEBUG'] = True
        logger.info("Running in debug mode")
    else:
        app.app.config['DEBUG'] = False
        app.app.config['TESTING'] = False
        logger.info("Running in production mode")
    
    # Setup graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        app.close()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start background tasks
    app.start_background_tasks(enabled=not args.no_background)
    
    # Run the application
    try:
        app.run(
            debug=args.debug,
            use_reloader=args.debug  # Only use reloader in debug mode
        )
        return 0
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        return 1


# Flask application factory for compatibility with 'flask run'
def create_app(config_path='config/config.json', start_background_tasks=False):
    """
    Create and configure Flask application instance.
    This function allows the app to be discovered by 'flask run'.
    
    Args:
        config_path: Path to config file
        start_background_tasks: Whether to start background tasks (default: False for flask run)
    """
    try:
        config = Config.load(config_path)
        # Setup basic logging for flask run (less verbose)
        setup_logging(
            log_file=config.log_file,
            log_level='WARNING',  # Less verbose for flask run
            enable_console=True
        )
        
        piframe_app = PiFrameApp(config)
        
        # Only start background tasks if explicitly requested
        if start_background_tasks:
            piframe_app.start_background_tasks(enabled=True)
        
        return piframe_app.app
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to create app: {e}")
        raise


# For flask run compatibility - create app instance without global state
app = create_app(start_background_tasks=False)


if __name__ == '__main__':
    sys.exit(main())
