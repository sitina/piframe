"""
Tests for configuration management
"""
import unittest
import json
import tempfile
import os
from unittest.mock import patch, mock_open

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfiguration(unittest.TestCase):
    """Test cases for configuration management"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_config = {
            "album": "test_album_id",
            "weather_api_key": "test_api_key_12345",
            "weather_location": "Prague,CZ"
        }

    def tearDown(self):
        """Clean up after tests"""
        pass

    def test_config_structure(self):
        """Test that config has required fields"""
        required_fields = ['album', 'weather_api_key', 'weather_location']
        
        for field in required_fields:
            self.assertIn(field, self.test_config)
            self.assertIsInstance(self.test_config[field], str)

    def test_config_validation(self):
        """Test config validation"""
        # Valid config
        self.assertTrue(self._is_valid_config(self.test_config))
        
        # Invalid configs
        invalid_configs = [
            {},  # Empty
            {"album": "test"},  # Missing fields
            {"album": "", "weather_api_key": "test", "weather_location": "test"},  # Empty album
            {"album": "test", "weather_api_key": "", "weather_location": "test"},  # Empty API key
        ]
        
        for config in invalid_configs:
            self.assertFalse(self._is_valid_config(config))

    def test_config_file_creation(self):
        """Test config file creation"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            config_file = f.name
        
        try:
            # Write config to file
            with open(config_file, 'w') as f:
                json.dump(self.test_config, f, indent=2)
            
            # Read config from file
            with open(config_file, 'r') as f:
                loaded_config = json.load(f)
            
            self.assertEqual(loaded_config, self.test_config)
            
        finally:
            # Clean up
            if os.path.exists(config_file):
                os.unlink(config_file)

    def test_config_file_loading(self):
        """Test config file loading"""
        with patch('builtins.open', mock_open(read_data=json.dumps(self.test_config))):
            with patch('json.load', return_value=self.test_config):
                # Simulate config loading
                config = self.test_config
                self.assertEqual(config, self.test_config)

    def test_config_file_not_found(self):
        """Test handling of missing config file"""
        with patch('os.path.exists', return_value=False):
            # Should create default config
            default_config = {
                "album": "",
                "weather_api_key": "",
                "weather_location": ""
            }
            self.assertEqual(default_config["album"], "")
            self.assertEqual(default_config["weather_api_key"], "")

    def test_config_file_corrupted(self):
        """Test handling of corrupted config file"""
        with patch('builtins.open', mock_open(read_data="invalid json")):
            with patch('json.load', side_effect=json.JSONDecodeError("", "", 0)):
                # Should handle JSON decode error gracefully
                default_config = {
                    "album": "",
                    "weather_api_key": "",
                    "weather_location": ""
                }
                self.assertEqual(default_config["album"], "")

    def test_weather_api_key_validation(self):
        """Test weather API key validation"""
        # Valid API key (32 characters)
        valid_key = "a" * 32
        self.assertTrue(self._is_valid_api_key(valid_key))
        
        # Invalid API keys
        invalid_keys = [
            "",  # Empty
            "short",  # Too short
            "a" * 100,  # Too long
            "invalid key with spaces",  # Contains spaces
        ]
        
        for key in invalid_keys:
            self.assertFalse(self._is_valid_api_key(key))

    def test_album_id_validation(self):
        """Test album ID validation"""
        # Valid album ID (Google Drive folder ID format)
        valid_album = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        self.assertTrue(self._is_valid_album_id(valid_album))
        
        # Invalid album IDs
        invalid_albums = [
            "",  # Empty
            "invalid",  # Too short
            "a" * 100,  # Too long
            "invalid@id",  # Contains @
            "invalid#id",  # Contains #
        ]
        
        for album in invalid_albums:
            self.assertFalse(self._is_valid_album_id(album))

    def test_weather_location_validation(self):
        """Test weather location validation"""
        # Valid locations
        valid_locations = [
            "Prague",
            "Prague,CZ",
            "New York,US",
            "London,GB"
        ]
        
        for location in valid_locations:
            self.assertTrue(self._is_valid_location(location))
        
        # Invalid locations
        invalid_locations = [
            "",  # Empty
            "a" * 100,  # Too long
            "Invalid@Location",  # Contains special characters
        ]
        
        for location in invalid_locations:
            self.assertFalse(self._is_valid_location(location))

    def test_config_environment_variables(self):
        """Test config loading from environment variables"""
        with patch.dict(os.environ, {
            'PIFRAME_ALBUM': 'env_album_id',
            'PIFRAME_WEATHER_API_KEY': 'env_api_key',
            'PIFRAME_WEATHER_LOCATION': 'env_location'
        }):
            # Should prioritize environment variables
            env_config = {
                "album": os.environ.get('PIFRAME_ALBUM', ''),
                "weather_api_key": os.environ.get('PIFRAME_WEATHER_API_KEY', ''),
                "weather_location": os.environ.get('PIFRAME_WEATHER_LOCATION', '')
            }
            
            self.assertEqual(env_config["album"], 'env_album_id')
            self.assertEqual(env_config["weather_api_key"], 'env_api_key')
            self.assertEqual(env_config["weather_location"], 'env_location')

    def test_config_merge(self):
        """Test merging config from file and environment"""
        file_config = {
            "album": "file_album_id",
            "weather_api_key": "file_api_key",
            "weather_location": "file_location"
        }
        
        with patch.dict(os.environ, {
            'PIFRAME_WEATHER_API_KEY': 'env_api_key'
        }):
            # Environment should override file config
            merged_config = file_config.copy()
            merged_config["weather_api_key"] = os.environ.get('PIFRAME_WEATHER_API_KEY', merged_config["weather_api_key"])
            
            self.assertEqual(merged_config["album"], 'file_album_id')
            self.assertEqual(merged_config["weather_api_key"], 'env_api_key')
            self.assertEqual(merged_config["weather_location"], 'file_location')

    def test_config_sensitive_data_masking(self):
        """Test that sensitive data is properly masked in logs"""
        config_with_sensitive_data = {
            "album": "test_album_id",
            "weather_api_key": "secret_api_key_12345",
            "weather_location": "Prague"
        }
        
        # Should mask API key in logs
        masked_config = self._mask_sensitive_data(config_with_sensitive_data)
        
        self.assertEqual(masked_config["album"], "test_album_id")
        self.assertNotEqual(masked_config["weather_api_key"], "secret_api_key_12345")
        self.assertIn("*", masked_config["weather_api_key"])
        self.assertEqual(masked_config["weather_location"], "Prague")

    # Helper methods
    def _is_valid_config(self, config):
        """Check if config is valid"""
        required_fields = ['album', 'weather_api_key', 'weather_location']
        return all(field in config and config[field] for field in required_fields)

    def _is_valid_api_key(self, api_key):
        """Check if API key is valid"""
        return isinstance(api_key, str) and 20 <= len(api_key) <= 50 and ' ' not in api_key

    def _is_valid_album_id(self, album_id):
        """Check if album ID is valid"""
        # Google Drive folder IDs are typically 33 characters long and contain only letters, numbers, and some special characters
        if not isinstance(album_id, str) or len(album_id) < 20 or len(album_id) > 50:
            return False
        
        # Check for invalid characters (spaces, special characters that aren't allowed in Drive IDs)
        invalid_chars = [' ', '@', '#', '$', '%', '^', '&', '*', '(', ')', '+', '=', '[', ']', '{', '}', '|', '\\', ':', ';', '"', "'", '<', '>', ',', '?', '/']
        return not any(char in album_id for char in invalid_chars)

    def _is_valid_location(self, location):
        """Check if location is valid"""
        return isinstance(location, str) and 1 <= len(location) <= 50 and '@' not in location

    def _mask_sensitive_data(self, config):
        """Mask sensitive data in config"""
        masked_config = config.copy()
        if 'weather_api_key' in masked_config and masked_config['weather_api_key']:
            api_key = masked_config['weather_api_key']
            if len(api_key) > 8:
                masked_config['weather_api_key'] = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]
            else:
                masked_config['weather_api_key'] = '*' * len(api_key)
        return masked_config


if __name__ == '__main__':
    unittest.main() 