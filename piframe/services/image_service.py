"""
Image service for PiFrame application.
Handles image serving, metadata extraction, and Flask responses.
"""

import io
import time
from typing import Optional, Dict, Any, Tuple

from flask import Response, send_file

from ..config.settings import Config
from ..models.cache import CacheManager, get_cache_manager
from ..utils.logging import LoggerMixin, log_performance
from .drive_service import DriveService
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import image_metadata


class ImageService(LoggerMixin):
    """Service for image serving and metadata extraction."""
    
    def __init__(self, config: Config, drive_service: DriveService,
                 cache_manager: Optional[CacheManager] = None):
        """
        Initialize image service.
        
        Args:
            config: Application configuration
            drive_service: Google Drive service instance
            cache_manager: Cache manager instance
        """
        self.config = config
        self.drive_service = drive_service
        self.cache_manager = cache_manager or get_cache_manager(config)
        
        # Synchronized image state for metadata consistency
        self._current_image_id = None
        self._current_image_metadata = None
        self._current_image_timestamp = 0
    
    @log_performance
    def serve_random_image(self, force_new: bool = False, 
                         include_metadata: bool = False) -> Response:
        """
        Serve a random image with optional metadata.
        
        Args:
            force_new: Force selection of a new image (bypass recently served)
            include_metadata: Include metadata in response headers
            
        Returns:
            Flask Response with image data
        """
        try:
            # Get random image info
            self.logger.info("Selecting random image")
            image_info = self.drive_service.get_random_image(avoid_recent=not force_new)
            
            if not image_info:
                self.logger.error("No images available")
                return Response("No images found", status=404, mimetype='text/plain')
            
            self.logger.info(f"Selected image: {image_info['name']} ({image_info['id']})")
            
            # Clear cache if force_new
            if force_new:
                cache_key = f"download_{image_info['id']}"
                self.cache_manager.delete('downloads', cache_key)
                self.logger.debug(f"Cleared download cache for {image_info['id']}")
            
            # Download image data
            image_data = self.drive_service.download_file(image_info['id'])
            if not image_data:
                self.logger.error(f"Failed to download image {image_info['id']}")
                return Response("Error downloading image", status=500, mimetype='text/plain')
            
            # Extract metadata if requested
            metadata_info = None
            if include_metadata:
                self.logger.debug("Extracting image metadata")
                metadata_info = self.get_image_metadata(image_info['id'], image_data)
            
            # Create Flask response
            response = self._create_image_response(image_info, image_data, metadata_info)
            
            # Update synchronized state
            if include_metadata:
                self._current_image_id = image_info['id']
                self._current_image_metadata = metadata_info
                self._current_image_timestamp = time.time()
            
            self.logger.info(f"Successfully served image: {image_info['name']}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error serving random image: {e}", exc_info=True)
            return Response("Internal server error", status=500, mimetype='text/plain')
    
    @log_performance
    def serve_image_by_id(self, file_id: str, include_metadata: bool = True) -> Response:
        """
        Serve a specific image by ID.
        
        Args:
            file_id: Google Drive file ID
            include_metadata: Include metadata in response headers
            
        Returns:
            Flask Response with image data
        """
        try:
            # Get file info
            image_info = self.drive_service.get_file_by_id(file_id)
            if not image_info:
                self.logger.error(f"Image not found: {file_id}")
                return Response("Image not found", status=404, mimetype='text/plain')
            
            self.logger.info(f"Serving specific image: {image_info['name']} ({file_id})")
            
            # Download image data
            image_data = self.drive_service.download_file(file_id)
            if not image_data:
                self.logger.error(f"Failed to download image {file_id}")
                return Response("Error downloading image", status=500, mimetype='text/plain')
            
            # Extract metadata if requested
            metadata_info = None
            if include_metadata:
                metadata_info = self.get_image_metadata(file_id, image_data)
            
            # Create Flask response
            response = self._create_image_response(image_info, image_data, metadata_info)
            
            self.logger.info(f"Successfully served specific image: {image_info['name']}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error serving image {file_id}: {e}", exc_info=True)
            return Response("Internal server error", status=500, mimetype='text/plain')
    
    def serve_synchronized_image(self) -> Response:
        """
        Serve the current synchronized image (for metadata consistency).
        
        Returns:
            Flask Response with synchronized image data
        """
        # Check if we have a current synchronized image (within 5 seconds)
        if (self._current_image_id and 
            time.time() - self._current_image_timestamp < 5):
            
            self.logger.debug(f"Serving synchronized image: {self._current_image_id}")
            return self.serve_image_by_id(self._current_image_id, include_metadata=False)
        else:
            # Fall back to random image
            self.logger.debug("No synchronized image available, serving random")
            return self.serve_random_image(force_new=False, include_metadata=False)
    
    def get_random_image_metadata(self) -> Dict[str, Any]:
        """
        Get metadata for a new random image.
        
        Returns:
            Dictionary with image metadata
        """
        try:
            # Get a new random image with metadata
            response = self.serve_random_image(force_new=True, include_metadata=True)
            
            # Extract metadata from current state
            if self._current_image_metadata and self._current_image_metadata.get('display_info'):
                display = self._current_image_metadata['display_info']
                metadata = {
                    'creation_date': display.get('creation_date', 'Unknown'),
                    'creation_time': display.get('creation_time', 'Unknown'),
                    'camera_info': display.get('camera_info', 'Unknown'),
                    'dimensions': display.get('dimensions', 'Unknown'),
                    'picture_url': f'/random-picture/synchronized?t={int(time.time())}'
                }
                
                self.logger.debug("Extracted metadata for random image")
                return metadata
            else:
                # Return default metadata
                return self._get_default_metadata()
                
        except Exception as e:
            self.logger.error(f"Error getting random image metadata: {e}")
            return self._get_default_metadata()
    
    def get_image_metadata(self, file_id: str, image_data: io.BytesIO) -> Optional[Dict[str, Any]]:
        """
        Extract and cache metadata for an image.
        
        Args:
            file_id: Google Drive file ID
            image_data: Image file data
            
        Returns:
            Dictionary with metadata information
        """
        cache_key = f"metadata_{file_id}"
        
        # Check cache first
        cached_metadata = self.cache_manager.get('metadata', cache_key)
        if cached_metadata is not None:
            self.logger.debug(f"Using cached metadata for {file_id}")
            return cached_metadata
        
        try:
            # Extract metadata using existing module
            image_data.seek(0)  # Ensure we're at the beginning
            metadata = image_metadata.extract_image_metadata(image_data)
            display_info = image_metadata.format_metadata_for_display(metadata)
            
            # Package the metadata
            metadata_info = {
                'metadata': metadata,
                'display_info': display_info,
                'timestamp': time.time()
            }
            
            # Cache the result
            self.cache_manager.set('metadata', cache_key, metadata_info)
            
            self.logger.debug(f"Extracted and cached metadata for {file_id}")
            return metadata_info
            
        except Exception as e:
            self.logger.warning(f"Error extracting metadata for {file_id}: {e}")
            # Return default metadata info
            default_info = self._get_default_display_info()
            metadata_info = {
                'metadata': {},
                'display_info': default_info,
                'timestamp': time.time()
            }
            return metadata_info
    
    def _create_image_response(self, image_info: Dict[str, Any], 
                             image_data: io.BytesIO,
                             metadata_info: Optional[Dict[str, Any]] = None) -> Response:
        """
        Create Flask response for image data.
        
        Args:
            image_info: Image file information
            image_data: Image file data
            metadata_info: Optional metadata information
            
        Returns:
            Flask Response object
        """
        # Create the response
        image_data.seek(0)
        response = send_file(
            image_data,
            mimetype=image_info['type'],
            as_attachment=False,
            download_name=image_info['name']
        )
        
        # Add cache control headers (encourage refresh)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['ETag'] = f'"{image_info["id"]}_{int(time.time())}"'
        
        # Add image ID for synchronization
        response.headers['X-Image-ID'] = image_info['id']
        
        # Add metadata headers if available
        if metadata_info and metadata_info.get('display_info'):
            display = metadata_info['display_info']
            response.headers['X-Image-Date'] = display.get('creation_date', 'Unknown')
            response.headers['X-Image-Time'] = display.get('creation_time', 'Unknown')
            response.headers['X-Camera-Info'] = display.get('camera_info', 'Unknown')
            response.headers['X-Image-Dimensions'] = display.get('dimensions', 'Unknown')
        
        return response
    
    def _get_default_metadata(self) -> Dict[str, Any]:
        """Get default metadata structure."""
        return {
            'creation_date': 'Unknown',
            'creation_time': 'Unknown',
            'camera_info': 'Unknown camera',
            'dimensions': 'Unknown',
            'picture_url': f'/random-picture?t={int(time.time())}'
        }
    
    def _get_default_display_info(self) -> Dict[str, str]:
        """Get default display info structure."""
        return {
            'creation_date': 'Unknown',
            'creation_time': 'Unknown',
            'camera_info': 'Unknown camera',
            'dimensions': 'Unknown',
            'format': 'Unknown'
        }
    
    def clear_metadata_cache(self) -> None:
        """Clear the metadata cache."""
        self.cache_manager.clear_cache('metadata')
        self.logger.info("Metadata cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for image-related caches."""
        stats = self.cache_manager.get_all_stats()
        return {
            'metadata_cache': stats.get('metadata', {}),
            'synchronized_image_id': self._current_image_id,
            'synchronized_age_seconds': time.time() - self._current_image_timestamp if self._current_image_id else None
        }
    
    def close(self) -> None:
        """Close the service and clean up resources."""
        self._current_image_id = None
        self._current_image_metadata = None
        self.logger.info("Image service closed")