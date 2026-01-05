# PiFrame

A Flask-based digital photo frame application that displays random photos from Google Drive along with weather information. Optimized for Raspberry Pi deployment.

## Features

- **Photo Display**: Random photos from Google Drive albums
- **Weather Information**: Current weather and forecast with charts
- **Image Metadata**: Display photo creation date, camera info, and dimensions
- **Performance Optimized**: Enhanced caching and background tasks for Raspberry Pi
- **Image Variety**: Different images on each refresh
- **Responsive Design**: Works on tablets, phones, and desktop

## Current Status

✅ **Fully Functional**: The application has been completely refactored with a clean modular architecture. All features are working with proper configuration management and error handling.

## Quick Start

1. **Clone and setup**:
```bash
git clone <repository-url>
cd piframe
./scripts/start-install.sh
```

2. **Configure your settings** (choose one method):

   **Option A: Interactive setup** (recommended):
   ```bash
   python setup.py
   ```

   **Option B: Manual configuration**:
   - Edit `config/config.json` and add your Google Drive folder ID:
```json
{
  "album_id": "YOUR_GOOGLE_DRIVE_FOLDER_ID",
  "weather_api_key": "your_openweathermap_api_key",
  "weather_location": "Your City, Country"
}
```

   **Option C: Environment variables** (production recommended):
   ```bash
   export PIFRAME_ALBUM_ID="YOUR_GOOGLE_DRIVE_FOLDER_ID"
   export PIFRAME_WEATHER_API_KEY="your_openweathermap_api_key"
   export PIFRAME_WEATHER_LOCATION="Your City, Country"
   ```

3. **Get your Google Drive folder ID** (if doing manual setup):
   - Open Google Drive in your browser
   - Navigate to the folder containing your photos
   - Copy the URL from the address bar
   - The folder ID is the long string after `/folders/` in the URL
   - Example: `https://drive.google.com/drive/folders/1ABC123DEF456GHI789JKL`
   - Folder ID: `1ABC123DEF456GHI789JKL`

4. **Access the application**:
   - Open http://localhost:81 in your browser

## Installation

### Prerequisites

1. **Google Drive API Setup**:
   - Create a project in [Google Cloud Console](https://console.developers.google.com/)
   - Enable Google Drive API
   - Create OAuth 2.0 credentials
   - Download as `config/client_secret.json` to the config directory

2. **OpenWeatherMap API** (optional):
   - Get free API key from [OpenWeatherMap](https://openweathermap.org/api)
   - Add to `config/config.json`

### Automated Setup

```bash
./scripts/start-install.sh
```

This script will:
- Create virtual environment
- Install dependencies
- Start the application on port 81

### Manual Setup

1. **Create virtual environment**:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure the application**:
   - **Option A**: Use the interactive setup script: `python setup.py`
   - **Option B**: Manually edit `config/config.json` with your settings
   - Ensure `config/client_secret.json` is in the config directory

4. **Run the application**:
```bash
# Development mode
python app.py --debug

# Production mode (default)
python app.py

# Custom port
python app.py --port 8080
```

## Configuration

### Quick Setup

For interactive configuration, use the setup script:
```bash
python setup.py
```

This will guide you through setting up all required configuration options.

### Manual Configuration

Create or edit `config/config.json`:

```json
{
  "album_id": "your_google_drive_folder_id",
  "weather_api_key": "your_openweathermap_api_key",
  "weather_location": "City, Country",
  "background_refresh_interval": 300,
  "error_retry_interval": 60,
  "frontend_refresh_interval": 30,
  "weather_cache_ttl": 600,
  "forecast_cache_ttl": 1800,
  "chart_cache_ttl": 3600
}
```

### Configuration Options

#### Required Settings

- **`album_id`**: Your Google Drive folder ID containing the photos (legacy: `album`)
- **`weather_api_key`**: Your OpenWeatherMap API key (optional, for weather features)
- **`weather_location`**: Your location for weather data (optional, e.g., "Prague, CZ")

#### Optional Settings

**Background Task Settings:**
- **`background_refresh_interval`** (default: 300 seconds = 5 minutes): How often weather data is refreshed in the background
- **`error_retry_interval`** (default: 60 seconds = 1 minute): How long to wait before retrying on background refresh errors  
- **`preload_interval`** (default: 900 seconds = 15 minutes): How often images are preloaded
- **`preload_error_retry_interval`** (default: 300 seconds = 5 minutes): Retry interval for image preload errors

**Cache Settings (TTL in seconds):**
- **`weather_cache_ttl`** (default: 600 = 10 minutes): Weather data cache duration
- **`forecast_cache_ttl`** (default: 1800 = 30 minutes): Forecast data cache duration
- **`chart_cache_ttl`** (default: 3600 = 1 hour): Chart image cache duration
- **`files_cache_ttl`** (default: 3600 = 1 hour): Drive file listing cache duration
- **`download_cache_ttl`** (default: 60 = 1 minute): Image download cache duration

**Frontend Settings:**
- **`frontend_refresh_interval`** (default: 30 seconds): How often the fullscreen view automatically refreshes to show new images

**Cache Size Settings:**
- **`download_cache_size`** (default: 5): Number of images to keep in download cache
- **`metadata_cache_size`** (default: 20): Number of metadata entries to cache

**Server Settings:**
- **`default_host`** (default: "0.0.0.0"): Host to bind server to
- **`default_port`** (default: 5001): Port to run server on

### Environment Variables

All configuration options can be overridden using environment variables (recommended for production):

- `PIFRAME_ALBUM_ID` - Google Drive folder ID
- `PIFRAME_WEATHER_API_KEY` - Weather API key
- `PIFRAME_WEATHER_LOCATION` - Weather location
- `PIFRAME_WEATHER_LAT` - Weather latitude (float)
- `PIFRAME_WEATHER_LON` - Weather longitude (float)
- `PIFRAME_HOST` - Server host
- `PIFRAME_PORT` - Server port (integer)
- `PIFRAME_SECRET_KEY` - Flask secret key

### Finding Your Google Drive Folder ID

1. Open Google Drive in your browser
2. Navigate to the folder containing your photos
3. Copy the URL from the address bar
4. The folder ID is the long string after '/folders/' in the URL
   - Example: `https://drive.google.com/drive/folders/1ABC123DEF456GHI789JKL`
   - The folder ID would be: `1ABC123DEF456GHI789JKL`

## Usage

### Access Points

- **Main view**: http://localhost:5001 (default) or http://localhost:81 (when using start-install.sh)
- **Weather view**: http://localhost:5001/weather
- **Picture view**: http://localhost:5001/picture
- **Fullscreen**: http://localhost:5001/fullscreen

### Command Line Options

```bash
# Development mode
python app.py --debug

# Custom port
python app.py --port 8080

# Custom host
python app.py --host 127.0.0.1

# Disable background tasks (for testing)
python app.py --no-background
```

### System Service (Linux/Raspberry Pi)

```bash
sudo cp piframe-optimized.service /etc/systemd/system/
sudo systemctl enable piframe-optimized
sudo systemctl start piframe-optimized
```

## API Endpoints

- `/` - Home page (redirects to fullscreen)
- `/fullscreen` - Fullscreen photo display
- `/picture` - Photo display with weather overlay
- `/weather` - Weather information only
- `/random-picture` - Serve random image
- `/random-picture/new` - Force new random image
- `/random-picture/metadata` - Get image metadata as JSON
- `/random-picture/synchronized` - Get synchronized random image (for metadata consistency)
- `/random-picture/synchronized-metadata` - Get synchronized image metadata
- `/weather/forecast.png` - Weather forecast chart

## Testing

### Run all tests with coverage:
```bash
python scripts/run_tests.py
```

### Run specific test categories:
```bash
# Unit tests only
python scripts/run_tests.py --unit-only

# Integration tests only  
python scripts/run_tests.py --integration-only

# Performance tests only
python scripts/run_tests.py --performance-only
```

### Test Google Drive connection:
```bash
python scripts/test_drive_connection.py
```

## Troubleshooting

### Common Issues

1. **Images not loading**:
   - **Check virtual environment**: Ensure you're using the virtual environment with dependencies installed
     ```bash
     source venv/bin/activate  # Activate virtual environment
     pip install -r requirements.txt  # Install dependencies if missing
     ```
   - Check that `album` field is set in `config/config.json`
   - Verify the folder ID is correct
   - Ensure you have access to the Google Drive folder
   - Check that `config/client_secret.json` is valid

2. **Weather not showing**:
   - Verify `weather_api_key` is set in `config/config.json`
   - Check that the API key is valid
   - Ensure `weather_location` is correctly formatted

3. **Port conflicts**:
   - Default port is 5001, but `scripts/start-install.sh` uses port 81
   - Change port using `python app.py --port 8080`
   - Or modify `scripts/start-install.sh` to use a different port

4. **Google Drive API errors**:
   - Verify `config/client_secret.json` exists and is valid
   - Check that Google Drive API is enabled in your Google Cloud project
   - Ensure OAuth consent screen is configured

5. **Module import errors** (e.g., "No module named 'flask'", "No module named 'requests'"):
   - This indicates dependencies are not installed
   - Activate virtual environment and install requirements:
     ```bash
     source venv/bin/activate
     pip install -r requirements.txt
     python app.py  # Should work now
     ```
   - If no virtual environment exists, create one:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     pip install -r requirements.txt
     ```

### Debug Mode

Run with debug mode to see detailed error messages:
```bash
python app.py --debug
```

### Logs

Check the application logs:
```bash
tail -f logs/piframe.log
```

## Architecture

PiFrame uses a clean, modular architecture with proper separation of concerns:

### Core Components

- **Service Layer Pattern**: Business logic separated into focused services
  - `WeatherService` - Weather API calls, data processing, chart generation
  - `DriveService` - Google Drive authentication, file operations, caching
  - `ImageService` - Image serving, metadata extraction, Flask responses

- **Centralized Configuration**: Single source of truth with environment variable support
- **Advanced Caching**: Thread-safe TTL cache with automatic cleanup
- **Background Task Management**: Coordinated background operations with error handling
- **Dependency Injection**: Clean service initialization and resource management

### Performance Optimizations

- **Enhanced Caching**: Multi-layer caching with configurable TTLs
- **Background Tasks**: Automatic data refresh and image preloading
- **Memory Management**: Automatic cleanup and size limits
- **Network Optimization**: Connection pooling and timeouts
- **Error Resilience**: Comprehensive error handling with fallback to cached data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## Directory Structure

The project follows a clean, modular architecture:

```
piframe/
├── app.py                          # Main Flask application
├── setup.py                        # Interactive configuration setup
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Build configuration
├── CLAUDE.md                       # Development guidance
├── config/                         # Configuration files
│   ├── config.json                 # Main app configuration
│   ├── client_secret.json          # Google API credentials (gitignored)
│   ├── token.pickle                # OAuth token (gitignored)
│   └── systemd/                    # Systemd service files
├── piframe/                        # Main Python package
│   ├── config/
│   │   └── settings.py             # Centralized configuration management
│   ├── services/
│   │   ├── weather_service.py      # Weather API + caching + charts
│   │   ├── drive_service.py        # Google Drive operations
│   │   └── image_service.py        # Image serving + metadata
│   ├── models/
│   │   └── cache.py                # Centralized TTL cache management
│   ├── background/
│   │   └── tasks.py                # Background task coordination
│   └── utils/
│       └── logging.py              # Centralized logging framework
├── scripts/                        # Utility scripts
│   ├── run_tests.py               # Test runner with coverage
│   ├── start-install.sh           # Quick setup script
│   ├── test_drive_connection.py   # Drive connection tester
│   └── test_*.py                  # Individual test scripts
├── tests/                          # Comprehensive test suite
│   ├── test_*.py                  # Unit and integration tests
│   └── __init__.py
├── logs/                           # Log files (gitignored)
│   ├── piframe.log                # Main application logs
│   └── performance/               # Performance monitoring logs
├── docs/                           # Project documentation
├── templates/                      # Flask templates
├── static/                         # Static web assets
└── htmlcov/                        # Test coverage reports (gitignored)
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.