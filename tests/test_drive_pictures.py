"""
Tests for drive_pictures module
"""
import unittest
import io
import time
import tempfile
import os
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import drive_pictures

# Skip all Google Drive integration tests in CI environment
SKIP_DRIVE_TESTS = os.getenv('CI') == 'true' or os.getenv('GITHUB_ACTIONS') == 'true'


@unittest.skipIf(SKIP_DRIVE_TESTS, "Skipping Google Drive integration tests in CI environment")
class TestDrivePictures(unittest.TestCase):
    """Test cases for drive_pictures module"""

    def setUp(self):
        """Set up test fixtures"""
        # Reset global caches
        drive_pictures._credentials_cache = None
        drive_pictures._service_cache = None
        drive_pictures._files_cache = {'data': [], 'ts': 0, 'folder_id': None}
        drive_pictures._download_cache = {}
        drive_pictures._metadata_cache = {}
        
        # Reset recently served list
        if hasattr(drive_pictures.serve_random_image, '_recently_served'):
            drive_pictures.serve_random_image._recently_served.clear()

    def tearDown(self):
        """Clean up after tests"""
        # Reset global caches
        drive_pictures._credentials_cache = None
        drive_pictures._service_cache = None
        drive_pictures._files_cache = {'data': [], 'ts': 0, 'folder_id': None}
        drive_pictures._download_cache = {}
        drive_pictures._metadata_cache = {}
        
        # Reset recently served list
        if hasattr(drive_pictures.serve_random_image, '_recently_served'):
            drive_pictures.serve_random_image._recently_served.clear()

    @patch('drive_pictures.os.path.exists')
    @patch('drive_pictures.pickle.load')
    @patch('drive_pictures.pickle.dump')
    def test_get_credentials_with_existing_token(self, mock_dump, mock_load, mock_exists):
        """Test getting credentials with existing token file"""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_load.return_value = mock_creds
        
        creds = drive_pictures.get_credentials()
        
        self.assertEqual(creds, mock_creds)
        mock_load.assert_called_once()

    @patch('drive_pictures.os.path.exists')
    @patch('drive_pictures.pickle.load')
    @patch('drive_pictures.pickle.dump')
    @patch('drive_pictures.InstalledAppFlow')
    def test_get_credentials_without_token(self, mock_flow, mock_dump, mock_load, mock_exists):
        """Test getting credentials without existing token"""
        mock_exists.return_value = False
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        
        creds = drive_pictures.get_credentials()
        
        self.assertEqual(creds, mock_creds)
        mock_flow.from_client_secrets_file.assert_called_once()

    @patch('drive_pictures.get_credentials')
    @patch('drive_pictures.build')
    def test_get_service(self, mock_build, mock_get_creds):
        """Test getting Google Drive service"""
        mock_creds = MagicMock()
        mock_get_creds.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        service = drive_pictures.get_service()
        
        self.assertEqual(service, mock_service)
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_creds)

    @patch('drive_pictures.get_service')
    def test_list_images_in_folder_with_cache(self, mock_get_service):
        """Test listing images with cache hit"""
        # Set up cache
        cached_files = [{'id': '1', 'name': 'test.jpg', 'mimeType': 'image/jpeg'}]
        drive_pictures._files_cache = {
            'data': cached_files,
            'ts': time.time(),
            'folder_id': 'test_folder'
        }
        
        files = drive_pictures.list_images_in_folder('test_folder')
        
        self.assertEqual(files, cached_files)
        mock_get_service.assert_not_called()  # Should use cache

    @patch('drive_pictures.get_service')
    def test_list_images_in_folder_api_call(self, mock_get_service):
        """Test listing images with API call"""
        # Set up expired cache
        drive_pictures._files_cache = {
            'data': [],
            'ts': time.time() - 4000,  # Expired
            'folder_id': 'test_folder'
        }
        
        mock_service = MagicMock()
        mock_files = [{'id': '1', 'name': 'test.jpg', 'mimeType': 'image/jpeg', 'webViewLink': 'http://example.com'}]
        mock_response = {'files': mock_files}
        mock_service.files().list().execute.return_value = mock_response
        mock_get_service.return_value = mock_service
        
        files = drive_pictures.list_images_in_folder('test_folder')
        
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['name'], 'test.jpg')
        mock_service.files().list().execute.assert_called_once()

    @patch('drive_pictures.get_service')
    def test_list_images_in_folder_no_files(self, mock_get_service):
        """Test listing images when no files found"""
        mock_service = MagicMock()
        mock_response = {'files': []}
        mock_service.files().list().execute.return_value = mock_response
        mock_get_service.return_value = mock_service
        
        files = drive_pictures.list_images_in_folder('test_folder')
        
        self.assertEqual(files, [])

    @patch('drive_pictures.get_service')
    def test_list_images_in_folder_api_error(self, mock_get_service):
        """Test listing images with API error"""
        mock_service = MagicMock()
        mock_service.files().list().execute.side_effect = Exception("API Error")
        mock_get_service.return_value = mock_service
        
        files = drive_pictures.list_images_in_folder('test_folder')
        
        self.assertEqual(files, [])

    def test_get_random_image_with_files(self):
        """Test getting random image with available files"""
        test_files = [
            {'id': '1', 'name': 'test1.jpg'},
            {'id': '2', 'name': 'test2.jpg'}
        ]
        
        with patch('drive_pictures.list_images_in_folder', return_value=test_files):
            random_file = drive_pictures.get_random_image('test_folder')
            
            self.assertIn(random_file, test_files)

    def test_get_random_image_no_files(self):
        """Test getting random image with no files"""
        with patch('drive_pictures.list_images_in_folder', return_value=[]):
            random_file = drive_pictures.get_random_image('test_folder')
            
            self.assertIsNone(random_file)

    @patch('drive_pictures.get_service')
    def test_download_file_success(self, mock_get_service):
        """Test successful file download"""
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)
        
        mock_service.files().get_media.return_value = mock_request
        mock_get_service.return_value = mock_service
        
        # Mock MediaIoBaseDownload with proper file data
        with patch('drive_pictures.MediaIoBaseDownload', return_value=mock_downloader):
            with patch('drive_pictures.io.BytesIO') as mock_bytesio:
                mock_file_data = io.BytesIO(b'test data')
                mock_bytesio.return_value = mock_file_data
                
                file_data = drive_pictures.download_file('test_file_id')
                
                self.assertIsNotNone(file_data)
                self.assertIsInstance(file_data, type(io.BytesIO()))

    @patch('drive_pictures.get_service')
    def test_download_file_error(self, mock_get_service):
        """Test file download with error"""
        mock_service = MagicMock()
        mock_service.files().get_media.side_effect = Exception("Download error")
        mock_get_service.return_value = mock_service
        
        file_data = drive_pictures.download_file('test_file_id')
        
        self.assertIsNone(file_data)

    def test_download_file_with_cache(self):
        """Test file download with cache hit"""
        # Set up cache
        cached_data = io.BytesIO(b'test data')
        drive_pictures._download_cache['test_id'] = {
            'data': cached_data,
            'ts': time.time()
        }
        
        file_data = drive_pictures.download_file('test_id')
        
        self.assertEqual(file_data, cached_data)

    def test_download_file_cache_expired(self):
        """Test file download with expired cache"""
        # Set up expired cache
        cached_data = io.BytesIO(b'test data')
        drive_pictures._download_cache['test_id'] = {
            'data': cached_data,
            'ts': time.time() - 400  # Expired
        }
        
        with patch('drive_pictures.get_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.files().get_media.side_effect = Exception("Should not be called")
            mock_get_service.return_value = mock_service
            
            file_data = drive_pictures.download_file('test_id')
            
            # Should return None due to exception, but cache should be cleared
            self.assertIsNone(file_data)

    @patch('drive_pictures.get_random_image')
    @patch('drive_pictures.download_file')
    @patch('drive_pictures.send_file')
    def test_serve_random_image_success(self, mock_send_file, mock_download, mock_get_random):
        """Test successful random image serving"""
        mock_file = {'id': 'test_id', 'name': 'test.jpg', 'type': 'image/jpeg'}
        mock_get_random.return_value = mock_file
        
        mock_file_data = io.BytesIO(b'test data')
        mock_download.return_value = mock_file_data
        
        mock_response = MagicMock()
        mock_send_file.return_value = mock_response
        
        response = drive_pictures.serve_random_image()
        
        self.assertEqual(response, mock_response)
        mock_send_file.assert_called_once()

    @patch('drive_pictures.get_random_image')
    def test_serve_random_image_no_files(self, mock_get_random):
        """Test serving random image with no files"""
        mock_get_random.return_value = None
        
        # Mock list_images_in_folder to return empty list
        with patch('drive_pictures.list_images_in_folder', return_value=[]):
            response = drive_pictures.serve_random_image()
            
            # Should return a tuple with error message and status code
            self.assertIsInstance(response, tuple)
            self.assertEqual(len(response), 2)
            self.assertEqual(response[1], 404)  # Status code

    @patch('drive_pictures.get_random_image')
    @patch('drive_pictures.download_file')
    def test_serve_random_image_download_error(self, mock_download, mock_get_random):
        """Test serving random image with download error"""
        mock_file = {'id': 'test_id', 'name': 'test.jpg', 'type': 'image/jpeg'}
        mock_get_random.return_value = mock_file
        mock_download.return_value = None
        
        response = drive_pictures.serve_random_image()
        
        self.assertEqual(response[1], 500)  # Status code

    def test_serve_random_image_recently_served(self):
        """Test serving random image avoiding recently served"""
        test_files = [
            {'id': '1', 'name': 'test1.jpg'},
            {'id': '2', 'name': 'test2.jpg'},
            {'id': '3', 'name': 'test3.jpg'}
        ]
        
        with patch('drive_pictures.list_images_in_folder', return_value=test_files):
            with patch('drive_pictures.download_file', return_value=io.BytesIO(b'test')):
                with patch('drive_pictures.send_file', return_value=MagicMock()):
                    # First call
                    drive_pictures.serve_random_image()
                    
                    # Second call should avoid the first image
                    drive_pictures.serve_random_image()
                    
                    # Check that recently served list is maintained
                    self.assertTrue(hasattr(drive_pictures.serve_random_image, '_recently_served'))
                    self.assertEqual(len(drive_pictures.serve_random_image._recently_served), 2)

    @patch('drive_pictures.get_random_image')
    @patch('drive_pictures.download_file')
    @patch('drive_pictures.send_file')
    @patch('drive_pictures.image_metadata.extract_image_metadata')
    def test_serve_random_image_with_metadata(self, mock_extract_metadata, mock_send_file, mock_download, mock_get_random):
        """Test serving random image with metadata"""
        mock_file = {'id': 'test_id', 'name': 'test.jpg', 'type': 'image/jpeg'}
        mock_get_random.return_value = mock_file
        
        mock_file_data = io.BytesIO(b'test data')
        mock_download.return_value = mock_file_data
        
        mock_metadata = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45',
            'camera_info': 'Canon EOS R5',
            'dimensions': '4000 x 3000'
        }
        mock_extract_metadata.return_value = mock_metadata
        
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_send_file.return_value = mock_response
        
        response = drive_pictures.serve_random_image(include_metadata=True)
        
        self.assertEqual(response, mock_response)
        mock_extract_metadata.assert_called_once_with(mock_file_data)


if __name__ == '__main__':
    unittest.main() 