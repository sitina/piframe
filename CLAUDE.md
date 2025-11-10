# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

### Use Git Tools

- Before modifying files (understand history)
- When tests fail (check recent changes)
- Finding related code (git grep)
- Understanding features (follow evolution)
- Checking workflows (CI/CD issues)

### The Ten Universal Commandments

1. Thou shalt ALWAYS use MCP tools before coding
2. Thou shalt NEVER assume; always question
3. Thou shalt write code that's clear and obvious
4. Thou shalt be BRUTALLY HONEST in assessments
5. Thou shalt PRESERVE CONTEXT, not delete it
6. Thou shalt make atomic, descriptive commits
7. Thou shalt document the WHY, not just the WHAT
8. Thou shalt test before declaring done
9. Thou shalt handle errors explicitly
10. Thou shalt treat user data as sacred

### Final Reminders

- Codebase > Documentation > Training data (in order of truth)
- Research current docs, don't trust outdated knowledge
- Ask questions early and often
- Use slash commands for consistent workflows
- Derive documentation on-demand
- Extended thinking for complex problems
- Visual inputs for UI/UX debugging
- Test locally before pushing
- Think simple: clear, obvious, no bullshit

_Remember: Write code as if the person maintaining it is a violent psychopath who knows where you live. Make it that clear._

## Project Overview

PiFrame is a Flask-based digital photo frame application that displays random photos from Google Drive along with weather information. It's optimized for Raspberry Pi deployment but runs on any Python environment.

## Development Commands

### Setup and Installation
```bash
# Quick setup (creates venv, installs deps, runs on port 81)
./scripts/start-install.sh

# Interactive configuration
python setup.py

# Manual virtual environment setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Production mode (default port 5001)
python app.py

# Development mode with debug
python app.py --debug

# Custom port
python app.py --port 8080

# Disable background tasks (for testing)
python app.py --no-background
```

### Testing
```bash
# Run all tests with coverage
python scripts/run_tests.py

# Run specific test categories
python scripts/run_tests.py --unit-only
python scripts/run_tests.py --integration-only
python scripts/run_tests.py --performance-only

# Test Google Drive connection
python scripts/test_drive_connection.py

# Run specific test file
python scripts/run_tests.py --test-file tests/test_app.py

# Other test utilities
python scripts/test_metadata.py    # Test image metadata
python scripts/test_sync.py        # Test synchronized endpoints
```

### Code Quality
```bash
# Format code (configured in pyproject.toml)
autopep8 --recursive --in-place .

# Sort imports
isort .

# Performance monitoring
python legacy/monitor_performance.py
```

## Core Architecture (Refactored - Clean Modular Design)

### Modular Structure

The application follows a clean, modular architecture with proper separation of concerns:

```
piframe/
├── config/
│   ├── __init__.py
│   └── settings.py          # Centralized configuration management
├── services/
│   ├── __init__.py
│   ├── weather_service.py   # Weather API + caching + chart generation  
│   ├── drive_service.py     # Google Drive authentication + file operations
│   └── image_service.py     # Image serving + metadata + Flask responses
├── models/
│   ├── __init__.py
│   └── cache.py            # Centralized TTL cache management
├── background/
│   ├── __init__.py
│   └── tasks.py            # Background task coordination
└── utils/
    ├── __init__.py
    └── logging.py          # Centralized logging framework
```

### Main Components

1. **app.py** - Clean Flask app using service layer pattern
2. **PiFrameApp class** - Application orchestrator with dependency injection
3. **Service Layer** - Business logic separated into focused services
4. **Configuration** - Centralized config with environment variable support
5. **Background Tasks** - Coordinated background operations with error handling
6. **Caching** - Thread-safe TTL cache with automatic cleanup

### Key Design Patterns

**Service Layer Pattern**: Each domain has a dedicated service:
- `WeatherService` - Weather API calls, data processing, chart generation
- `DriveService` - Google Drive authentication, file operations, caching
- `ImageService` - Image serving, metadata extraction, Flask responses

**Dependency Injection**: Services are injected rather than using globals:
- Configuration passed to all services  
- Cache manager shared across services
- Clean shutdown and resource management

**Centralized Configuration**: Single source of truth with validation:
- Environment variable support (e.g., `PIFRAME_WEATHER_API_KEY`)
- Backward compatibility with existing config/config.json
- Automatic config file generation
- Configuration validation with helpful error messages

**Advanced Caching**: Thread-safe caching with TTL and LRU eviction:
- Per-service cache configuration
- Automatic expired entry cleanup
- Cache statistics and monitoring
- Memory-efficient design

**Background Task Management**: Coordinated background operations:
- Configurable intervals and error retry logic
- Graceful shutdown handling
- Task status monitoring
- Error isolation between tasks

### Configuration Structure

**Configuration System**: Centralized in `piframe/config/settings.py`

**Required settings:**
- `album_id` - Google Drive folder ID (legacy: `album` also supported)
- `drive_credentials_file` - Path to Google API credentials (default: config/client_secret.json)
- `drive_token_file` - Path to OAuth token (default: config/token.pickle)

**Optional settings:**
- `weather_api_key` - OpenWeatherMap API key
- `weather_location` - Location string for weather
- `weather_lat`, `weather_lon` - Coordinates (defaults to Prague)

**Environment Variable Support** (overrides config/config.json):
- `PIFRAME_ALBUM_ID` - Google Drive folder ID
- `PIFRAME_WEATHER_API_KEY` - Weather API key  
- `PIFRAME_WEATHER_LOCATION` - Weather location
- `PIFRAME_WEATHER_LAT`, `PIFRAME_WEATHER_LON` - Coordinates
- `PIFRAME_HOST`, `PIFRAME_PORT` - Server settings
- `PIFRAME_SECRET_KEY` - Flask secret key

**Performance Settings** (all configurable):
- Cache TTLs: weather (10min), forecast (30min), charts (1hr), files (1hr)
- Background intervals: weather refresh (5min), image preload (15min)
- Error retry intervals with exponential backoff
- Cache sizes: downloads (5), metadata (20)
- Frontend refresh interval (30s)

### API Endpoints

- `/` - Redirects to fullscreen view
- `/fullscreen` - Main photo frame view with auto-refresh
- `/picture` - Photo view with weather overlay
- `/weather` - Weather-only view with forecast
- `/random-picture` - Serve random image from Drive
- `/random-picture/new` - Force new image (bypass cache)
- `/random-picture/metadata` - Get image metadata as JSON
- `/random-picture/synchronized` - Synchronized image for metadata consistency
- `/random-picture/synchronized-metadata` - Get synchronized image and metadata
- `/weather/forecast.png` - Generated forecast chart

### Error Handling & Resilience

**Comprehensive Error Handling**:
- Service-level error isolation with fallback to cached data
- Retry logic with exponential backoff for transient failures
- Background task error recovery without affecting main application
- Graceful degradation when external services unavailable

**Logging & Monitoring**:
- Structured logging throughout all components
- Performance monitoring with execution time tracking
- Cache statistics and health monitoring
- Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Production Deployment

**Enhanced Production Support**:
- Clean shutdown handling for SIGINT/SIGTERM signals
- Resource cleanup (file handles, network connections)
- Background task coordination and shutdown
- Production Flask configuration with optimizations
- Environment variable configuration support

**Deployment Options**:
- Existing systemd service files remain compatible
- New CLI options: `--log-level`, `--config`, `--no-background`
- Docker-friendly with environment variable configuration

## Migration from Original Code

**Backward Compatibility**:
- Existing `config/config.json` files continue to work (with legacy key mapping)
- All original API endpoints preserved
- Same deployment scripts and service files remain functional
- Original code preserved in `legacy/` directory as fallbacks

**What Changed**:
- **Architecture**: Modular service-based architecture with dependency injection
- **Configuration**: Centralized config management with environment variable support
- **Caching**: Thread-safe TTL cache with automatic cleanup and size limits
- **Background Tasks**: Coordinated task management with proper error handling
- **Logging**: Structured logging with performance monitoring
- **Error Handling**: Comprehensive error handling with graceful degradation

**What Stayed the Same**:
- All API endpoints and functionality preserved
- Template structure and static files unchanged
- Google Drive integration and authentication flow
- Weather API integration and chart generation
- Image metadata extraction and serving logic
- Flask application interface (can still use `flask run`)