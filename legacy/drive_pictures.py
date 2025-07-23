# Standard library imports
import io
import os.path
import pickle
import random
import time
import threading
from functools import lru_cache

# Third-party imports
from flask import send_file, Response
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import requests

# Local imports
from . import image_metadata

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Global cache for better performance
_credentials_cache = None
_service_cache = None
_files_cache = {'data': [], 'ts': 0, 'folder_id': None}
CACHE_TTL = 3600  # 1 hour cache for file listing

# Metadata cache
_metadata_cache = {}
METADATA_CACHE_SIZE = 20  # Keep metadata for 20 images

# Load configuration for refresh intervals
def load_refresh_config():
    """Load refresh intervals from config.json"""
    try:
        import json
        with open("config.json", "r") as f:
            config = json.load(f)
            return {
                'preload_interval': config.get('preload_interval', 900),  # 15 minutes default
                'preload_error_retry_interval': config.get('preload_error_retry_interval', 300)  # 5 minutes default
            }
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Return defaults if config file is not available
        return {
            'preload_interval': 900,  # 15 minutes default
            'preload_error_retry_interval': 300  # 5 minutes default
        }

def get_credentials():
    """Get valid user credentials from storage or user input with caching."""
    global _credentials_cache
    
    if _credentials_cache is not None and _credentials_cache.valid:
        return _credentials_cache
    
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        try:
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        except (EOFError, pickle.UnpicklingError, FileNotFoundError) as e:
            print(f"Error loading token.pickle: {e}")
            print("Removing corrupted token file and will create new one")
            try:
                os.remove('token.pickle')
            except OSError:
                pass
            creds = None
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                creds = None
        
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'client_secret.json', SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Error during OAuth flow: {e}")
                raise
        
        # Save the credentials for the next run
        try:
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
            print("Credentials saved to token.pickle")
        except Exception as e:
            print(f"Error saving credentials: {e}")
    
    _credentials_cache = creds
    return creds

def get_service():
    """Get Google Drive service with caching."""
    global _service_cache
    
    if _service_cache is None:
        try:
            creds = get_credentials()
            
            # Create service with credentials only (no http parameter)
            _service_cache = build('drive', 'v3', credentials=creds)
            print("Successfully created Google Drive service")
            
        except Exception as e:
            print(f"Error creating Google Drive service: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    return _service_cache

def list_images_in_folder(folder_id=None, force_refresh=False):
    """
    List all image files in a specific Google Drive folder with caching.
    If folder_id is None, lists images from root directory.
    Returns a list of dictionaries containing file information.
    """
    global _files_cache
    
    ts = time.time()
    
    # Check if we can use cached data
    if (not force_refresh and 
        _files_cache['data'] and 
        _files_cache['folder_id'] == folder_id and 
        ts - _files_cache['ts'] < CACHE_TTL):
        return _files_cache['data']
    
    try:
        service = get_service()
        
        # Define image MIME types
        image_mime_types = [
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/bmp',
            'image/webp'
        ]
        
        # Construct the query using OR for each mimeType
        mime_query = ' or '.join([f"mimeType='{mt}'" for mt in image_mime_types])
        query_parts = [f"({mime_query})"]
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        
        query = ' and '.join(query_parts)
        
        # Call the Drive v3 API with the correct query
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, webViewLink)"
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            print('No images found.')
            _files_cache['data'] = []
            _files_cache['ts'] = ts
            _files_cache['folder_id'] = folder_id
            return []
        
        # Return a list of dictionaries with file information
        file_list = [{
            'name': item['name'],
            'type': item['mimeType'],
            'link': item['webViewLink'],
            'id': item['id']
        } for item in items]
        
        # Update cache
        _files_cache['data'] = file_list
        _files_cache['ts'] = ts
        _files_cache['folder_id'] = folder_id
        
        return file_list
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        if hasattr(e, 'resp') and hasattr(e.resp, 'status'):
            print(f"Status code: {e.resp.status}")
        if hasattr(e, 'content'):
            print(f"Error details: {e.content.decode('utf-8')}")
        return []

def get_random_image(folder_id):
    """Get a random image from the specified folder."""
    files = list_images_in_folder(folder_id)
    if not files:
        return None
    return random.choice(files)

# Cache for downloaded files to avoid repeated downloads
_download_cache = {}
DOWNLOAD_CACHE_SIZE = 5  # Reduced from 10 to 5 for more variety
CACHE_DURATION = 60  # Reduced from 300 to 60 seconds for more variety

def download_file(file_id):
    """Download a file from Google Drive with caching and improved error handling."""
    # Check cache first
    if file_id in _download_cache:
        cached_data = _download_cache[file_id]
        if time.time() - cached_data['ts'] < CACHE_DURATION:  # 1 minute cache instead of 5
            cached_data['data'].seek(0)
            return cached_data['data']
    
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            service = get_service()
            
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    print(f"Download progress: {int(status.progress() * 100)}%")
            
            fh.seek(0)
            
            # Verify we got some data
            if fh.getbuffer().nbytes == 0:
                raise Exception("Downloaded file is empty")
            
            # Cache the downloaded file
            if len(_download_cache) >= DOWNLOAD_CACHE_SIZE:
                # Remove oldest entry
                oldest_key = min(_download_cache.keys(), 
                               key=lambda k: _download_cache[k]['ts'])
                del _download_cache[oldest_key]
            
            _download_cache[file_id] = {
                'data': fh,
                'ts': time.time()
            }
            
            print(f"Successfully downloaded file {file_id}")
            return fh
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error downloading file (attempt {attempt + 1}/{max_retries}): {error_msg}")
            
            # Handle specific SSL errors
            if "SSL" in error_msg or "ssl" in error_msg.lower():
                print(f"SSL error detected, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            
            # Handle network timeouts
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                print(f"Network error detected, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            
            # For other errors, don't retry
            if attempt == max_retries - 1:
                print(f"Failed to download file after {max_retries} attempts")
                return None
            else:
                time.sleep(retry_delay)
                retry_delay *= 2
    
    return None

def serve_random_image(force_new=False, include_metadata=False):
    """Serve a random image from the Google Drive folder with optimizations."""
    folder_id = '1USBfMHxXEZiL1XS562A6WlApGBobVp3q'
    
    try:
        # Get all available images
        print(f"Fetching images from folder: {folder_id}")
        files = list_images_in_folder(folder_id)
        
        if not files:
            print("No images found in folder")
            return "No images found", 404
        
        print(f"Found {len(files)} images in folder")
        
        # Select a random image, but avoid recently served ones
        available_files = files.copy()
        
        # If force_new is True, clear recently served list
        if force_new and hasattr(serve_random_image, '_recently_served'):
            serve_random_image._recently_served = []
        
        # Remove recently served files from selection (last 3 served)
        if hasattr(serve_random_image, '_recently_served'):
            for recent_id in serve_random_image._recently_served:
                available_files = [f for f in available_files if f['id'] != recent_id]
            
            # If we've served all images recently, reset the list
            if not available_files:
                available_files = files.copy()
                serve_random_image._recently_served = []
        
        # Select random file
        random_file = random.choice(available_files)
        print(f"Selected image: {random_file['name']} (ID: {random_file['id']})")
        
        # Track recently served files
        if not hasattr(serve_random_image, '_recently_served'):
            serve_random_image._recently_served = []
        
        serve_random_image._recently_served.append(random_file['id'])
        
        # Keep only last 3 served files
        if len(serve_random_image._recently_served) > 3:
            serve_random_image._recently_served = serve_random_image._recently_served[-3:]
        
        # If force_new, bypass cache
        if force_new:
            # Clear this specific file from cache
            if random_file['id'] in _download_cache:
                del _download_cache[random_file['id']]
                print(f"Cleared cache for file: {random_file['id']}")
        
        print(f"Downloading file: {random_file['id']}")
        file_data = download_file(random_file['id'])
        
        if not file_data:
            print(f"Failed to download file: {random_file['id']}")
            return "Error downloading file", 500
        
        print(f"Successfully downloaded file: {random_file['name']}")
        
        # Extract metadata if requested
        metadata_info = None
        if include_metadata:
            print("Extracting metadata...")
            metadata_info = get_image_metadata(random_file['id'], file_data)
        
        # Add cache headers for better performance
        response = send_file(
            file_data,
            mimetype=random_file['type'],
            as_attachment=False,
            download_name=random_file['name']
        )
        
        # Add shorter caching headers to encourage refresh
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['ETag'] = f'"{random_file["id"]}_{int(time.time())}"'
        
        # Add image ID to response headers for synchronization
        response.headers['X-Image-ID'] = random_file['id']
        
        # Add metadata to response headers if available
        if metadata_info and metadata_info['display_info']:
            display = metadata_info['display_info']
            response.headers['X-Image-Date'] = display.get('creation_date', 'Unknown')
            response.headers['X-Image-Time'] = display.get('creation_time', 'Unknown')
            response.headers['X-Camera-Info'] = display.get('camera_info', 'Unknown')
            response.headers['X-Image-Dimensions'] = display.get('dimensions', 'Unknown')
        
        print(f"Successfully served image: {random_file['name']}")
        return response
        
    except Exception as e:
        print(f"Error in serve_random_image: {str(e)}")
        import traceback
        traceback.print_exc()
        return "Internal server error", 500

# Background task to preload images
def preload_images():
    """Background task to preload some images for faster serving."""
    folder_id = '1USBfMHxXEZiL1XS562A6WlApGBobVp3q'
    
    # Load refresh configuration
    refresh_config = load_refresh_config()
    preload_interval = refresh_config['preload_interval']
    preload_error_retry_interval = refresh_config['preload_error_retry_interval']
    
    while True:
        try:
            # Refresh file list more frequently
            list_images_in_folder(folder_id, force_refresh=True)
            
            # Clear download cache periodically for variety
            global _download_cache
            if len(_download_cache) > 0:
                print(f"Clearing download cache ({len(_download_cache)} items) for variety")
                _download_cache.clear()
            
            # Preload a few random images
            files = list_images_in_folder(folder_id)
            if files:
                # Preload 2 random images (reduced from 3)
                for _ in range(min(2, len(files))):
                    random_file = random.choice(files)
                    download_file(random_file['id'])
            
            time.sleep(preload_interval)  # Use configured interval
        except Exception as e:
            print(f"Preload error: {e}")
            time.sleep(preload_error_retry_interval)  # Use configured error retry interval

def start_preload_task():
    """Start background preload task."""
    preload_thread = threading.Thread(target=preload_images, daemon=True)
    preload_thread.start()

# Start preload task
start_preload_task()

def get_image_metadata(file_id, file_data):
    """Extract and cache metadata for an image file."""
    global _metadata_cache
    
    # Check if metadata is already cached
    if file_id in _metadata_cache:
        return _metadata_cache[file_id]
    
    try:
        # Extract metadata
        metadata = image_metadata.extract_image_metadata(file_data)
        display_info = image_metadata.format_metadata_for_display(metadata)
        
        # Cache the metadata
        if len(_metadata_cache) >= METADATA_CACHE_SIZE:
            # Remove oldest entry
            oldest_key = min(_metadata_cache.keys(), 
                           key=lambda k: _metadata_cache[k]['ts'])
            del _metadata_cache[oldest_key]
        
        _metadata_cache[file_id] = {
            'metadata': metadata,
            'display_info': display_info,
            'ts': time.time()
        }
        
        return _metadata_cache[file_id]
        
    except Exception as e:
        print(f"Error extracting metadata for {file_id}: {e}")
        # Return default metadata
        default_info = {
            'creation_date': 'Unknown',
            'creation_time': 'Unknown',
            'camera_info': 'Unknown camera',
            'dimensions': 'Unknown',
            'format': 'Unknown'
        }
        return {
            'metadata': {},
            'display_info': default_info,
            'ts': time.time()
        }

def serve_image_by_id(file_id):
    """Serve a specific image by its ID with metadata."""
    try:
        # Get file info from cache or fetch it
        files = list_images_in_folder()
        target_file = None
        
        for file in files:
            if file['id'] == file_id:
                target_file = file
                break
        
        if not target_file:
            print(f"Image with ID {file_id} not found")
            return "Image not found", 404
        
        print(f"Serving specific image: {target_file['name']} (ID: {target_file['id']})")
        
        # Download the file
        file_data = download_file(target_file['id'])
        
        if not file_data:
            print(f"Failed to download file: {target_file['id']}")
            return "Error downloading file", 500
        
        # Extract metadata
        metadata_info = get_image_metadata(target_file['id'], file_data)
        
        # Create response
        response = send_file(
            file_data,
            mimetype=target_file['type'],
            as_attachment=False,
            download_name=target_file['name']
        )
        
        # Add cache headers
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['ETag'] = f'"{target_file["id"]}_{int(time.time())}"'
        
        # Add image ID to response headers
        response.headers['X-Image-ID'] = target_file['id']
        
        # Add metadata to response headers if available
        if metadata_info and metadata_info['display_info']:
            display = metadata_info['display_info']
            response.headers['X-Image-Date'] = display.get('creation_date', 'Unknown')
            response.headers['X-Image-Time'] = display.get('creation_time', 'Unknown')
            response.headers['X-Camera-Info'] = display.get('camera_info', 'Unknown')
            response.headers['X-Image-Dimensions'] = display.get('dimensions', 'Unknown')
        
        print(f"Successfully served specific image: {target_file['name']}")
        return response
        
    except Exception as e:
        print(f"Error in serve_image_by_id: {str(e)}")
        import traceback
        traceback.print_exc()
        return "Internal server error", 500
