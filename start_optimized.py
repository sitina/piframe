#!/usr/bin/env python3
"""
Optimized startup script for Raspberry Pi photo frame
"""
import os
import sys
import signal
import logging
from app import app

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

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def main():
    """Main startup function with optimizations for Raspberry Pi"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Optimize for Raspberry Pi
    os.environ['FLASK_ENV'] = 'production'
    
    # Disable Flask debug mode for better performance
    app.config['DEBUG'] = False
    
    # Optimize Flask settings
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300  # 5 minutes cache
    app.config['TEMPLATES_AUTO_RELOAD'] = False
    
    logger.info("Starting PiFrame application...")
    logger.info("Optimized for Raspberry Pi performance")
    
    try:
        # Run with optimized settings for Raspberry Pi
        app.run(
            host='0.0.0.0',
            port=5001,  # Changed from 5000 to avoid macOS AirPlay conflict
            threaded=True,  # Enable threading for better performance
            debug=False,
            use_reloader=False  # Disable reloader in production
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 