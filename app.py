"""
Refactored PiFrame Flask application.
Clean separation of concerns using service architecture.
"""

import argparse
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
        self.app.config['SECRET_KEY'] = 'piframe-secret-key'  # Should be from config in production
        self.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300  # 5 minutes cache
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
    
    def get_fullscreen(self):
        """Render fullscreen template."""
        return render_template('fullscreen.html', 
                             refresh_interval=self.config.frontend_refresh_interval)
    
    def get_weather(self):
        """Render weather template."""
        weather_data = self.weather_service.get_current_weather()
        if not weather_data:
            return Response("Weather data unavailable", status=503, mimetype='text/plain')
        
        forecast_data = self.weather_service.get_forecast()
        forecast = self.weather_service.process_forecast_data(forecast_data) if forecast_data else []
        
        temperature = self.weather_service.to_celsius(weather_data['main']['temp'])
        feels_like = self.weather_service.to_celsius(weather_data['main']['feels_like'])
        weather_type = weather_data['weather'][0]['main']
        
        return render_template(
            'weather.html',
            temperature=temperature,
            feels_like=feels_like,
            weather_type=weather_type,
            forecast=forecast[:6]  # First 6 items
        )
    
    def get_picture(self):
        """Render picture template with weather overlay."""
        weather_data = self.weather_service.get_current_weather()
        if not weather_data:
            return Response("Weather data unavailable", status=503, mimetype='text/plain')
        
        forecast_data = self.weather_service.get_forecast()
        forecast = self.weather_service.process_forecast_data(forecast_data) if forecast_data else []
        
        temperature = self.weather_service.to_celsius(weather_data['main']['temp'])
        feels_like = self.weather_service.to_celsius(weather_data['main']['feels_like'])
        weather_type = weather_data['weather'][0]['main']
        
        return render_template(
            'picture.html',
            temperature=temperature,
            feels_like=feels_like,
            weather_type=weather_type,
            forecast=forecast[:6]  # First 6 items
        )
    
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
    parser.add_argument('--config', type=str, default='config.json',
                       help='Configuration file path (default: config.json)')
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
        config.validate()
    except Exception as e:
        print(f"Configuration error: {e}")
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
def create_app(config_path='config.json', start_background_tasks=False):
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
        print(f"Failed to create app: {e}")
        raise


# Create default app instance for flask run (without background tasks)
# Background tasks will be started by flask run environment
app = None

def get_flask_app():
    """Lazy initialization of Flask app for flask run."""
    global app
    if app is None:
        app = create_app(start_background_tasks=False)
    return app

# For flask run compatibility
app = get_flask_app()


if __name__ == '__main__':
    sys.exit(main())