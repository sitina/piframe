"""
Tests for DriveService class from the new modular architecture.
"""
import unittest
import io
import pickle
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piframe.services.drive_service import DriveService
from piframe.config.settings import Config
from piframe.models.cache import CacheManager


class TestDriveService(unittest.TestCase):
    """Test cases for DriveService class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = Config(
            album_id="test_folder_id",
            drive_credentials_file="client_secret.json",
            drive_token_file="token.pickle",
            files_cache_ttl=3600,
            download_cache_ttl=60
        )
        
        # Mock cache manager
        self.mock_cache_manager = MagicMock(spec=CacheManager)
        
        # Create service with mocked cache
        self.drive_service = DriveService(
            config=self.config,
            cache_manager=self.mock_cache_manager
        )

    def tearDown(self):
        """Clean up after tests."""
        self.drive_service.close()

    def test_init(self):
        """Test DriveService initialization."""
        self.assertEqual(self.drive_service.config, self.config)
        self.assertEqual(self.drive_service.cache_manager, self.mock_cache_manager)
        self.assertIsNone(self.drive_service._credentials)
        self.assertIsNone(self.drive_service._service)
        self.assertEqual(self.drive_service._recently_served, [])

    def test_constants(self):
        """Test class constants."""
        self.assertEqual(DriveService.SCOPES, ['https://www.googleapis.com/auth/drive.readonly'])
        self.assertIn('image/jpeg', DriveService.IMAGE_MIME_TYPES)
        self.assertIn('image/png', DriveService.IMAGE_MIME_TYPES)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    @patch('pickle.load')
    def test_load_credentials_existing_valid(self, mock_pickle_load, mock_file, mock_exists):
        """Test loading existing valid credentials."""
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_pickle_load.return_value = mock_creds
        
        result = self.drive_service._load_credentials()
        
        self.assertEqual(result, mock_creds)
        self.assertEqual(self.drive_service._credentials, mock_creds)
        mock_file.assert_called_with("token.pickle", 'rb')

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pickle.load', side_effect=pickle.UnpicklingError("Corrupted"))
    @patch('os.remove')
    def test_load_credentials_corrupted_token(self, mock_remove, mock_pickle_load, mock_file, mock_exists):
        """Test handling corrupted token file."""
        # Mock token file exists, credentials file exists
        mock_exists.side_effect = lambda path: path in ["token.pickle", "client_secret.json"]
        
        with patch('piframe.services.drive_service.InstalledAppFlow') as mock_flow:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_flow_instance = MagicMock()
            mock_flow_instance.run_local_server.return_value = mock_creds
            mock_flow.from_client_secrets_file.return_value = mock_flow_instance
            
            result = self.drive_service._load_credentials()
            
            # Should remove corrupted token file
            mock_remove.assert_called_with(self.config.drive_token_file)
            # Should create new credentials
            self.assertEqual(result, mock_creds)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    @patch('pickle.load')
    def test_load_credentials_expired_with_refresh(self, mock_pickle_load, mock_file, mock_exists):
        """Test refreshing expired credentials."""
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_pickle_load.return_value = mock_creds
        
        with patch('piframe.services.drive_service.Request') as mock_request:
            # After refresh, credentials become valid
            def refresh_side_effect(request):
                mock_creds.valid = True
            
            mock_creds.refresh.side_effect = refresh_side_effect
            
            result = self.drive_service._load_credentials()
            
            self.assertEqual(result, mock_creds)
            mock_creds.refresh.assert_called_once()

    @patch('os.path.exists', return_value=False)
    def test_load_credentials_no_credentials_file(self, mock_exists):
        """Test handling missing credentials file."""
        result = self.drive_service._load_credentials()
        
        self.assertIsNone(result)

    def test_credentials_property(self):
        """Test credentials property caching."""
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        result = self.drive_service.credentials
        
        self.assertEqual(result, mock_creds)

    @patch('piframe.services.drive_service.build')
    def test_service_property(self, mock_build):
        """Test service property creation."""
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        result = self.drive_service.service
        
        self.assertEqual(result, mock_service)
        mock_build.assert_called_with('drive', 'v3', credentials=mock_creds)

    def test_service_property_no_credentials(self):
        """Test service property with no credentials."""
        with patch.object(self.drive_service, '_load_credentials', return_value=None):
            with self.assertRaises(RuntimeError):
                _ = self.drive_service.service

    def test_list_images_in_folder_cached(self):
        """Test listing images with cached data."""
        cached_files = [{'id': '1', 'name': 'test.jpg', 'type': 'image/jpeg'}]
        self.mock_cache_manager.get.return_value = cached_files
        
        result = self.drive_service.list_images_in_folder()
        
        self.assertEqual(result, cached_files)
        self.mock_cache_manager.get.assert_called_with('files', 'files_test_folder_id')

    def test_list_images_in_folder_no_folder_id(self):
        """Test listing images with no folder ID."""
        config = Config(album_id="")
        service = DriveService(config, self.mock_cache_manager)
        
        result = service.list_images_in_folder()
        
        self.assertEqual(result, [])

    @patch('piframe.services.drive_service.build')
    def test_list_images_in_folder_api_call(self, mock_build):
        """Test listing images with API call (single page)."""
        self.mock_cache_manager.get.return_value = None
        
        # Mock service
        mock_service = MagicMock()
        mock_files_data = {
            'files': [
                {
                    'id': '1',
                    'name': 'test1.jpg',
                    'mimeType': 'image/jpeg',
                    'webViewLink': 'https://drive.google.com/file/d/1/view'
                },
                {
                    'id': '2',
                    'name': 'test2.png',
                    'mimeType': 'image/png',
                    'webViewLink': 'https://drive.google.com/file/d/2/view'
                }
            ]
            # No 'nextPageToken' = single page
        }
        mock_service.files().list().execute.return_value = mock_files_data
        mock_build.return_value = mock_service
        
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        result = self.drive_service.list_images_in_folder()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'test1.jpg')
        self.assertEqual(result[1]['name'], 'test2.png')
        self.mock_cache_manager.set.assert_called_once()

    @patch('piframe.services.drive_service.build')
    def test_list_images_in_folder_pagination_multiple_pages(self, mock_build):
        """Test listing images with pagination (multiple pages)."""
        self.mock_cache_manager.get.return_value = None
        
        # Mock service with pagination
        mock_service = MagicMock()
        
        # First page response
        page1_data = {
            'files': [
                {'id': '1', 'name': 'page1_img1.jpg', 'mimeType': 'image/jpeg', 'webViewLink': 'https://drive.google.com/file/d/1/view'},
                {'id': '2', 'name': 'page1_img2.jpg', 'mimeType': 'image/jpeg', 'webViewLink': 'https://drive.google.com/file/d/2/view'}
            ],
            'nextPageToken': 'token_page2'
        }
        
        # Second page response
        page2_data = {
            'files': [
                {'id': '3', 'name': 'page2_img1.jpg', 'mimeType': 'image/jpeg', 'webViewLink': 'https://drive.google.com/file/d/3/view'},
                {'id': '4', 'name': 'page2_img2.jpg', 'mimeType': 'image/jpeg', 'webViewLink': 'https://drive.google.com/file/d/4/view'}
            ],
            'nextPageToken': 'token_page3'
        }
        
        # Third page response (final)
        page3_data = {
            'files': [
                {'id': '5', 'name': 'page3_img1.jpg', 'mimeType': 'image/jpeg', 'webViewLink': 'https://drive.google.com/file/d/5/view'}
            ]
            # No 'nextPageToken' = final page
        }
        
        # Mock API calls in sequence
        mock_list_call = mock_service.files().list
        mock_list_call().execute.side_effect = [page1_data, page2_data, page3_data]
        mock_build.return_value = mock_service
        
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        result = self.drive_service.list_images_in_folder()
        
        # Should have all files from all pages
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]['name'], 'page1_img1.jpg')
        self.assertEqual(result[2]['name'], 'page2_img1.jpg')
        self.assertEqual(result[4]['name'], 'page3_img1.jpg')
        
        # Should have made 3 API calls
        self.assertEqual(mock_list_call().execute.call_count, 3)

    @patch('piframe.services.drive_service.build')
    def test_list_images_in_folder_pagination_large_folder(self, mock_build):
        """Test listing images with pagination for a large folder (1000+ files)."""
        self.mock_cache_manager.get.return_value = None
        
        # Mock service
        mock_service = MagicMock()
        
        # Generate mock data for 1500 files across 2 pages (1000 + 500)
        def generate_page_data(page_num, files_count, has_next=False):
            files = []
            start_id = (page_num - 1) * 1000 + 1
            for i in range(files_count):
                file_id = start_id + i
                files.append({
                    'id': str(file_id),
                    'name': f'image_{file_id:04d}.jpg',
                    'mimeType': 'image/jpeg',
                    'webViewLink': f'https://drive.google.com/file/d/{file_id}/view'
                })
            
            response = {'files': files}
            if has_next:
                response['nextPageToken'] = f'token_page{page_num + 1}'
            return response
        
        page1_data = generate_page_data(1, 1000, has_next=True)  # 1000 files, has next page
        page2_data = generate_page_data(2, 500, has_next=False)  # 500 files, final page
        
        mock_list_call = mock_service.files().list
        mock_list_call().execute.side_effect = [page1_data, page2_data]
        mock_build.return_value = mock_service
        
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        result = self.drive_service.list_images_in_folder()
        
        # Should have all 1500 files
        self.assertEqual(len(result), 1500)
        self.assertEqual(result[0]['name'], 'image_0001.jpg')
        self.assertEqual(result[999]['name'], 'image_1000.jpg')
        self.assertEqual(result[1000]['name'], 'image_1001.jpg')
        self.assertEqual(result[1499]['name'], 'image_1500.jpg')
        
        # Should have made 2 API calls
        self.assertEqual(mock_list_call().execute.call_count, 2)

    @patch('piframe.services.drive_service.build')
    def test_list_images_in_folder_pagination_safety_limit(self, mock_build):
        """Test pagination safety limit to prevent infinite loops."""
        self.mock_cache_manager.get.return_value = None
        
        # Mock service that always returns nextPageToken (infinite pagination)
        mock_service = MagicMock()
        
        def infinite_pagination(*args, **kwargs):
            return {
                'files': [{'id': '1', 'name': 'test.jpg', 'mimeType': 'image/jpeg', 'webViewLink': 'https://example.com'}],
                'nextPageToken': 'always_has_next'  # Always returns a next page token
            }
        
        mock_list_call = mock_service.files().list
        mock_list_call().execute.side_effect = infinite_pagination
        mock_build.return_value = mock_service
        
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        result = self.drive_service.list_images_in_folder()
        
        # Should stop at safety limit (100 pages, but counts to 101 before breaking)
        self.assertEqual(len(result), 101)  # 101 pages * 1 file per page
        self.assertEqual(mock_list_call().execute.call_count, 101)

    @patch('piframe.services.drive_service.build')
    def test_list_images_in_folder_pagination_empty_pages(self, mock_build):
        """Test pagination with some empty pages."""
        self.mock_cache_manager.get.return_value = None
        
        # Mock service
        mock_service = MagicMock()
        
        page1_data = {
            'files': [
                {'id': '1', 'name': 'img1.jpg', 'mimeType': 'image/jpeg', 'webViewLink': 'https://drive.google.com/file/d/1/view'}
            ],
            'nextPageToken': 'token_page2'
        }
        
        page2_data = {
            'files': [],  # Empty page
            'nextPageToken': 'token_page3'
        }
        
        page3_data = {
            'files': [
                {'id': '2', 'name': 'img2.jpg', 'mimeType': 'image/jpeg', 'webViewLink': 'https://drive.google.com/file/d/2/view'}
            ]
            # Final page
        }
        
        mock_list_call = mock_service.files().list
        mock_list_call().execute.side_effect = [page1_data, page2_data, page3_data]
        mock_build.return_value = mock_service
        
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        result = self.drive_service.list_images_in_folder()
        
        # Should have 2 files (empty page should not affect result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'img1.jpg')
        self.assertEqual(result[1]['name'], 'img2.jpg')
        
        # Should have made 3 API calls
        self.assertEqual(mock_list_call().execute.call_count, 3)

    @patch('piframe.services.drive_service.build')
    def test_list_images_in_folder_api_error(self, mock_build):
        """Test listing images with API error."""
        self.mock_cache_manager.get.side_effect = [None, None]  # No cache, then no fallback
        
        mock_service = MagicMock()
        mock_service.files().list().execute.side_effect = Exception("API Error")
        mock_build.return_value = mock_service
        
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        result = self.drive_service.list_images_in_folder()
        
        self.assertEqual(result, [])

    @patch('piframe.services.drive_service.build')
    def test_list_images_in_folder_no_files(self, mock_build):
        """Test listing images when no files found."""
        self.mock_cache_manager.get.return_value = None
        
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {'files': []}
        mock_build.return_value = mock_service
        
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        result = self.drive_service.list_images_in_folder()
        
        self.assertEqual(result, [])
        self.mock_cache_manager.set.assert_called_with('files', 'files_test_folder_id', [])

    def test_download_file_cached(self):
        """Test downloading file with cached data."""
        cached_bytes = b'cached file data'
        self.mock_cache_manager.get.return_value = cached_bytes
        
        result = self.drive_service.download_file('test_file_id')
        
        # Should return a fresh BytesIO object with the cached content
        self.assertIsInstance(result, io.BytesIO)
        result.seek(0)
        self.assertEqual(result.read(), cached_bytes)
        self.mock_cache_manager.get.assert_called_with('downloads', 'download_test_file_id')

    @patch('piframe.services.drive_service.build')
    @patch('piframe.services.drive_service.MediaIoBaseDownload')
    def test_download_file_success(self, mock_downloader_class, mock_build):
        """Test successful file download."""
        self.mock_cache_manager.get.return_value = None
        
        # Mock service
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_service.files().get_media.return_value = mock_request
        mock_build.return_value = mock_service
        
        # Mock downloader
        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)
        mock_downloader_class.return_value = mock_downloader
        
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        # Mock file data
        test_data = b'test file data'
        
        with patch('io.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getbuffer().nbytes = len(test_data)
            mock_buffer.read.return_value = test_data
            mock_bytesio.return_value = mock_buffer
            
            result = self.drive_service.download_file('test_file_id')
            
            self.assertIsNotNone(result)
            mock_service.files().get_media.assert_called_with(fileId='test_file_id')

    @patch('piframe.services.drive_service.build')
    def test_download_file_empty_file(self, mock_build):
        """Test downloading empty file."""
        self.mock_cache_manager.get.return_value = None
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        with patch('io.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getbuffer().nbytes = 0  # Empty file
            mock_bytesio.return_value = mock_buffer
            
            with patch('piframe.services.drive_service.MediaIoBaseDownload'):
                result = self.drive_service.download_file('test_file_id')
                
                self.assertIsNone(result)

    def test_should_retry_download(self):
        """Test download retry logic."""
        # Should retry
        self.assertTrue(self.drive_service._should_retry_download("SSL error occurred"))
        self.assertTrue(self.drive_service._should_retry_download("Connection timeout"))
        self.assertTrue(self.drive_service._should_retry_download("Network unreachable"))
        
        # Should not retry
        self.assertFalse(self.drive_service._should_retry_download("File not found"))
        self.assertFalse(self.drive_service._should_retry_download("Permission denied"))

    def test_cache_download(self):
        """Test download caching."""
        file_buffer = io.BytesIO(b'test data')
        
        self.drive_service._cache_download('test_file_id', file_buffer)
        
        self.mock_cache_manager.set.assert_called_once()
        call_args = self.mock_cache_manager.set.call_args
        self.assertEqual(call_args[0][0], 'downloads')
        self.assertEqual(call_args[0][1], 'download_test_file_id')

    def test_get_random_image_success(self):
        """Test getting random image successfully."""
        test_files = [
            {'id': '1', 'name': 'test1.jpg', 'type': 'image/jpeg'},
            {'id': '2', 'name': 'test2.jpg', 'type': 'image/jpeg'},
            {'id': '3', 'name': 'test3.jpg', 'type': 'image/jpeg'}
        ]
        
        with patch.object(self.drive_service, 'list_images_in_folder', return_value=test_files):
            result = self.drive_service.get_random_image()
            
            self.assertIsNotNone(result)
            self.assertIn(result, test_files)
            # Should track as recently served
            self.assertIn(result['id'], self.drive_service._recently_served)

    def test_get_random_image_no_files(self):
        """Test getting random image with no files."""
        with patch.object(self.drive_service, 'list_images_in_folder', return_value=[]):
            result = self.drive_service.get_random_image()
            
            self.assertIsNone(result)

    def test_get_random_image_avoid_recent(self):
        """Test avoiding recently served images."""
        test_files = [
            {'id': '1', 'name': 'test1.jpg', 'type': 'image/jpeg'},
            {'id': '2', 'name': 'test2.jpg', 'type': 'image/jpeg'},
            {'id': '3', 'name': 'test3.jpg', 'type': 'image/jpeg'}
        ]
        
        # Mark one as recently served
        self.drive_service._recently_served = ['1']
        
        with patch.object(self.drive_service, 'list_images_in_folder', return_value=test_files):
            result = self.drive_service.get_random_image()
            
            self.assertIsNotNone(result)
            self.assertNotEqual(result['id'], '1')  # Should avoid recently served

    def test_get_random_image_reset_recent_list(self):
        """Test resetting recently served list when all served."""
        test_files = [
            {'id': '1', 'name': 'test1.jpg', 'type': 'image/jpeg'},
            {'id': '2', 'name': 'test2.jpg', 'type': 'image/jpeg'}
        ]
        
        # Mark both as recently served
        self.drive_service._recently_served = ['1', '2']
        
        with patch.object(self.drive_service, 'list_images_in_folder', return_value=test_files):
            result = self.drive_service.get_random_image()
            
            self.assertIsNotNone(result)
            # Recently served list should be reset and contain only the new selection
            self.assertEqual(len(self.drive_service._recently_served), 1)

    @patch('piframe.services.drive_service.build')
    def test_get_file_by_id_from_cache(self, mock_build):
        """Test getting file by ID from cached list."""
        test_files = [
            {'id': '1', 'name': 'test1.jpg', 'type': 'image/jpeg'},
            {'id': '2', 'name': 'test2.jpg', 'type': 'image/jpeg'}
        ]
        
        with patch.object(self.drive_service, 'list_images_in_folder', return_value=test_files):
            result = self.drive_service.get_file_by_id('1')
            
            self.assertEqual(result['name'], 'test1.jpg')

    @patch('piframe.services.drive_service.build')
    def test_get_file_by_id_from_api(self, mock_build):
        """Test getting file by ID from API."""
        # Mock empty file list
        with patch.object(self.drive_service, 'list_images_in_folder', return_value=[]):
            mock_service = MagicMock()
            mock_service.files().get().execute.return_value = {
                'id': 'test_id',
                'name': 'test.jpg',
                'mimeType': 'image/jpeg',
                'webViewLink': 'https://drive.google.com/file/d/test_id/view'
            }
            mock_build.return_value = mock_service
            
            mock_creds = MagicMock()
            mock_creds.valid = True
            self.drive_service._credentials = mock_creds
            
            result = self.drive_service.get_file_by_id('test_id')
            
            self.assertEqual(result['name'], 'test.jpg')
            self.assertEqual(result['id'], 'test_id')

    @patch('piframe.services.drive_service.build')
    def test_get_file_by_id_not_found(self, mock_build):
        """Test getting file by ID when not found."""
        with patch.object(self.drive_service, 'list_images_in_folder', return_value=[]):
            mock_service = MagicMock()
            mock_service.files().get().execute.side_effect = Exception("File not found")
            mock_build.return_value = mock_service
            
            mock_creds = MagicMock()
            mock_creds.valid = True
            self.drive_service._credentials = mock_creds
            
            result = self.drive_service.get_file_by_id('nonexistent_id')
            
            self.assertIsNone(result)

    def test_clear_download_cache(self):
        """Test clearing download cache."""
        self.drive_service.clear_download_cache()
        
        self.mock_cache_manager.clear_cache.assert_called_with('downloads')

    def test_force_refresh_file_list(self):
        """Test forcing file list refresh."""
        with patch.object(self.drive_service, 'list_images_in_folder') as mock_list:
            mock_list.return_value = []
            
            result = self.drive_service.force_refresh_file_list()
            
            mock_list.assert_called_with(None, force_refresh=True)

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        mock_stats = {
            'files': {'hit_count': 10, 'miss_count': 2},
            'downloads': {'hit_count': 5, 'miss_count': 1}
        }
        self.mock_cache_manager.get_all_stats.return_value = mock_stats
        
        result = self.drive_service.get_cache_stats()
        
        self.assertEqual(result['files_cache'], mock_stats['files'])
        self.assertEqual(result['downloads_cache'], mock_stats['downloads'])
        self.assertIsInstance(result['recently_served_count'], int)

    def test_close(self):
        """Test service cleanup."""
        self.drive_service._service = MagicMock()
        self.drive_service._credentials = MagicMock()
        
        self.drive_service.close()
        
        self.assertIsNone(self.drive_service._service)
        self.assertIsNone(self.drive_service._credentials)


if __name__ == '__main__':
    unittest.main()