"""
Tests for ImageService class from the new modular architecture.
"""
import unittest
import io
import time
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piframe.services.image_service import ImageService
from piframe.services.drive_service import DriveService
from piframe.config.settings import Config
from piframe.models.cache import CacheManager
from flask import Flask, Response


class TestImageService(unittest.TestCase):
    """Test cases for ImageService class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = Config(
            download_cache_ttl=60,
            metadata_cache_size=20
        )
        
        # Mock services
        self.mock_cache_manager = MagicMock(spec=CacheManager)
        self.mock_drive_service = MagicMock(spec=DriveService)
        
        # Create Flask app context for testing
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create service with mocked dependencies
        self.image_service = ImageService(
            config=self.config,
            drive_service=self.mock_drive_service,
            cache_manager=self.mock_cache_manager
        )

    def tearDown(self):
        """Clean up after tests."""
        self.image_service.close()
        self.app_context.pop()

    def test_init(self):
        """Test ImageService initialization."""
        self.assertEqual(self.image_service.config, self.config)
        self.assertEqual(self.image_service.drive_service, self.mock_drive_service)
        self.assertEqual(self.image_service.cache_manager, self.mock_cache_manager)
        self.assertIsNone(self.image_service._current_image_id)
        self.assertIsNone(self.image_service._current_image_metadata)
        self.assertEqual(self.image_service._current_image_timestamp, 0)

    @patch('piframe.services.image_service.send_file')
    def test_serve_random_image_success(self, mock_send_file):
        """Test successful random image serving."""
        # Mock image info
        image_info = {
            'id': 'test_id',
            'name': 'test.jpg',
            'type': 'image/jpeg',
            'link': 'https://drive.google.com/file/d/test_id/view'
        }
        self.mock_drive_service.get_random_image.return_value = image_info
        
        # Mock image data
        image_data = io.BytesIO(b'fake image data')
        self.mock_drive_service.download_file.return_value = image_data
        
        # Mock Flask response
        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        mock_send_file.return_value = mock_response
        
        result = self.image_service.serve_random_image()
        
        self.assertEqual(result, mock_response)
        self.mock_drive_service.get_random_image.assert_called_with(avoid_recent=True)
        self.mock_drive_service.download_file.assert_called_with('test_id')
        mock_send_file.assert_called_once()

    def test_serve_random_image_no_images(self):
        """Test serving random image when no images available."""
        self.mock_drive_service.get_random_image.return_value = None
        
        result = self.image_service.serve_random_image()
        
        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 404)
        self.assertIn(b'No images found', result.data)

    @patch('piframe.services.image_service.send_file')
    def test_serve_random_image_download_failed(self, mock_send_file):
        """Test serving random image when download fails."""
        image_info = {
            'id': 'test_id',
            'name': 'test.jpg',
            'type': 'image/jpeg'
        }
        self.mock_drive_service.get_random_image.return_value = image_info
        self.mock_drive_service.download_file.return_value = None
        
        result = self.image_service.serve_random_image()
        
        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 500)
        self.assertIn(b'Error downloading image', result.data)

    @patch('piframe.services.image_service.send_file')
    @patch('piframe.services.image_service.image_metadata')
    def test_serve_random_image_with_metadata(self, mock_metadata_module, mock_send_file):
        """Test serving random image with metadata extraction."""
        # Mock image info
        image_info = {
            'id': 'test_id',
            'name': 'test.jpg',
            'type': 'image/jpeg'
        }
        self.mock_drive_service.get_random_image.return_value = image_info
        
        # Mock image data
        image_data = io.BytesIO(b'fake image data')
        self.mock_drive_service.download_file.return_value = image_data
        
        # Mock metadata extraction
        raw_metadata = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45',
            'camera_make': 'Canon',
            'camera_model': 'EOS R5'
        }
        display_info = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45',
            'camera_info': 'Canon EOS R5',
            'dimensions': '4000 x 3000'
        }
        
        mock_metadata_module.extract_image_metadata.return_value = raw_metadata
        mock_metadata_module.format_metadata_for_display.return_value = display_info
        
        # Mock cache miss
        self.mock_cache_manager.get.return_value = None
        
        # Mock Flask response
        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        mock_send_file.return_value = mock_response
        
        result = self.image_service.serve_random_image(include_metadata=True)
        
        self.assertEqual(result, mock_response)
        # Check that metadata was extracted
        mock_metadata_module.extract_image_metadata.assert_called_once()
        # Check that metadata was cached
        self.mock_cache_manager.set.assert_called_once()
        # Check synchronized state was updated
        self.assertEqual(self.image_service._current_image_id, 'test_id')

    @patch('piframe.services.image_service.send_file')
    def test_serve_random_image_force_new(self, mock_send_file):
        """Test serving random image with force_new flag."""
        image_info = {
            'id': 'test_id',
            'name': 'test.jpg',
            'type': 'image/jpeg'
        }
        self.mock_drive_service.get_random_image.return_value = image_info
        
        image_data = io.BytesIO(b'fake image data')
        self.mock_drive_service.download_file.return_value = image_data
        
        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        mock_send_file.return_value = mock_response
        
        result = self.image_service.serve_random_image(force_new=True)
        
        # Should avoid recent images = False when force_new = True
        self.mock_drive_service.get_random_image.assert_called_with(avoid_recent=False)
        # Should clear cache
        self.mock_cache_manager.delete.assert_called_with('downloads', 'download_test_id')

    @patch('piframe.services.image_service.send_file')
    def test_serve_image_by_id_success(self, mock_send_file):
        """Test successful image serving by ID."""
        image_info = {
            'id': 'test_id',
            'name': 'test.jpg',
            'type': 'image/jpeg'
        }
        self.mock_drive_service.get_file_by_id.return_value = image_info
        
        image_data = io.BytesIO(b'fake image data')
        self.mock_drive_service.download_file.return_value = image_data
        
        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        mock_send_file.return_value = mock_response
        
        result = self.image_service.serve_image_by_id('test_id')
        
        self.assertEqual(result, mock_response)
        self.mock_drive_service.get_file_by_id.assert_called_with('test_id')
        self.mock_drive_service.download_file.assert_called_with('test_id')

    def test_serve_image_by_id_not_found(self):
        """Test serving image by ID when not found."""
        self.mock_drive_service.get_file_by_id.return_value = None
        
        result = self.image_service.serve_image_by_id('nonexistent_id')
        
        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 404)
        self.assertIn(b'Image not found', result.data)

    @patch('piframe.services.image_service.send_file')
    def test_serve_image_by_id_download_failed(self, mock_send_file):
        """Test serving image by ID when download fails."""
        image_info = {
            'id': 'test_id',
            'name': 'test.jpg',
            'type': 'image/jpeg'
        }
        self.mock_drive_service.get_file_by_id.return_value = image_info
        self.mock_drive_service.download_file.return_value = None
        
        result = self.image_service.serve_image_by_id('test_id')
        
        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 500)
        self.assertIn(b'Error downloading image', result.data)

    def test_serve_synchronized_image_current(self):
        """Test serving synchronized image when current image exists."""
        # Set up synchronized state
        self.image_service._current_image_id = 'test_id'
        self.image_service._current_image_timestamp = time.time()
        
        with patch.object(self.image_service, 'serve_image_by_id') as mock_serve:
            mock_response = MagicMock()
            mock_serve.return_value = mock_response
            
            result = self.image_service.serve_synchronized_image()
            
            self.assertEqual(result, mock_response)
            mock_serve.assert_called_with('test_id', include_metadata=False)

    def test_serve_synchronized_image_expired(self):
        """Test serving synchronized image when current image is expired."""
        # Set up expired synchronized state
        self.image_service._current_image_id = 'test_id'
        self.image_service._current_image_timestamp = time.time() - 10  # 10 seconds ago
        
        with patch.object(self.image_service, 'serve_random_image') as mock_serve:
            mock_response = MagicMock()
            mock_serve.return_value = mock_response
            
            result = self.image_service.serve_synchronized_image()
            
            self.assertEqual(result, mock_response)
            mock_serve.assert_called_with(force_new=False, include_metadata=False)

    def test_serve_synchronized_image_no_current(self):
        """Test serving synchronized image when no current image."""
        with patch.object(self.image_service, 'serve_random_image') as mock_serve:
            mock_response = MagicMock()
            mock_serve.return_value = mock_response
            
            result = self.image_service.serve_synchronized_image()
            
            self.assertEqual(result, mock_response)
            mock_serve.assert_called_with(force_new=False, include_metadata=False)

    def test_get_random_image_metadata_success(self):
        """Test getting random image metadata successfully."""
        # Set up current metadata
        display_info = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45',
            'camera_info': 'Canon EOS R5',
            'dimensions': '4000 x 3000'
        }
        self.image_service._current_image_metadata = {
            'display_info': display_info
        }
        
        with patch.object(self.image_service, 'serve_random_image') as mock_serve:
            mock_serve.return_value = MagicMock()
            
            result = self.image_service.get_random_image_metadata()
            
            self.assertEqual(result['creation_date'], '25.12.2023')
            self.assertEqual(result['camera_info'], 'Canon EOS R5')
            self.assertIn('picture_url', result)
            mock_serve.assert_called_with(force_new=True, include_metadata=True)

    def test_get_random_image_metadata_no_metadata(self):
        """Test getting random image metadata when none available."""
        self.image_service._current_image_metadata = None
        
        with patch.object(self.image_service, 'serve_random_image') as mock_serve:
            mock_serve.return_value = MagicMock()
            
            result = self.image_service.get_random_image_metadata()
            
            # Should return default metadata
            self.assertEqual(result['creation_date'], 'Unknown')
            self.assertEqual(result['camera_info'], 'Unknown camera')

    def test_get_random_image_metadata_exception(self):
        """Test getting random image metadata with exception."""
        with patch.object(self.image_service, 'serve_random_image', side_effect=Exception("Test error")):
            result = self.image_service.get_random_image_metadata()
            
            # Should return default metadata
            self.assertEqual(result['creation_date'], 'Unknown')
            self.assertEqual(result['camera_info'], 'Unknown camera')

    @patch('piframe.services.image_service.image_metadata')
    def test_get_image_metadata_success(self, mock_metadata_module):
        """Test successful image metadata extraction."""
        # Mock cache miss
        self.mock_cache_manager.get.return_value = None
        
        # Mock metadata extraction
        raw_metadata = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45'
        }
        display_info = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45',
            'camera_info': 'Canon EOS R5'
        }
        
        mock_metadata_module.extract_image_metadata.return_value = raw_metadata
        mock_metadata_module.format_metadata_for_display.return_value = display_info
        
        image_data = io.BytesIO(b'fake image data')
        
        result = self.image_service.get_image_metadata('test_id', image_data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['metadata'], raw_metadata)
        self.assertEqual(result['display_info'], display_info)
        self.assertIn('timestamp', result)
        
        # Should cache the result
        self.mock_cache_manager.set.assert_called_once()

    def test_get_image_metadata_cached(self):
        """Test getting cached image metadata."""
        cached_metadata = {
            'metadata': {'test': 'data'},
            'display_info': {'creation_date': '25.12.2023'},
            'timestamp': time.time()
        }
        self.mock_cache_manager.get.return_value = cached_metadata
        
        image_data = io.BytesIO(b'fake image data')
        
        result = self.image_service.get_image_metadata('test_id', image_data)
        
        self.assertEqual(result, cached_metadata)
        self.mock_cache_manager.get.assert_called_with('metadata', 'metadata_test_id')

    @patch('piframe.services.image_service.image_metadata')
    def test_get_image_metadata_extraction_error(self, mock_metadata_module):
        """Test image metadata extraction with error."""
        self.mock_cache_manager.get.return_value = None
        mock_metadata_module.extract_image_metadata.side_effect = Exception("Extraction error")
        
        image_data = io.BytesIO(b'fake image data')
        
        result = self.image_service.get_image_metadata('test_id', image_data)
        
        # Should return default metadata
        self.assertIsNotNone(result)
        self.assertEqual(result['display_info']['creation_date'], 'Unknown')
        self.assertEqual(result['display_info']['camera_info'], 'Unknown camera')

    @patch('piframe.services.image_service.send_file')
    def test_create_image_response(self, mock_send_file):
        """Test creating Flask image response."""
        image_info = {
            'id': 'test_id',
            'name': 'test.jpg',
            'type': 'image/jpeg'
        }
        image_data = io.BytesIO(b'fake image data')
        
        metadata_info = {
            'display_info': {
                'creation_date': '25.12.2023',
                'creation_time': '14:30:45',
                'camera_info': 'Canon EOS R5',
                'dimensions': '4000 x 3000'
            }
        }
        
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_send_file.return_value = mock_response
        
        result = self.image_service._create_image_response(image_info, image_data, metadata_info)
        
        self.assertEqual(result, mock_response)
        mock_send_file.assert_called_once()
        
        # Check headers were set
        self.assertEqual(mock_response.headers['X-Image-ID'], 'test_id')
        self.assertEqual(mock_response.headers['X-Image-Date'], '25.12.2023')
        self.assertEqual(mock_response.headers['X-Camera-Info'], 'Canon EOS R5')

    @patch('piframe.services.image_service.send_file')
    def test_create_image_response_no_metadata(self, mock_send_file):
        """Test creating Flask image response without metadata."""
        image_info = {
            'id': 'test_id',
            'name': 'test.jpg',
            'type': 'image/jpeg'
        }
        image_data = io.BytesIO(b'fake image data')
        
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_send_file.return_value = mock_response
        
        result = self.image_service._create_image_response(image_info, image_data)
        
        self.assertEqual(result, mock_response)
        # Should have basic headers but no metadata headers
        self.assertEqual(mock_response.headers['X-Image-ID'], 'test_id')
        self.assertNotIn('X-Image-Date', mock_response.headers)

    def test_get_default_metadata(self):
        """Test getting default metadata structure."""
        result = self.image_service._get_default_metadata()
        
        self.assertEqual(result['creation_date'], 'Unknown')
        self.assertEqual(result['creation_time'], 'Unknown')
        self.assertEqual(result['camera_info'], 'Unknown camera')
        self.assertEqual(result['dimensions'], 'Unknown')
        self.assertIn('picture_url', result)

    def test_get_default_display_info(self):
        """Test getting default display info structure."""
        result = self.image_service._get_default_display_info()
        
        self.assertEqual(result['creation_date'], 'Unknown')
        self.assertEqual(result['creation_time'], 'Unknown')
        self.assertEqual(result['camera_info'], 'Unknown camera')
        self.assertEqual(result['dimensions'], 'Unknown')
        self.assertEqual(result['format'], 'Unknown')

    def test_clear_metadata_cache(self):
        """Test clearing metadata cache."""
        self.image_service.clear_metadata_cache()
        
        self.mock_cache_manager.clear_cache.assert_called_with('metadata')

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        mock_stats = {
            'metadata': {'hit_count': 10, 'miss_count': 2}
        }
        self.mock_cache_manager.get_all_stats.return_value = mock_stats
        
        # Set up synchronized state
        self.image_service._current_image_id = 'test_id'
        self.image_service._current_image_timestamp = time.time() - 5
        
        result = self.image_service.get_cache_stats()
        
        self.assertEqual(result['metadata_cache'], mock_stats['metadata'])
        self.assertEqual(result['synchronized_image_id'], 'test_id')
        self.assertIsInstance(result['synchronized_age_seconds'], float)

    def test_get_cache_stats_no_synchronized_image(self):
        """Test getting cache statistics with no synchronized image."""
        mock_stats = {}
        self.mock_cache_manager.get_all_stats.return_value = mock_stats
        
        result = self.image_service.get_cache_stats()
        
        self.assertIsNone(result['synchronized_image_id'])
        self.assertIsNone(result['synchronized_age_seconds'])

    def test_close(self):
        """Test service cleanup."""
        self.image_service._current_image_id = 'test_id'
        self.image_service._current_image_metadata = {'test': 'data'}
        
        self.image_service.close()
        
        self.assertIsNone(self.image_service._current_image_id)
        self.assertIsNone(self.image_service._current_image_metadata)

    def test_serve_random_image_exception_handling(self):
        """Test exception handling in serve_random_image."""
        self.mock_drive_service.get_random_image.side_effect = Exception("Unexpected error")
        
        result = self.image_service.serve_random_image()
        
        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 500)
        self.assertIn(b'Internal server error', result.data)

    def test_serve_image_by_id_exception_handling(self):
        """Test exception handling in serve_image_by_id."""
        self.mock_drive_service.get_file_by_id.side_effect = Exception("Unexpected error")
        
        result = self.image_service.serve_image_by_id('test_id')
        
        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 500)
        self.assertIn(b'Internal server error', result.data)


if __name__ == '__main__':
    unittest.main()