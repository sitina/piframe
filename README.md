# PiFrame

A Flask-based digital photo frame application that displays random photos from Google Drive along with weather information. Optimized for Raspberry Pi deployment.

## Features

- **Photo Display**: Random photos from Google Drive albums
- **Weather Information**: Current weather and forecast with charts
- **Image Metadata**: Display photo creation date, camera info, and dimensions
- **Performance Optimized**: Enhanced caching and background tasks for Raspberry Pi
- **Image Variety**: Different images on each refresh
- **Responsive Design**: Works on tablets, phones, and desktop

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd piframe
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up Google Drive API:
   - Create a project in Google Cloud Console
   - Enable Google Drive API
   - Create credentials (OAuth 2.0)
   - Download `credentials.json` to project root

5. Configure the application:
   - Create `config.json` with your settings:
```json
{
  "album": "your_google_drive_folder_id",
  "weather_api_key": "your_openweathermap_api_key",
  "weather_location": "Prague,CZ"
}
```

## Usage

### Development Mode
```bash
python app.py --debug
```

### Production Mode (Optimized for Raspberry Pi) - Default
```bash
python app.py
```

### Custom Port
```bash
python app.py --port 8080
```

### Disable Background Tasks (for testing)
```bash
python app.py --no-background
```

### System Service (Linux)
```bash
sudo cp piframe-optimized.service /etc/systemd/system/
sudo systemctl enable piframe-optimized
sudo systemctl start piframe-optimized
```

## Testing

The project includes a comprehensive test suite covering:

- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **Performance Tests**: Performance monitoring and optimization
- **Configuration Tests**: Config management and validation

### Running Tests

1. **Run all tests with coverage**:
```bash
python run_tests.py
```

2. **Run specific test categories**:
```bash
# Unit tests only
python run_tests.py --unit-only

# Integration tests only
python run_tests.py --integration-only

# Performance tests only
python run_tests.py --performance-only
```

3. **Run specific test file**:
```bash
python run_tests.py --test-file tests/test_app.py
```

4. **Run without coverage**:
```bash
python run_tests.py --no-coverage
```

5. **Run individual test files**:
```bash
python -m unittest tests.test_app
python -m unittest tests.test_drive_pictures
python -m unittest tests.test_image_metadata
```

### Test Coverage

The test suite provides comprehensive coverage of:
- Flask routes and error handling
- Google Drive API integration
- Image metadata extraction
- Weather API integration
- Caching mechanisms
- Performance monitoring
- Configuration management

Coverage reports are generated in HTML format in the `htmlcov/` directory.

## API Endpoints

- `/` - Home page (redirects to fullscreen)
- `/fullscreen` - Fullscreen photo display
- `/picture` - Photo display with weather overlay
- `/weather` - Weather information only
- `/random-picture` - Serve random image
- `/random-picture/new` - Force new random image
- `/random-picture/metadata` - Get image metadata as JSON
- `/weather/forecast.png` - Weather forecast chart

## Configuration

### Environment Variables
- `PIFRAME_ALBUM` - Google Drive folder ID
- `PIFRAME_WEATHER_API_KEY` - OpenWeatherMap API key
- `PIFRAME_WEATHER_LOCATION` - Weather location

### Performance Settings
- Weather cache TTL: 10 minutes
- Forecast cache TTL: 30 minutes
- Chart cache TTL: 1 hour
- Image cache TTL: 5 minutes
- Recently served images: 10 items

## Performance Optimizations

- **Enhanced Caching**: Longer TTLs for reduced API calls
- **Background Tasks**: Weather and image preloading
- **Memory Management**: Automatic cleanup and limits
- **Network Optimization**: Connection pooling and timeouts
- **Matplotlib Optimization**: Non-interactive backend
- **Resource Limits**: Systemd service with memory/CPU limits

## Monitoring

Use the performance monitoring script:
```bash
python monitor_performance.py
```

This provides:
- Memory usage tracking
- CPU usage monitoring
- Disk usage statistics
- Network usage metrics
- Performance alerts
- Trend analysis

## Troubleshooting

### Common Issues

1. **Port 5000 in use** (macOS):
   - Disable AirPlay Receiver in System Preferences
   - Or use port 5001: `python start_optimized.py --port 5001`

2. **SSL errors during image download**:
   - Check network connectivity
   - Verify Google Drive API credentials
   - Check firewall settings

3. **Weather API errors**:
   - Verify API key is valid
   - Check location format
   - Ensure API quota not exceeded

### Logs

- Application logs: `piframe.log`
- System service logs: `journalctl -u piframe-optimized`

## Development

### Code Quality

The project uses:
- **Flake8** for linting
- **Autopep8** for code formatting
- **Coverage** for test coverage
- **Unittest** for testing

### Running Linters

```bash
# Format code
autopep8 --in-place --recursive .

# Check code style
flake8 .
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs
3. Run the test suite
4. Create an issue with detailed information
