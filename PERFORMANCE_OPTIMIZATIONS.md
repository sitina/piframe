# PiFrame Performance Optimizations for Raspberry Pi

## Overview
This document outlines the performance optimizations implemented to make PiFrame run efficiently on Raspberry Pi hardware, ensuring smooth operation for kitchen iPad display.

## Key Optimizations Implemented

### 1. **Enhanced Caching System**
- **Weather Cache**: Extended from 5 minutes to 10-30 minutes to reduce API calls
- **Forecast Cache**: Extended to 30 minutes with chart caching for 1 hour
- **Image Cache**: Implemented 5-minute cache for downloaded images
- **File List Cache**: 1-hour cache for Google Drive file listings

### 2. **Background Tasks**
- **Weather Refresh**: Automatic background refresh every 5 minutes
- **Image Preloading**: Preloads 3 random images every 30 minutes
- **Non-blocking Operations**: All background tasks run in separate threads

### 3. **Matplotlib Optimizations**
- **Non-interactive Backend**: Uses 'Agg' backend for better performance
- **Smaller Figure Size**: Reduced from default to 8x4 inches at 72 DPI
- **Memory Management**: Explicitly closes figures to free memory
- **Optimized Rendering**: Reduced line widths and font sizes

### 4. **Network Optimizations**
- **Request Timeouts**: Added 10-15 second timeouts to prevent hanging
- **Error Handling**: Graceful fallback to cached data on API failures
- **HTTP Caching**: Added proper cache headers for images and charts

### 5. **Flask Optimizations**
- **Production Mode**: Disabled debug mode and auto-reload
- **Threading**: Enabled threaded mode for better concurrency
- **Template Caching**: Disabled template auto-reload
- **Static File Caching**: 5-minute cache for static files

### 6. **Memory Management**
- **Limited Cache Sizes**: Maximum 10 images in memory cache
- **LRU Eviction**: Automatic removal of oldest cached items
- **Resource Limits**: Systemd service with 512MB memory limit

### 7. **Google API Optimizations**
- **Service Caching**: Reuses Google API service instances
- **Credential Caching**: Caches authentication tokens
- **Batch Operations**: Optimized file listing queries

## Performance Monitoring

### Using the Monitor Script
```bash
# Monitor for 1 hour with 30-second intervals
python monitor_performance.py --duration 60 --interval 30

# Monitor for 30 minutes with 10-second intervals
python monitor_performance.py --duration 30 --interval 10
```

### Key Metrics to Watch
- **CPU Usage**: Should stay below 50% average
- **Memory Usage**: Should stay below 80% of 512MB limit
- **Temperature**: Should stay below 70°C
- **Network I/O**: Monitor for excessive API calls

## Deployment Instructions

### 1. Install Dependencies
```bash
./venv/bin/pip install -r requirements.txt
```

### 2. Configure Systemd Service
```bash
# Copy service file
sudo cp piframe-optimized.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable piframe-optimized
sudo systemctl start piframe-optimized
```

### 3. Monitor Service Status
```bash
# Check service status
sudo systemctl status piframe-optimized

# View logs
sudo journalctl -u piframe-optimized -f
```

## Expected Performance Improvements

### Before Optimization
- **API Calls**: Every 5 minutes (weather + forecast)
- **Image Loading**: Fresh download on each request
- **Chart Generation**: Real-time generation on each request
- **Memory Usage**: Unbounded growth
- **Response Time**: 2-5 seconds per request

### After Optimization
- **API Calls**: Every 10-30 minutes (reduced by 60-80%)
- **Image Loading**: 5-minute cache (reduced by 90% for repeated images)
- **Chart Generation**: 1-hour cache (reduced by 95% for repeated charts)
- **Memory Usage**: Bounded to 512MB maximum
- **Response Time**: 0.1-0.5 seconds for cached content

## Troubleshooting

### High CPU Usage
1. Check if background tasks are running properly
2. Monitor temperature and consider adding cooling
3. Reduce cache TTL values if needed

### High Memory Usage
1. Check for memory leaks in image cache
2. Reduce `DOWNLOAD_CACHE_SIZE` in drive_pictures.py
3. Monitor with `htop` or `free -h`

### Slow Image Loading
1. Check network connectivity to Google Drive
2. Verify folder_id in drive_pictures.py
3. Monitor preload task logs

### Weather Data Issues
1. Check OpenWeatherMap API key
2. Verify location settings in config.json
3. Check network connectivity

## Configuration Tuning

### Cache TTL Values (in app.py)
```python
WEATHER_CACHE_TTL = 600      # 10 minutes
FORECAST_CACHE_TTL = 1800    # 30 minutes  
CHART_CACHE_TTL = 3600       # 1 hour
```

### Image Cache Settings (in drive_pictures.py)
```python
CACHE_TTL = 3600             # 1 hour for file list
DOWNLOAD_CACHE_SIZE = 10     # Max 10 images in memory
```

### Systemd Resource Limits (in piframe-optimized.service)
```ini
MemoryMax=512M               # Max memory usage
CPUQuota=50%                 # Max CPU usage
```

## Best Practices for Raspberry Pi

1. **Use SSD**: If possible, use an SSD instead of SD card for better I/O
2. **Adequate Cooling**: Ensure proper ventilation to prevent thermal throttling
3. **Stable Power**: Use a quality power supply (5V/3A recommended)
4. **Network**: Use wired Ethernet for better stability
5. **Regular Updates**: Keep Raspberry Pi OS updated
6. **Monitoring**: Use the performance monitor script regularly

## Expected Resource Usage

### Typical Usage (Idle)
- **CPU**: 5-15%
- **Memory**: 150-250MB
- **Network**: Minimal (background refresh only)
- **Temperature**: 45-55°C

### Typical Usage (Active)
- **CPU**: 20-40% (during image loading/chart generation)
- **Memory**: 200-350MB
- **Network**: Moderate (API calls + image downloads)
- **Temperature**: 50-65°C

### Peak Usage
- **CPU**: 60-80% (during heavy operations)
- **Memory**: 400-500MB
- **Network**: High (multiple concurrent requests)
- **Temperature**: 60-70°C 