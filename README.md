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

⚠️ **Important**: The application currently has a simplified configuration. You need to set up your Google Drive album ID manually.

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
  "album": "YOUR_GOOGLE_DRIVE_FOLDER_ID",
  "weather_api_key": "your_openweathermap_api_key",
  "weather_location": "Your City, Country"
}
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
  "album": "your_google_drive_folder_id",
  "weather_api_key": "your_openweathermap_api_key",
  "weather_location": "City, Country",
  "background_refresh_interval": 300,
  "error_retry_interval": 60,
  "frontend_refresh_interval": 30
}
```

### Configuration Options

#### Required Settings

- **`album`**: Your Google Drive folder ID containing the photos
- **`weather_api_key`**: Your OpenWeatherMap API key (optional, for weather features)
- **`weather_location`**: Your location for weather data (optional, e.g., "Prague, CZ")

#### Optional Settings

- **`background_refresh_interval`** (default: 300 seconds = 5 minutes): How often weather data is refreshed in the background
- **`error_retry_interval`** (default: 60 seconds = 1 minute): How long to wait before retrying on background refresh errors  
- **`frontend_refresh_interval`** (default: 30 seconds): How often the fullscreen view automatically refreshes to show new images

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

## Performance Optimizations

- **Enhanced Caching**: Weather data cached for 10 minutes
- **Background Tasks**: Automatic weather data refresh
- **Memory Management**: Automatic cleanup and limits
- **Network Optimization**: Connection pooling and timeouts
- **Matplotlib Optimization**: Non-interactive backend

## Monitoring

Monitor performance with:
```bash
python monitor_performance.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## Directory Structure

The project is organized with the following clean structure:

```
piframe/
├── app.py                          # Main application
├── setup.py                        # Interactive configuration
├── requirements.txt                # Python dependencies
├── config/                         # All configuration files
│   ├── config.json                 # Main app configuration
│   ├── client_secret.json          # Google API credentials
│   ├── token.pickle                # OAuth token
│   └── systemd/                    # Systemd service files
├── scripts/                        # All executable scripts
│   ├── run_tests.py               # Test runner
│   ├── start-install.sh           # Quick setup script
│   ├── start.sh                   # Start script
│   └── test_*.py                  # Individual test scripts
├── logs/                           # All log files
│   ├── piframe.log                # Main application logs
│   └── performance/               # Performance logs
├── docs/                          # Documentation
├── legacy/                        # Legacy/backup files
├── piframe/                       # Main Python package
├── tests/                         # Test suite
├── templates/                     # Flask templates
└── static/                        # Static assets
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.