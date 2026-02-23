"""
Google Drive service for PiFrame application.
Handles Drive API authentication, file operations, and caching.
"""

import io
import os
import pickle
import random
import threading
import time
from typing import List, Dict, Any, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from ..config.settings import Config
from ..models.cache import CacheManager, get_cache_manager
from ..utils.logging import LoggerMixin, log_performance


class DriveService(LoggerMixin):
    """Service for Google Drive API operations."""
    
    # Google Drive API scope
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    # Supported image MIME types
    IMAGE_MIME_TYPES = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/bmp',
        'image/webp'
    ]

    # Pagination limits for Drive API listing
    PAGE_SIZE = 1000
    MAX_PAGES = 100  # Safety limit: PAGE_SIZE * MAX_PAGES = 100,000 files max

    # Recently-served tracking: prevents the same image from appearing
    # back-to-back. Capped at half the album size to avoid starving selection.
    MAX_RECENT_SERVED = 3
    
    def __init__(self, config: Config, cache_manager: Optional[CacheManager] = None):
        """
        Initialize Drive service.
        
        Args:
            config: Application configuration
            cache_manager: Cache manager instance
        """
        self.config = config
        self.cache_manager = cache_manager or get_cache_manager(config)
        self._credentials = None
        self._service = None
        self._recently_served = []
        self._recently_served_lock = threading.Lock()
        
    @property
    def credentials(self) -> Optional[Credentials]:
        """Get or load Google Drive credentials."""
        if self._credentials is not None and self._credentials.valid:
            return self._credentials
        
        return self._load_credentials()
    
    @property
    def service(self):
        """Get or create Google Drive service."""
        if self._service is None:
            creds = self.credentials
            if creds:
                self._service = build('drive', 'v3', credentials=creds)
                self.logger.info("Google Drive service created successfully")
            else:
                self.logger.error("Cannot create Drive service without valid credentials")
                raise RuntimeError("Invalid Google Drive credentials")
        
        return self._service
    
    def _load_credentials(self) -> Optional[Credentials]:
        """Load and validate Google Drive credentials."""
        creds = None
        
        # Load existing token
        if os.path.exists(self.config.drive_token_file):
            try:
                with open(self.config.drive_token_file, 'rb') as token:
                    creds = pickle.load(token)
                    self.logger.debug("Loaded existing credentials from token file")
            except (EOFError, pickle.UnpicklingError, FileNotFoundError) as e:
                self.logger.warning(f"Error loading token file: {e}")
                self.logger.info("Removing corrupted token file")
                try:
                    os.remove(self.config.drive_token_file)
                except OSError:
                    pass
                creds = None
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    self.logger.info("Refreshing expired credentials")
                    creds.refresh(Request())
                except Exception as e:
                    self.logger.error(f"Error refreshing credentials: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.config.drive_credentials_file):
                    self.logger.error(f"Credentials file not found: {self.config.drive_credentials_file}")
                    return None
                
                try:
                    self.logger.info("Starting OAuth flow for new credentials")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.config.drive_credentials_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    self.logger.error(f"Error during OAuth flow: {e}")
                    return None
            
            # Save credentials
            try:
                with open(self.config.drive_token_file, 'wb') as token:
                    pickle.dump(creds, token)
                self.logger.info("Credentials saved successfully")
            except Exception as e:
                self.logger.error(f"Error saving credentials: {e}")
        
        self._credentials = creds
        return creds
    
    @log_performance
    def list_images_in_folder(self, folder_id: Optional[str] = None,
                            force_refresh: bool = False,
                            max_retries: int = 3) -> List[Dict[str, Any]]:
        """
        List all image files in a Google Drive folder.

        Args:
            folder_id: Drive folder ID (uses config default if None)
            force_refresh: Skip cache and fetch fresh data
            max_retries: Maximum number of retry attempts for transient errors

        Returns:
            List of image file information dictionaries
        """
        if folder_id is None:
            folder_id = self.config.album_id

        if not folder_id:
            self.logger.error("No folder ID provided and none configured")
            return []

        cache_key = f"files_{folder_id}"

        # Try cache first unless force refresh
        if not force_refresh:
            cached_files = self.cache_manager.get('files', cache_key)
            if cached_files is not None:
                self.logger.debug(f"Using cached file list for folder {folder_id}")
                return cached_files

        return self._fetch_images_with_retry(folder_id, cache_key, max_retries)

    def _build_image_query(self, folder_id: str) -> str:
        """Build Drive API query for image files in folder."""
        mime_query = ' or '.join([f"mimeType='{mt}'" for mt in self.IMAGE_MIME_TYPES])
        query_parts = [f"({mime_query})"]
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        return ' and '.join(query_parts)

    def _fetch_all_pages(self, query: str) -> List[Dict[str, Any]]:
        """Fetch all pages of results from Drive API."""
        all_items = []
        page_token = None
        page_count = 0

        while True:
            page_count += 1
            self.logger.debug(f"Fetching page {page_count} from Drive API")

            request_params = {
                'q': query,
                'pageSize': self.PAGE_SIZE,
                'fields': "nextPageToken, files(id, name, mimeType, webViewLink, createdTime, modifiedTime)"
            }
            if page_token:
                request_params['pageToken'] = page_token

            results = self.service.files().list(**request_params).execute()

            page_items = results.get('files', [])
            all_items.extend(page_items)

            self.logger.debug(f"Page {page_count}: found {len(page_items)} items (total: {len(all_items)})")

            page_token = results.get('nextPageToken')
            if not page_token:
                break

            if page_count >= self.MAX_PAGES:
                self.logger.warning(f"Pagination safety limit reached after {page_count} pages")
                break

        return all_items

    def _process_file_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process raw API items into file info dictionaries."""
        file_list = []
        for item in items:
            file_dict = {
                'id': item['id'],
                'name': item['name'],
                'type': item['mimeType'],
                'link': item['webViewLink']
            }
            if 'createdTime' in item:
                file_dict['createdTime'] = item['createdTime']
            if 'modifiedTime' in item:
                file_dict['modifiedTime'] = item['modifiedTime']
            file_list.append(file_dict)
        return file_list

    def _fetch_images_with_retry(self, folder_id: str, cache_key: str,
                                  max_retries: int) -> List[Dict[str, Any]]:
        """Fetch images from Drive with retry logic for transient errors."""
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Fetching image list from Drive folder: {folder_id} (attempt {attempt + 1}/{max_retries})")

                query = self._build_image_query(folder_id)
                items = self._fetch_all_pages(query)

                if not items:
                    self.logger.warning(f"No images found in folder {folder_id}")
                    self.cache_manager.set('files', cache_key, [])
                    return []

                file_list = self._process_file_items(items)
                self.cache_manager.set('files', cache_key, file_list)

                self.logger.info(f"Found {len(file_list)} images in folder {folder_id}")
                return file_list

            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"List images attempt {attempt + 1} failed: {error_msg}")

                should_retry, should_reset = self._should_retry_download(error_msg)

                if should_reset:
                    self._reset_service()

                if should_retry and attempt < max_retries - 1:
                    self.logger.info(f"Retrying list images in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue

                self.logger.error(f"Error listing images from Drive: {e}", exc_info=True)

                cached_files = self.cache_manager.get('files', cache_key)
                if cached_files is not None:
                    self.logger.info("Using expired cached file list as fallback")
                    return cached_files

                return []

        return []
    
    def _get_cached_download(self, file_id: str, cache_key: str) -> Optional[io.BytesIO]:
        """
        Get cached download if available and valid.

        Args:
            file_id: Google Drive file ID
            cache_key: Cache key for the download

        Returns:
            BytesIO object if cache hit, None otherwise
        """
        cached_data = self.cache_manager.get('downloads', cache_key)
        if cached_data is None:
            return None

        self.logger.debug(f"Using cached download for file {file_id}")
        try:
            # Handle both old BytesIO objects and new raw bytes
            if isinstance(cached_data, bytes):
                fresh_copy = io.BytesIO(cached_data)
                fresh_copy.seek(0)
                self.logger.debug(f"Created fresh BytesIO from cached bytes for {file_id} ({len(cached_data)} bytes)")
                return fresh_copy
            elif hasattr(cached_data, 'read'):
                if hasattr(cached_data, 'closed') and cached_data.closed:
                    self.logger.warning(f"Cached BytesIO for {file_id} is closed, removing from cache")
                    self.cache_manager.delete('downloads', cache_key)
                else:
                    cached_data.seek(0)
                    fresh_copy = io.BytesIO(cached_data.read())
                    fresh_copy.seek(0)
                    self.logger.debug(f"Created fresh copy from cached BytesIO for {file_id}")
                    return fresh_copy
            else:
                self.logger.warning(f"Invalid cached data format for {file_id}, removing from cache")
                self.cache_manager.delete('downloads', cache_key)
        except (ValueError, OSError, AttributeError) as e:
            self.logger.warning(f"Cached download for {file_id} is invalid ({e}), removing from cache")
            self.cache_manager.delete('downloads', cache_key)

        return None

    def _execute_download(self, file_id: str) -> io.BytesIO:
        """
        Execute the actual download from Google Drive.

        Args:
            file_id: Google Drive file ID

        Returns:
            BytesIO object containing file data

        Raises:
            ValueError: If downloaded file is empty
            Exception: On API errors
        """
        request = self.service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                if progress % 25 == 0:
                    self.logger.debug(f"Download progress: {progress}%")

        file_buffer.seek(0)
        if file_buffer.getbuffer().nbytes == 0:
            raise ValueError("Downloaded file is empty")

        return file_buffer

    @log_performance
    def download_file(self, file_id: str, max_retries: int = 3) -> Optional[io.BytesIO]:
        """
        Download a file from Google Drive with caching and retry logic.

        Args:
            file_id: Google Drive file ID
            max_retries: Maximum number of retry attempts

        Returns:
            BytesIO object containing file data or None if failed
        """
        cache_key = f"download_{file_id}"

        # Check cache first
        cached = self._get_cached_download(file_id, cache_key)
        if cached is not None:
            return cached

        retry_delay = 1

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Downloading file {file_id} (attempt {attempt + 1}/{max_retries})")

                file_buffer = self._execute_download(file_id)

                self._cache_download(file_id, file_buffer)

                self.logger.info(f"Successfully downloaded file {file_id}")
                file_buffer.seek(0)
                return file_buffer

            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"Download attempt {attempt + 1} failed: {error_msg}")

                should_retry, should_reset = self._should_retry_download(error_msg)

                if should_reset:
                    self._reset_service()

                if should_retry and attempt < max_retries - 1:
                    self.logger.info(f"Retrying download in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue

                break

        self.logger.error(f"Failed to download file {file_id} after {max_retries} attempts")
        return None
    
    def _reset_service(self) -> None:
        """Reset the Drive service to force new connection."""
        self._service = None
        self.logger.info("Drive service reset - will create new connection on next request")

    def _should_retry_download(self, error_msg: str) -> Tuple[bool, bool]:
        """
        Determine if a download error should trigger a retry and/or service reset.

        Returns:
            (should_retry, should_reset_service) based on error message keywords.
            Network/timeout errors trigger retry; SSL errors also trigger service reset.
        """
        retry_keywords = ['timeout', 'connection', 'network', 'reset', 'broken pipe']
        ssl_keywords = ['ssl', 'handshake', 'certificate', 'record layer']

        error_lower = error_msg.lower()
        should_retry = any(keyword in error_lower for keyword in retry_keywords + ssl_keywords)
        should_reset = any(keyword in error_lower for keyword in ssl_keywords)

        return should_retry, should_reset
    
    def _cache_download(self, file_id: str, file_buffer: io.BytesIO) -> None:
        """Cache downloaded file with size management."""
        cache_key = f"download_{file_id}"
        
        # Store raw bytes instead of BytesIO object to avoid shared state issues
        file_buffer.seek(0)
        raw_bytes = file_buffer.read()
        
        # Store raw bytes in cache
        self.cache_manager.set('downloads', cache_key, raw_bytes)
        
        self.logger.debug(f"Cached download for file {file_id} ({len(raw_bytes)} bytes)")
    
    def get_random_image(self, folder_id: Optional[str] = None, 
                        avoid_recent: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get a random image from the specified folder.
        
        Args:
            folder_id: Drive folder ID (uses config default if None)
            avoid_recent: Whether to avoid recently served images
            
        Returns:
            Random image file info or None if no images available
        """
        files = self.list_images_in_folder(folder_id)
        if not files:
            return None
        
        with self._recently_served_lock:
            available_files = files

            if avoid_recent and self._recently_served:
                recently_served_ids = set(self._recently_served)
                available_files = [f for f in files if f['id'] not in recently_served_ids]

                if not available_files:
                    # Every image has been served recently -- reset and allow all
                    available_files = files
                    self._recently_served.clear()
                    self.logger.debug("Reset recently served list - all images served")

            random_file = random.choice(available_files)
            self._recently_served.append(random_file['id'])

            # Cap the history so we never block more than half the album
            max_recent = min(self.MAX_RECENT_SERVED, len(files) // 2)
            if len(self._recently_served) > max_recent:
                self._recently_served = self._recently_served[-max_recent:]
        
        self.logger.info(f"Selected random image: {random_file['name']} ({random_file['id']})")
        return random_file
    
    def get_file_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get file information by ID.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            File information dictionary or None if not found
        """
        # Check in cached file list first
        files = self.list_images_in_folder()
        for file in files:
            if file['id'] == file_id:
                return file
        
        # If not found in cache, try API call
        try:
            result = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, webViewLink, createdTime, modifiedTime"
            ).execute()
            
            file_dict = {
                'id': result['id'],
                'name': result['name'],
                'type': result['mimeType'],
                'link': result['webViewLink']
            }
            # Include created and modified times if available
            if 'createdTime' in result:
                file_dict['createdTime'] = result['createdTime']
            if 'modifiedTime' in result:
                file_dict['modifiedTime'] = result['modifiedTime']
            return file_dict
        except Exception as e:
            self.logger.error(f"Error getting file {file_id}: {e}")
            return None
    
    def clear_download_cache(self) -> None:
        """Clear the download cache."""
        self.cache_manager.clear_cache('downloads')
        self.logger.info("Download cache cleared")
    
    def force_refresh_file_list(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Force refresh the file list cache."""
        return self.list_images_in_folder(folder_id, force_refresh=True)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for Drive-related caches."""
        stats = self.cache_manager.get_all_stats()
        with self._recently_served_lock:
            recently_served_count = len(self._recently_served)
        return {
            'files_cache': stats.get('files', {}),
            'downloads_cache': stats.get('downloads', {}),
            'recently_served_count': recently_served_count
        }
    
    def close(self) -> None:
        """Close the service and clean up resources."""
        self._service = None
        self._credentials = None
        self.logger.info("Drive service closed")