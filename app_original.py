"""
The application serves random photo from google photos album
Optimized for Raspberry Pi performance
"""
# Standard library imports
import io
import json
import os
import pickle
import random
import time
import threading
from datetime import datetime, timedelta
from functools import wraps

# Third-party imports
from dateutil import parser
from flask import Flask, Response, render_template, request, jsonify
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for better performance
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import requests

# Local imports
import drive_pictures

# Global variables
album = ''
app = Flask(__name__, static_folder='static')

# Global synchronization for current image
_current_image_id = None
_current_image_metadata = None
_current_image_timestamp = 0

# Enhanced caching with longer TTL for Raspberry Pi
weather_cache = {
    'ts': 0, 
    'forecast_ts': 0, 
    'data': None, 
    'forecast': None,
    'forecast_chart': None,
    'forecast_chart_ts': 0
}

# Cache TTLs (in seconds) - longer for Raspberry Pi to reduce API calls
WEATHER_CACHE_TTL = 600  # 10 minutes instead of 5
FORECAST_CACHE_TTL = 1800  # 30 minutes instead of 5
CHART_CACHE_TTL = 3600  # 1 hour for chart generation

# Background task for preloading data
def background_data_refresh():
    """Background task to refresh weather data periodically"""
    while True:
        try:
            # Refresh weather data in background
            get_weather(force_refresh=True)
            get_forecast(force_refresh=True)
            time.sleep(background_refresh_interval)  # Use configured interval
        except Exception as e:
            print(f"Background refresh error: {e}")
            time.sleep(error_retry_interval)  # Use configured error retry interval

def start_background_tasks():
    """Start background tasks in separate thread"""
    refresh_thread = threading.Thread(target=background_data_refresh, daemon=True)
    refresh_thread.start()

def get_weather(force_refresh=False):
    """Get weather data with enhanced caching"""
    ts = time.time()
    if force_refresh or ts - weather_cache['ts'] > WEATHER_CACHE_TTL:
        if weather_api_key:
            try:
                weather_url = f"http://api.openweathermap.org/data/2.5/weather?appid={weather_api_key}&q={weather_location}"
                weather_data = requests.get(weather_url, timeout=10).json()
                weather_cache['ts'] = ts
                weather_cache['data'] = weather_data
                return weather_data
            except Exception as e:
                print(f"Weather API error: {e}")
                # Return cached data if available, even if expired
                if weather_cache['data']:
                    return weather_cache['data']
                return None
    return weather_cache['data']

def get_forecast(force_refresh=False):
    """Get forecast data with enhanced caching"""
    print('getting forecast')
    forecast_file = 'forecast.json'
    lon = 14.4936
    lat = 50.1267
    ts = time.time()
    
    if force_refresh or ts - weather_cache['forecast_ts'] > FORECAST_CACHE_TTL:
        if os.path.isfile(forecast_file):
            with open(forecast_file) as f:
                print('fetching weather data from file')
                data = json.load(f)
                weather_cache['forecast_ts'] = ts
                weather_cache['forecast'] = data
                return data
        elif weather_api_key:
            try:
                print('getting forecast via api')
                weather_url = f"http://api.openweathermap.org/data/2.5/forecast?appid={weather_api_key}&lat={lat}&lon={lon}"
                weather_data = requests.get(weather_url, timeout=15).json()
                weather_cache['forecast_ts'] = ts
                weather_cache['forecast'] = weather_data
                return weather_data
            except Exception as e:
                print(f"Forecast API error: {e}")
                if weather_cache['forecast']:
                    return weather_cache['forecast']
                return None
    else:
        print('using weather cache')
        return weather_cache['forecast']

@app.route("/")
def home():
    return get_fullscreen()

def to_celsius(original):
    return round(original - 273.15, 1)

def process_forecast(forecast_data):
    """Process forecast data with caching"""
    if not forecast_data or 'list' not in forecast_data:
        return []
    
    result = []
    for item in forecast_data['list']:
        temp = to_celsius(item['main']['temp'])
        feels_like = to_celsius(item['main']['feels_like'])
        humidity = item['main']['humidity']
        weather = item['weather'][0]['main']
        dt = item['dt_txt']
        tt = item['dt_txt'][11:]
        icon = '/static/images/' + item['weather'][0]['icon'] + '@2x.gif'
        result.append({
            'dt': dt,
            'temp': temp,
            'feels_like': feels_like,
            'weather': weather,
            'humidity': humidity,
            'icon': icon,
            'time': tt[:2],
        })
    return result

@app.route('/weather/forecast.png')
def plot_png():
    """Serve forecast chart with enhanced caching"""
    ts = time.time()
    if ts - weather_cache['forecast_chart_ts'] > CHART_CACHE_TTL or not weather_cache['forecast_chart']:
        try:
            fig = create_figure()
            output = io.BytesIO()
            FigureCanvas(fig).print_png(output)
            weather_cache['forecast_chart'] = output.getvalue()
            weather_cache['forecast_chart_ts'] = ts
            plt.close(fig)  # Close figure to free memory
        except Exception as e:
            print(f"Chart generation error: {e}")
            return "Chart generation failed", 500

    return Response(weather_cache['forecast_chart'], mimetype='image/png')

def create_figure():
    """Create forecast chart with optimized settings"""
    # Use smaller figure size for better performance
    fig = Figure(figsize=(8, 4), dpi=72)
    fig.patch.set_alpha(0.3)
    axis = fig.add_subplot(1, 1, 1, facecolor="none")

    forecast_data = get_forecast()
    forecast = process_forecast(forecast_data)
    
    if not forecast:
        return fig

    # Optimize data processing
    xs = [f['dt'][:13][8:] for f in forecast]
    xticks = [f['dt'][:13][11:] for f in forecast]
    ys1 = [f['temp'] for f in forecast]
    ys2 = [f['feels_like'] for f in forecast]

    axis.plot(xs, ys1, color='red', label='forecast', linewidth=1)
    axis.plot(xs, ys2, color='blue', label='feels like', linewidth=1)
    axis.legend(loc='best', fontsize=8)
    axis.set_xticks(xs)
    axis.set_xticklabels(xticks, fontsize=8)
    axis.tick_params(axis='x', rotation=90)

    # Optimize day separator lines
    for val in xs:
        if val[3:] == '00':
            axis.axvline(x=val, color='black', alpha=0.3, linewidth=0.5)

    return fig

@app.route("/weather")
def weather_view():
    """Weather view with optimized data fetching"""
    weather = get_weather()
    forecast_data = get_forecast()
    forecast = process_forecast(forecast_data)
    
    if not weather:
        return "Weather data unavailable", 503
    
    temperature = to_celsius(weather['main']['temp'])
    feels_like = to_celsius(weather['main']['feels_like'])
    weather_type = weather['weather'][0]['main']

    return render_template(
        'weather.html',
        temperature=temperature,
        feels_like=feels_like,
        weather_type=weather_type,
        forecast=forecast[:6]  # Only first 6 items
    )

@app.route("/picture")
def get_picture():
    """Picture view with optimized data fetching and metadata"""
    
    weather = get_weather()
    forecast_data = get_forecast()
    forecast = process_forecast(forecast_data)
    
    if not weather:
        return "Weather data unavailable", 503
    
    temperature = to_celsius(weather['main']['temp'])
    feels_like = to_celsius(weather['main']['feels_like'])
    weather_type = weather['weather'][0]['main']

    return render_template(
        'picture.html',
        temperature=temperature,
        feels_like=feels_like,
        weather_type=weather_type,
        forecast=forecast[:6]  # Only first 6 items
    )

@app.route("/fullscreen")
def get_fullscreen():
    return render_template('fullscreen.html', refresh_interval=frontend_refresh_interval)

@app.route("/random-picture")
def get_random_picture():
    return drive_pictures.serve_random_image()

@app.route("/random-picture/new")
def get_new_random_picture():
    """Force a new random picture by bypassing cache"""
    return drive_pictures.serve_random_image(force_new=True)

@app.route("/random-picture/metadata")
def get_random_picture_metadata():
    """Get metadata for a random picture with synchronized image data"""
    global _current_image_id, _current_image_metadata, _current_image_timestamp
    
    # Get a random image with metadata
    response = drive_pictures.serve_random_image(force_new=True, include_metadata=True)
    
    # Extract metadata from response headers
    metadata = {
        'creation_date': response.headers.get('X-Image-Date', 'Unknown'),
        'creation_time': response.headers.get('X-Image-Time', 'Unknown'),
        'camera_info': response.headers.get('X-Camera-Info', 'Unknown'),
        'dimensions': response.headers.get('X-Image-Dimensions', 'Unknown'),
        'picture_url': '/random-picture/synchronized?t=' + str(time.time())
    }
    
    # Store the current image ID and metadata for synchronization
    _current_image_id = response.headers.get('X-Image-ID', None)
    _current_image_metadata = metadata
    _current_image_timestamp = time.time()
    
    return jsonify(metadata)

@app.route("/random-picture/synchronized")
def get_synchronized_random_picture():
    """Get a random picture that is synchronized with the metadata endpoint"""
    global _current_image_id, _current_image_timestamp
    
    # If we have a current image ID and it's recent (within 5 seconds), use it
    if (_current_image_id and 
        time.time() - _current_image_timestamp < 5):
        # Serve the specific image by ID
        return drive_pictures.serve_image_by_id(_current_image_id)
    else:
        # Fall back to random image if no synchronization
        return drive_pictures.serve_random_image(force_new=False, include_metadata=False)

# Configuration loading
try:
    with open("config.json", "r") as f:
        print('loading config')
        config = json.load(f)
        album = config['album']
        weather_api_key = config['weather_api_key']
        weather_location = config['weather_location']
        
        # Load refresh intervals from config with defaults
        background_refresh_interval = config.get('background_refresh_interval', 300)  # 5 minutes default
        error_retry_interval = config.get('error_retry_interval', 60)  # 1 minute default
        frontend_refresh_interval = config.get('frontend_refresh_interval', 30)  # 30 seconds default
        
        print(album)
except FileNotFoundError:
    print('loading config failed')
    album = ''
    weather_api_key = None
    weather_location = None
    background_refresh_interval = 300  # 5 minutes default
    error_retry_interval = 60  # 1 minute default
    frontend_refresh_interval = 30  # 30 seconds default
    config = {
        "album": album,
        "weather_api_key": "",
        "weather_location": "",
        "background_refresh_interval": background_refresh_interval,
        "error_retry_interval": error_retry_interval,
        "frontend_refresh_interval": frontend_refresh_interval
    }
    config_json = json.dumps(config, indent=2)
    with open("config.json", "w") as jsonfile:
        jsonfile.write(config_json)
        print("config template written to config file")

# Start background tasks
start_background_tasks()

if __name__ == '__main__':
    """
    Optimized startup for Raspberry Pi performance
    """
    import argparse
    import logging
    import signal
    import sys
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='PiFrame - Digital Photo Frame with Weather')
    parser.add_argument('--port', type=int, default=5001, help='Port to run on (default: 5001)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-background', action='store_true', help='Disable background tasks')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('piframe.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting PiFrame application...")
    logger.info("Optimized for Raspberry Pi performance")
    
    # Graceful shutdown handler
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Disable background tasks if requested
    if args.no_background:
        logger.info("Background tasks disabled")
    else:
        logger.info("Background tasks enabled")
    
    # Configure Flask for production
    if not args.debug:
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        
        # Production optimizations
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300  # 5 minutes cache
        app.config['TEMPLATES_AUTO_RELOAD'] = False
        
        logger.info("Running in production mode")
    else:
        app.config['DEBUG'] = True
        logger.info("Running in debug mode")
    
    try:
        # Start the Flask application
        logger.info(f"Starting server on {args.host}:{args.port}")
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            threaded=True,
            use_reloader=False  # Disable reloader for production
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
