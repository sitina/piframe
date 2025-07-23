# PiFrame Migration Guide

## Quick Fix for Existing Installations

Your existing scripts should now work! The refactored code maintains backward compatibility:

### ✅ Working Commands

```bash
# Original scripts still work
./start.sh                    # Uses new CLI
./start-install.sh           # Uses new CLI

# Flask run still works  
flask run --host=0.0.0.0 --port=81

# New CLI with more options
python app.py --host=0.0.0.0 --port=81
python app.py --debug --no-background
python app.py --log-level DEBUG
```

### 🔧 What Changed

- **app.py**: Now uses clean service architecture
- **Configuration**: Enhanced with environment variable support
- **Logging**: Proper structured logging instead of print()
- **Caching**: Thread-safe with automatic cleanup
- **Error Handling**: Better resilience and fallback strategies

### 🔄 What Stayed the Same

- **All API endpoints**: Same URLs and responses
- **Templates**: No changes needed
- **Config file**: Your existing config.json works
- **Dependencies**: Same requirements.txt
- **Deployment**: Same systemd service files work

### 🚀 New Features Available

```bash
# Environment variables (great for Docker/production)
export PIFRAME_ALBUM_ID="your-drive-folder-id"
export PIFRAME_WEATHER_API_KEY="your-api-key"
export PIFRAME_WEATHER_LOCATION="Your City"
python app.py

# Better logging
python app.py --log-level DEBUG

# Disable background tasks for testing
python app.py --no-background

# Custom config file
python app.py --config /path/to/custom-config.json
```

### 📊 Monitoring

The new architecture provides better monitoring:
- Structured logging in piframe.log
- Cache statistics available
- Background task status monitoring
- Performance metrics with execution timing

### 🆘 Troubleshooting

If something doesn't work:

1. **Check logs**: `tail -f piframe.log`
2. **Test config**: The app validates config on startup
3. **Fallback**: The original app_original.py is preserved as backup
4. **Debug mode**: Use `--debug` flag for detailed output

### 💡 Recommended Next Steps

1. **Test the new version**: Start with `--no-background` first
2. **Check logs**: Monitor piframe.log for any issues  
3. **Try environment variables**: Better for production deployments
4. **Update systemd**: Consider updating service files to use new CLI options