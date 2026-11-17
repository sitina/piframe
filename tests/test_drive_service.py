"""
Tests for DriveService class from the new modular architecture.
"""
import unittest
import io
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piframe.services.drive_service import DriveService, AuthenticationRequired, CredentialRefreshUnavailable
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
        self.mock_cache_manager.get_stale.return_value = None
        
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

    def test_load_credentials_existing_valid(self):
        creds = MagicMock(valid=True)
        with patch.object(self.drive_service.credential_store, 'load', return_value=creds):
            self.assertIs(self.drive_service._load_credentials(), creds)

    def test_load_credentials_corrupted_token_is_preserved(self):
        from piframe.services.credential_store import CredentialStoreError
        with patch.object(self.drive_service.credential_store, 'load',
                          side_effect=CredentialStoreError('malformed')), \
             patch('google_auth_oauthlib.flow.InstalledAppFlow') as flow:
            with self.assertRaises(CredentialStoreError):
                self.drive_service._load_credentials()
            flow.from_client_secrets_file.assert_not_called()

    def test_permission_failure_preserves_actionable_remedy(self):
        from piframe.services.credential_store import CredentialPermissionError
        error = CredentialPermissionError('run chmod 600 fixture-token.json')
        with patch.object(self.drive_service.credential_store, 'load', side_effect=error):
            with self.assertRaisesRegex(CredentialPermissionError, 'chmod 600'):
                self.drive_service._load_credentials()

    def test_load_credentials_expired_with_refresh(self):
        creds = MagicMock(valid=False, expired=True, refresh_token='fixture')
        creds.refresh.side_effect = lambda request: setattr(creds, 'valid', True)
        with patch.object(self.drive_service.credential_store, 'load', return_value=creds), \
             patch.object(self.drive_service.credential_store, 'save') as save, \
             patch('piframe.services.drive_service.Request'):
            self.assertIs(self.drive_service._load_credentials(), creds)
            creds.refresh.assert_called_once()
            save.assert_called_once_with(creds)

    def test_load_credentials_no_credentials_file(self):
        with patch.object(self.drive_service.credential_store, 'load', return_value=None), \
             patch('os.path.exists', return_value=False):
            with self.assertRaises(AuthenticationRequired):
                self.drive_service._load_credentials()

    def test_credentials_property(self):
        """Test credentials property caching."""
        mock_creds = MagicMock()
        mock_creds.valid = True
        self.drive_service._credentials = mock_creds
        
        result = self.drive_service.credentials
        
        self.assertEqual(result, mock_creds)

    def test_refresh_failure_never_starts_oauth_or_overwrites_token(self):
        from google.auth.exceptions import RefreshError
        for error, expected in [(OSError('offline'), CredentialRefreshUnavailable),
                                (RefreshError('revoked'), AuthenticationRequired),
                                (RefreshError('busy', retryable=True), CredentialRefreshUnavailable)]:
            creds = MagicMock(valid=False, refresh_token='fixture')
            creds.refresh.side_effect = error
            with self.subTest(error=type(error).__name__), \
                 patch.object(self.drive_service.credential_store, 'load', return_value=creds), \
                 patch.object(self.drive_service.credential_store, 'save') as save, \
                 patch('google_auth_oauthlib.flow.InstalledAppFlow') as flow:
                with self.assertRaises(expected):
                    self.drive_service._load_credentials()
                save.assert_not_called()
                flow.from_client_secrets_file.assert_not_called()

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
        mock_build.assert_called_with(
            'drive', 'v3', credentials=mock_creds, cache_discovery=False)

    def test_concurrent_api_operations_do_not_share_transport(self):
        """Preloads, downloads and metadata requests must not overlap HTTP use."""
        active = 0
        maximum = 0
        counter_lock = threading.Lock()
        start = threading.Barrier(3)
        info = {'id': 'photo', 'name': 'photo.jpg', 'mimeType': 'image/jpeg',
                'webViewLink': 'fixture-view', 'size': '13'}

        def transport_call(result):
            nonlocal active, maximum
            with counter_lock:
                active += 1
                maximum = max(maximum, active)
            try:
                # Simulate network I/O releasing the GIL while other workers run.
                threading.Event().wait(0.02)
                return result
            finally:
                with counter_lock:
                    active -= 1

        api = MagicMock()
        api.files.return_value.list.return_value.execute.side_effect = (
            lambda: transport_call({'files': [info]}))
        api.files.return_value.get.return_value.execute.side_effect = (
            lambda: transport_call(info))
        self.drive_service._service = api

        class Downloader:
            def __init__(self, buffer, request, **kwargs):
                self.buffer = buffer

            def next_chunk(self):
                self.buffer.write(b'fixture image')
                return transport_call((None, True))

        def run(operation):
            start.wait(timeout=5)
            return operation()

        with patch('piframe.services.drive_service.MediaIoBaseDownload', Downloader), \
             patch.object(self.drive_service, 'list_images_in_folder', return_value=[]):
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [pool.submit(run, operation) for operation in [
                    lambda: self.drive_service._fetch_all_pages('fixture query'),
                    lambda: self.drive_service._execute_download('photo'),
                    lambda: self.drive_service.get_file_by_id('photo'),
                ]]
                results = [future.result(timeout=5) for future in futures]

        self.assertEqual(maximum, 1, 'HTTP transport used concurrently')
        self.assertEqual(results[0], [info])
        self.assertEqual(results[1].getvalue(), b'fixture image')
        self.assertEqual(results[2]['id'], 'photo')

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
        
        # Should stop at safety limit (100 pages)
        self.assertEqual(len(result), 100)  # 100 pages * 1 file per page
        self.assertEqual(mock_list_call().execute.call_count, 100)

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

    def test_download_file_success_and_empty_file(self):
        self.mock_cache_manager.get.return_value = None
        api = MagicMock()
        api.files.return_value.get.return_value.execute.return_value = {'size': '13'}
        self.drive_service._service = api
        for payload in [b'fixture image', b'']:
            class Downloader:
                def __init__(self, stream, request, **kwargs):
                    self.stream = stream
                def next_chunk(self):
                    self.stream.write(payload)
                    return None, True
            with self.subTest(payload=payload), \
                 patch('piframe.services.drive_service.MediaIoBaseDownload', Downloader):
                result = self.drive_service.download_file('photo')
                if payload:
                    self.assertEqual(result.getvalue(), payload)
                else:
                    self.assertIsNone(result)

    def test_should_retry_download(self):
        """Test download retry logic."""
        # Should retry AND reset service (SSL errors)
        should_retry, should_reset = self.drive_service._should_retry_download("SSL error occurred")
        self.assertTrue(should_retry)
        self.assertTrue(should_reset)

        should_retry, should_reset = self.drive_service._should_retry_download("record layer failure")
        self.assertTrue(should_retry)
        self.assertTrue(should_reset)

        # Should retry but NOT reset service (network errors)
        should_retry, should_reset = self.drive_service._should_retry_download("Connection timeout")
        self.assertTrue(should_retry)
        self.assertFalse(should_reset)

        should_retry, should_reset = self.drive_service._should_retry_download("Network unreachable")
        self.assertTrue(should_retry)
        self.assertFalse(should_reset)

        # Should not retry at all
        should_retry, should_reset = self.drive_service._should_retry_download("File not found")
        self.assertFalse(should_retry)
        self.assertFalse(should_reset)

        should_retry, should_reset = self.drive_service._should_retry_download("Permission denied")
        self.assertFalse(should_retry)
        self.assertFalse(should_reset)

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
