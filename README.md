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

Python 3.11 or newer is required. Python 3.14 is the development default;
CI covers Python 3.11–3.15.

1. **Create virtual environment**:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
python -m pip install --require-hashes -r requirements.txt
```

For development and tests, install `requirements-dev.txt` instead. It includes
the same locked runtime dependencies plus coverage and formatting tools.

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

Normal runs (`python app.py` and `./scripts/start.sh`) use Waitress, a production
WSGI server. `--debug` uses Flask's development server and debugger instead.
The configured log directory is created automatically on first startup.

After pulling updates, activate the virtual environment and run
`python -m pip install --require-hashes -r requirements.txt` before restarting.
`start.sh` does not install dependencies, so an already configured frame can
start without access to the package index.


## Existing OAuth tokens

Normal startup never opens a browser or waits for an OAuth callback. For new or
revoked credentials, explicitly run `python scripts/authenticate.py` on a machine
with a browser. The callback listens only on loopback and times out after three
minutes. For SSH setup, forward local port 8085 to the frame's loopback port 8085
and run the command on the frame with `--no-browser`, then open its printed URL
in the forwarded browser session. Keep the same Google Drive client credentials.
Transient refresh failures retain the saved token and require no new login.

Runtime credentials are now JSON in `config/credentials/token.json`, with a
private directory and owner-only file permissions. Runtime never unpickles data.
For a legacy token whose origin and integrity you trust, migrate it explicitly:

```bash
python scripts/migrate_token.py --trust-local-pickle
```

The command preserves the original pickle and refuses to overwrite an existing
JSON token. Custom legacy `*.pickle` token paths resolve to a `credentials/`
JSON sibling directory; pass the matching source/destination to the command.
Custom JSON destinations must be inside a private directory (0700 on Unix).

## Image resource budgets

Defaults cap a download at 16 MiB, retained download payloads at 32 MiB, an image
at 24 million pixels, and EXIF input at 1 MiB. JPEG, PNG, GIF, BMP and WebP are
accepted; unsupported or oversized images are not served. Google file size is
checked before media download, chunks are at most 1 MiB, and the output buffer
rejects excess bytes. Concurrent cold reads reuse a completed cached download.
These limits can be set in config JSON with `max_download_bytes`,
`download_cache_max_bytes`, `max_image_pixels`, and `max_metadata_bytes`.
The byte cache budget measures payloads, not Python/process overhead. Metadata
work is byte-limited; it is not executed in a sandbox with a CPU time limit.

## Dependency updates

`requirements.in` declares runtime inputs and security minimums;
`requirements.txt` locks the complete dependency tree with distribution hashes.
`requirements-dev.txt` adds test and formatting tools using the same runtime pins.
Generated environment markers select compatible packages for Python 3.11–3.15.

To update both lockfiles with uv:

```bash
uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes --upgrade -o requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.11 --generate-hashes --upgrade -o requirements-dev.txt
python -m pip install --require-hashes -r requirements-dev.txt
python -m pip check
python -m unittest discover -s tests -v
```

The end-to-end test runs a local HTTP server with real application services,
image/EXIF parsing, and chart rendering. Only the external Drive and weather API
transports use fixture responses, so tests need no credentials or API quota.
Verify live API access separately on the configured frame after updating.
Raspberry Pi installations should use a supported Python and a 64-bit OS to
benefit from upstream Linux ARM64 wheels; 32-bit systems may need source builds.

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
│   ├── credentials/token.json      # Private OAuth token (gitignored)
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

### Raspberry Pi 1 / ARMv6, Bookworm deployment

Use `requirements-pi-bookworm.txt` for 32-bit Raspberry Pi OS Bookworm and
CPython 3.11. It retains the universal lock's versions, selects explicit
[piwheels](https://www.piwheels.org/faq.html) binary artifacts for native packages,
and requires SHA256 hashes. Pure packages use hashed PyPI wheels. Source builds
are disabled. This profile does **not** apply to Trixie/Python 3.13 or 64-bit OSes.
`deployment/pi-bookworm-artifacts.json` records artifact provenance and OS packages.
Regenerate with `venv/bin/python scripts/lock_pi.py` after changing the universal
lock, then review the artifact hashes and OS dependencies.

On the Pi, after updating this checkout (preserve your local config/credentials):

```bash
cd ~/piframe
python3.11 -c 'import json; print(" ".join(json.load(open("deployment/pi-bookworm-artifacts.json"))["apt_packages"]))'
# Install exactly the package names printed above with sudo apt install.
/usr/bin/python3.11 scripts/deploy_pi.py prepare
# Run the activation command printed only after installation and smoke tests pass.
```

Preparation leaves the running service and its environment alone. Activation
requires the existing `piframe.service` to run this checkout's `scripts/start.sh`;
it switches `venv-current` atomically, restarts the service, and checks a real
photo plus native image/chart processing. Failure restores the previous environment
and restarts it. Keep the old environment and SD backup until you have checked
the physical display and a reboot. Rollback changes the environment only, not
application code, configuration, or OS packages. Neither installation nor hardware
operation is proven by tests on a development Mac; run preparation and activation
on the Pi before considering this deployment verified.

### Raspberry Pi 1 / ARMv6, Trixie deployment

Use `requirements-pi-trixie.txt` and `deployment/pi-trixie-artifacts.json` on
32-bit Raspberry Pi OS Trixie with CPython 3.13. The deployment script selects
the matching lock from the OS version and interpreter, rejecting mismatched
combinations. Bookworm's CPython 3.11 environment is not a Trixie environment;
create a new candidate instead of modifying or deleting it.

After the OS upgrade has completed and the Pi has rebooted successfully:

```bash
cd ~/piframe
python3.13 --version
python3.13 -c 'import json; print(" ".join(json.load(open("deployment/pi-trixie-artifacts.json"))["apt_packages"]))'
# Install exactly the package names printed above with sudo apt install --no-install-recommends.
/usr/bin/python3.13 scripts/deploy_pi.py prepare
# Run the activation command printed after all preparation checks pass.
```

Regenerate this profile with `venv/bin/python scripts/lock_pi.py --profile trixie`.
The default profile remains Bookworm. Both profiles derive their versions and
Python markers from `requirements.txt`; native wheels must match the profile's
CPython ABI and ARMv6 platform. Installation is hash checked and binary only.
The manifest records the system libraries required by those actual artifacts,
including Trixie's `t64` package names. Image codecs and their shared libraries
are needed for headless image processing; no desktop or display server is required.

Activation first checks that the previous environment can still run its native
smoke test. If the OS migration broke it, normal activation refuses to proceed.
With a full SD-card backup available, explicitly opt out of environment rollback:

```bash
/usr/bin/python3.13 scripts/deploy_pi.py activate /absolute/path/printed/by/prepare --allow-no-rollback
```

With this flag, a failed live check stops the service and retains the candidate
for diagnosis if no working old environment exists. It cannot roll back the OS.
Without the flag, a failed activation restores the verified previous environment.
The existing service must execute `scripts/start.sh`; inspect it using
`systemctl cat piframe.service`. Keep configuration and Google credentials in place.
After activation, check `systemctl status piframe.service` and
`journalctl -u piframe.service -n 80 --no-pager`, exercise the photo and weather
pages from another computer, then reboot and verify automatic startup.
Real ARMv6 imports, Google authentication, live weather and reboot behavior must
be verified on the Pi; development-host tests cannot establish hardware readiness.

### Consistent photo snapshots

Image metadata returns an opaque `/random-picture/snapshots/<token>` URL bound to
exact image bytes and metadata, even if another viewer selects a different photo
or Drive changes the source file. Fetching that URL does not call Drive. Retention
is bounded by `snapshot_cache_size` (4), `snapshot_cache_max_bytes` (32 MiB,
including serialized metadata), and `snapshot_cache_ttl` (300 seconds). Expired or
evicted URLs return 404; request new metadata to obtain a new snapshot. Legacy
synchronized endpoints still serve the latest retained snapshot.

### Browser refresh regression checks

The photo page owns one refresh controller and keeps a decoded photo visible
through failed or timed-out replacements. Weather HTML and charts refresh from
memory-only endpoints; the background worker prepares chart updates.

The optional browser suite uses actual templates and JavaScript with fixture
responses (no Google or weather credentials): install `playwright@1.65.1` into a
temporary npm prefix, install its Chromium browser, and run
`NODE_PATH=<prefix>/node_modules node tests/browser/frame.cjs` from the repository.
Set `PIFRAME_TEST_PYTHON` if the test interpreter is not `venv/bin/python`, and
`PLAYWRIGHT_CHROMIUM_EXECUTABLE` to use an existing Chromium binary.

### Fresh versus retained cache data

Ordinary cache reads return fresh entries only. Expired weather, forecast, and
Drive file lists can remain retained for explicit outage fallback, bounded by
`weather_stale_max_age` (1 hour), `forecast_stale_max_age` (3 hours), and
`files_stale_max_age` (24 hours). These are total ages since the last successful
cache write, not extensions renewed on each stale read. Cached-only photo weather
may use the same bounded fallback. Cleanup removes entries when retention ends;
entry-count and byte budgets still apply throughout. In-memory ages use a
monotonic clock so wall-clock adjustments cannot extend their lifetime.

### Offline photo checkpoints

After a valid live photo, the frame periodically checkpoints its bytes and
metadata to `state/last-photo.bin`. This private directory/file uses modes
0700/0600. One bounded container is flushed and atomically replaced, so an
interrupted write preserves the previous checkpoint. SHA256, schema, album ID,
MIME, byte/pixel limits, and a decoded image frame are checked before reuse.
No credentials or executable serialized objects are stored in this file.

A fresh process serves a valid checkpoint before contacting Drive, so a stalled
network cannot block its initial photo. Subsequent refreshes try live data while
the browser retains the displayed photo. Fallback does not renew the saved timestamp. Defaults:

- `last_photo_enabled`: true; set false to disable disk persistence and reuse.
- `last_photo_file`: `state/last-photo.bin` (parent directory must be private).
- `last_photo_max_age`: 604800 seconds (7 days), measured using the system clock.
- `last_photo_write_interval`: 300 seconds; at most one successful checkpoint
  per five minutes per process, limiting SD writes. It may therefore be older
  than the currently displayed photo.

Corrupt, oversized, expired, future-dated, or different-album checkpoints are
ignored. Correct system time is required for age checks, especially after an
offline Pi reboot. The image/metadata budgets also apply to checkpoints. Storage
failures are logged without interrupting live photo serving. Already displayed
photos and already-issued snapshot URLs follow their existing browser/retention
behavior; this age policy controls reading the durable fallback.
