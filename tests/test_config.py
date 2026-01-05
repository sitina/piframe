"""
Tests for configuration management (using actual Config class)
"""
import unittest
import json
import tempfile
import os
from unittest.mock import patch, mock_open

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piframe.config import Config


class TestConfiguration(unittest.TestCase):
    """Test cases for configuration management"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_config_data = {
            "album": "test_album_id",
            "weather_api_key": "test_api_key_12345",
            "weather_location": "Prague,CZ"
        }

    def tearDown(self):
        """Clean up after tests"""
        pass

    def test_config_defaults(self):
        """Test that config has default values"""
        config = Config()
        
        self.assertEqual(config.album_id, "")
        self.assertEqual(config.drive_credentials_file, "config/client_secret.json")
        self.assertEqual(config.weather_api_key, "")
        self.assertEqual(config.default_port, 5001)
        self.assertEqual(config.default_host, "0.0.0.0")

    def test_config_structure(self):
        """Test that config has required fields"""
        config = Config()
        
        # Check that all expected fields exist
        self.assertTrue(hasattr(config, 'album_id'))
        self.assertTrue(hasattr(config, 'weather_api_key'))
        self.assertTrue(hasattr(config, 'weather_location'))
        self.assertTrue(hasattr(config, 'default_port'))
        self.assertTrue(hasattr(config, 'default_host'))

    def test_config_validation(self):
        """Test config validation"""
        # Valid config
        config = Config()
        config.album_id = "test_album_id"
        config.drive_credentials_file = "config/client_secret.json"
        config.secret_key = "test_secret"
        
        # Create a temporary credentials file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('{}')
            temp_creds = f.name
        
        try:
            config.drive_credentials_file = temp_creds
            result = config.validate(fail_fast=False)
            self.assertTrue(result)
        finally:
            if os.path.exists(temp_creds):
                os.unlink(temp_creds)
        
        # Invalid config - missing album_id
        config_invalid = Config()
        result = config_invalid.validate(fail_fast=False)
        self.assertFalse(result)
        
        # Invalid port
        config_invalid_port = Config()
        config_invalid_port.default_port = 70000  # Invalid port
        result = config_invalid_port.validate(fail_fast=False)
        self.assertFalse(result)

    def test_config_file_creation(self):
        """Test config file creation"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            config_file = f.name
        
        try:
            config = Config()
            config.album_id = "test_album_id"
            config.weather_api_key = "test_key"
            config.config_file = config_file
            config.save()
            
            # Verify file was created
            self.assertTrue(os.path.exists(config_file))
            
            # Read and verify contents
            with open(config_file, 'r') as f:
                loaded_data = json.load(f)
            
            # Check that legacy 'album' key is used
            self.assertEqual(loaded_data.get('album'), "test_album_id")
            
        finally:
            if os.path.exists(config_file):
                os.unlink(config_file)

    def test_config_file_loading(self):
        """Test config file loading"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            config_file = f.name
            json.dump(self.test_config_data, f)
        
        try:
            config = Config.load(config_file)
            
            # Check that legacy 'album' key is mapped to album_id
            self.assertEqual(config.album_id, "test_album_id")
            self.assertEqual(config.weather_api_key, "test_api_key_12345")
            self.assertEqual(config.weather_location, "Prague,CZ")
        finally:
            if os.path.exists(config_file):
                os.unlink(config_file)

    def test_config_file_not_found(self):
        """Test handling of missing config file"""
        config_file = "nonexistent_config.json"
        
        # Should create default config and save it
        import logging
        with patch.object(logging, 'info'):
            config = Config.load(config_file)
            
            # Should have defaults
            self.assertEqual(config.album_id, "")
            self.assertEqual(config.weather_api_key, "")
            
            # Should have attempted to save
            if os.path.exists(config_file):
                os.unlink(config_file)

    def test_config_file_corrupted(self):
        """Test handling of corrupted config file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            config_file = f.name
            f.write("invalid json content")
        
        try:
            import logging
            with patch.object(logging, 'warning'):
                config = Config.load(config_file)
                
                # Should fall back to defaults
                self.assertEqual(config.album_id, "")
        finally:
            if os.path.exists(config_file):
                os.unlink(config_file)

    def test_weather_api_key_storage(self):
        """Test weather API key can be stored and retrieved"""
        config = Config()
        config.weather_api_key = "test_api_key_12345"
        
        self.assertEqual(config.weather_api_key, "test_api_key_12345")

    def test_album_id_storage(self):
        """Test album ID can be stored and retrieved"""
        config = Config()
        config.album_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        
        self.assertEqual(config.album_id, "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")

    def test_weather_location_storage(self):
        """Test weather location can be stored and retrieved"""
        config = Config()
        config.weather_location = "Prague,CZ"
        
        self.assertEqual(config.weather_location, "Prague,CZ")

    def test_config_environment_variables(self):
        """Test config loading from environment variables"""
        with patch.dict(os.environ, {
            'PIFRAME_ALBUM_ID': 'env_album_id',
            'PIFRAME_WEATHER_API_KEY': 'env_api_key',
            'PIFRAME_WEATHER_LOCATION': 'env_location',
            'PIFRAME_PORT': '8080',
            'PIFRAME_HOST': '127.0.0.1'
        }):
            config = Config()
            config._load_from_env()
            
            # Should load from environment
            self.assertEqual(config.album_id, 'env_album_id')
            self.assertEqual(config.weather_api_key, 'env_api_key')
            self.assertEqual(config.weather_location, 'env_location')
            self.assertEqual(config.default_port, 8080)
            self.assertEqual(config.default_host, '127.0.0.1')

    def test_config_merge(self):
        """Test merging config from file and environment"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            config_file = f.name
            file_config = {
                "album": "file_album_id",
                "weather_api_key": "file_api_key",
                "weather_location": "file_location"
            }
            json.dump(file_config, f)
        
        try:
            with patch.dict(os.environ, {
                'PIFRAME_WEATHER_API_KEY': 'env_api_key'
            }):
                # Load from file, then environment should override
                config = Config.load(config_file)
                
                # File values
                self.assertEqual(config.album_id, 'file_album_id')
                self.assertEqual(config.weather_location, 'file_location')
                # Environment should override
                self.assertEqual(config.weather_api_key, 'env_api_key')
        finally:
            if os.path.exists(config_file):
                os.unlink(config_file)

    def test_config_sensitive_data_masking(self):
        """Test that sensitive data is properly masked in logs"""
        config = Config()
        config.album_id = "test_album_id"
        config.weather_api_key = "secret_api_key_12345"
        config.weather_location = "Prague"
        
        # String representation should mask API key
        config_str = str(config)
        config_dict = json.loads(config_str)
        
        self.assertEqual(config_dict["album_id"], "test_album_id")
        self.assertEqual(config_dict["weather_api_key"], "***hidden***")
        self.assertEqual(config_dict["weather_location"], "Prague")

    def test_config_to_dict(self):
        """Test converting config to dictionary"""
        config = Config()
        config.album_id = "test_album"
        config.weather_api_key = "test_key"
        
        config_dict = config.to_dict()
        
        self.assertIsInstance(config_dict, dict)
        self.assertEqual(config_dict['album_id'], "test_album")
        self.assertEqual(config_dict['weather_api_key'], "test_key")

    def test_config_secret_key_generation(self):
        """Test automatic secret key generation"""
        config = Config.load("nonexistent.json")
        
        # Should generate a secret key if not provided
        self.assertIsNotNone(config.secret_key)
        self.assertGreater(len(config.secret_key), 0)

    def test_config_environment_variable_type_conversion(self):
        """Test environment variable type conversion"""
        with patch.dict(os.environ, {
            'PIFRAME_WEATHER_LAT': '50.5',
            'PIFRAME_WEATHER_LON': '14.5',
            'PIFRAME_PORT': '8080'
        }):
            config = Config()
            config._load_from_env()
            
            self.assertEqual(config.weather_lat, 50.5)
            self.assertEqual(config.weather_lon, 14.5)
            self.assertEqual(config.default_port, 8080)

    def test_config_environment_variable_invalid_type(self):
        """Test handling invalid environment variable types"""
        with patch.dict(os.environ, {
            'PIFRAME_PORT': 'invalid_port'
        }):
            import logging
            with patch.object(logging, 'warning'):
                config = Config()
                config._load_from_env()
                
                # Should keep default value
                self.assertEqual(config.default_port, 5001)

    def test_config_validate_fail_fast(self):
        """Test config validation with fail_fast=True"""
        config = Config()
        # Missing required fields
        
        with self.assertRaises(ValueError):
            config.validate(fail_fast=True)

    def test_config_update_from_dict_legacy_keys(self):
        """Test updating config from dict with legacy key names"""
        config = Config()
        data = {
            'album': 'legacy_album_id',  # Should map to album_id
            'weather_api_key': 'test_key'
        }
        
        config._update_from_dict(data)
        
        self.assertEqual(config.album_id, 'legacy_album_id')
        self.assertEqual(config.weather_api_key, 'test_key')


if __name__ == '__main__':
    unittest.main() 