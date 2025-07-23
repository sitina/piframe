"""
Centralized configuration management for PiFrame application.
Handles loading, validation, and access to all application settings.
"""

import json
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class Config:
    """Configuration class for PiFrame application."""
    
    # Google Drive settings
    album_id: str = ""
    drive_credentials_file: str = "config/client_secret.json"
    drive_token_file: str = "config/token.pickle"
    
    # Weather settings
    weather_api_key: str = ""
    weather_location: str = ""
    weather_lat: float = 50.1267  # Default Prague coordinates
    weather_lon: float = 14.4936
    weather_file_fallback: str = "forecast.json"
    
    # Cache TTL settings (in seconds)
    weather_cache_ttl: int = 600      # 10 minutes
    forecast_cache_ttl: int = 1800    # 30 minutes
    chart_cache_ttl: int = 3600       # 1 hour
    files_cache_ttl: int = 3600       # 1 hour
    download_cache_ttl: int = 60      # 1 minute
    
    # Background task intervals (in seconds)
    background_refresh_interval: int = 300    # 5 minutes
    error_retry_interval: int = 60            # 1 minute
    preload_interval: int = 900               # 15 minutes
    preload_error_retry_interval: int = 300   # 5 minutes
    
    # Frontend settings
    frontend_refresh_interval: int = 30       # 30 seconds
    
    # Cache sizes
    download_cache_size: int = 5
    metadata_cache_size: int = 20
    
    # Server settings
    default_host: str = "0.0.0.0"
    default_port: int = 5001
    
    # File paths
    config_file: str = "config/config.json"
    log_file: str = "logs/piframe.log"
    
    @classmethod
    def load(cls, config_path: str = "config/config.json") -> 'Config':
        """
        Load configuration from file with fallback to defaults.
        Creates config file with defaults if it doesn't exist.
        """
        config = cls()
        config.config_file = config_path
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    config._update_from_dict(data)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Warning: Error loading config from {config_path}: {e}")
                print("Using default configuration")
        else:
            print(f"Config file {config_path} not found, creating with defaults")
            config.save()
        
        # Load from environment variables (overrides file config)
        config._load_from_env()
        
        return config
    
    def _update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary, handling legacy key names."""
        # Handle legacy key mappings
        key_mappings = {
            'album': 'album_id',
            'background_refresh_interval': 'background_refresh_interval',
            'error_retry_interval': 'error_retry_interval',
            'frontend_refresh_interval': 'frontend_refresh_interval',
            'preload_interval': 'preload_interval',
            'preload_error_retry_interval': 'preload_error_retry_interval'
        }
        
        for key, value in data.items():
            # Use mapped key name if available, otherwise use original
            attr_name = key_mappings.get(key, key)
            if hasattr(self, attr_name):
                setattr(self, attr_name, value)
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        env_mappings = {
            'PIFRAME_ALBUM_ID': 'album_id',
            'PIFRAME_WEATHER_API_KEY': 'weather_api_key',
            'PIFRAME_WEATHER_LOCATION': 'weather_location',
            'PIFRAME_WEATHER_LAT': ('weather_lat', float),
            'PIFRAME_WEATHER_LON': ('weather_lon', float),
            'PIFRAME_HOST': 'default_host',
            'PIFRAME_PORT': ('default_port', int),
        }
        
        for env_var, attr_info in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if isinstance(attr_info, tuple):
                    attr_name, converter = attr_info
                    try:
                        setattr(self, attr_name, converter(value))
                    except (ValueError, TypeError):
                        print(f"Warning: Invalid value for {env_var}: {value}")
                else:
                    setattr(self, attr_info, value)
    
    def save(self, config_path: Optional[str] = None) -> None:
        """Save current configuration to file."""
        if config_path is None:
            config_path = self.config_file
        
        # Convert to dict, excluding internal fields
        config_dict = {}
        for key, value in asdict(self).items():
            if not key.startswith('_') and key not in ['config_file']:
                # Use legacy key names for backward compatibility
                if key == 'album_id':
                    config_dict['album'] = value
                else:
                    config_dict[key] = value
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2)
            print(f"Configuration saved to {config_path}")
        except IOError as e:
            print(f"Error saving configuration: {e}")
    
    def validate(self) -> bool:
        """
        Validate configuration and return True if valid.
        Prints warnings for missing required settings.
        """
        is_valid = True
        
        if not self.album_id:
            print("Warning: album_id not configured - image serving will not work")
            is_valid = False
        
        if not os.path.exists(self.drive_credentials_file):
            print(f"Warning: Drive credentials file {self.drive_credentials_file} not found")
            is_valid = False
        
        if not self.weather_api_key:
            print("Warning: weather_api_key not configured - weather features disabled")
        
        if not self.weather_location:
            print("Warning: weather_location not configured - using default coordinates")
        
        return is_valid
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    def __str__(self) -> str:
        """String representation of configuration (hiding sensitive data)."""
        config_copy = self.to_dict()
        # Hide sensitive information
        if config_copy.get('weather_api_key'):
            config_copy['weather_api_key'] = '***hidden***'
        return json.dumps(config_copy, indent=2)