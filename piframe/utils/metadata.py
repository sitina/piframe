"""
Image metadata extraction utilities for PiFrame.
Extracts EXIF data and formats it for display.
"""
import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import exifread
from PIL import Image

logger = logging.getLogger(__name__)


def extract_image_metadata(image_data: io.BytesIO,
                          file_created_time: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract metadata from image data (BytesIO object).

    Args:
        image_data: BytesIO object containing image data
        file_created_time: Optional file creation time from Google Drive (RFC 3339 format)

    Returns:
        Dictionary with metadata information
    """
    metadata = {
        'creation_date': None,
        'creation_time': None,
        'camera_make': None,
        'camera_model': None,
        'filename': None,
        'file_size': None,
        'dimensions': None,
        'format': None
    }

    try:
        # Reset the BytesIO object to beginning
        image_data.seek(0)

        # Get basic file info
        metadata['file_size'] = len(image_data.getvalue())

        # Use PIL to get basic image info
        image = Image.open(image_data)
        metadata['dimensions'] = f"{image.width} x {image.height}"
        metadata['format'] = image.format

        # Reset for EXIF reading
        image_data.seek(0)

        # Extract EXIF data
        tags = exifread.process_file(image_data, details=False)

        # Extract date/time information from EXIF
        date_extracted = _extract_exif_datetime(tags, metadata)

        # Extract camera information
        if 'Image Make' in tags:
            metadata['camera_make'] = str(tags['Image Make']).strip()
        if 'Image Model' in tags:
            metadata['camera_model'] = str(tags['Image Model']).strip()

        # If no EXIF date found, try to use file creation time from Google Drive
        if not date_extracted and file_created_time:
            _extract_file_datetime(file_created_time, metadata)

    except Exception as e:
        logger.warning(f"Metadata extraction failed, returning partial data: {e}")

    return metadata


def _format_date_for_display(dt: datetime) -> str:
    """Format a datetime as D.M.YYYY (European day-first style)."""
    return f"{dt.day}.{dt.month}.{dt.year}"


def _extract_exif_datetime(tags: Dict, metadata: Dict[str, Any]) -> bool:
    """
    Extract date/time from EXIF tags, trying standard tag names in priority order.

    EXIF stores dates in "YYYY:MM:DD HH:MM:SS" format (colon-separated date).

    Returns:
        True if date was extracted, False otherwise
    """
    exif_date_tags = [
        'EXIF DateTimeOriginal',  # When the photo was taken
        'EXIF DateTime',          # General EXIF datetime
        'Image DateTime',         # TIFF/IFD datetime
    ]

    for tag_name in exif_date_tags:
        if tag_name in tags:
            date_str = str(tags[tag_name])
            try:
                dt = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                metadata['creation_date'] = _format_date_for_display(dt)
                metadata['creation_time'] = dt.strftime("%H:%M:%S")
                return True
            except ValueError:
                continue

    return False


def _extract_file_datetime(file_created_time: str, metadata: Dict[str, Any]) -> bool:
    """
    Extract date/time from Google Drive file creation time.

    Args:
        file_created_time: RFC 3339 format timestamp (e.g., "2023-12-25T14:30:45.000Z")
        metadata: Dictionary to populate with date/time

    Returns:
        True if date was extracted, False otherwise
    """
    try:
        if 'T' in file_created_time:
            # Remove timezone info and microseconds if present
            date_str = file_created_time.split('.')[0].split('Z')[0].split('+')[0]
            dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
            metadata['creation_date'] = _format_date_for_display(dt)
            metadata['creation_time'] = dt.strftime("%H:%M:%S")
            return True
    except (ValueError, AttributeError):
        pass

    return False


def format_metadata_for_display(metadata: Dict[str, Any]) -> Dict[str, str]:
    """
    Format metadata for display in templates.

    Args:
        metadata: Raw metadata dictionary

    Returns:
        Dictionary with formatted display values
    """
    display_info = {}

    # Date and time
    if metadata.get('creation_date'):
        display_info['creation_date'] = metadata['creation_date']
        display_info['creation_time'] = metadata.get('creation_time', 'Unknown')
    else:
        display_info['creation_date'] = "Unknown"
        display_info['creation_time'] = "Unknown"

    # Camera info
    camera_make = metadata.get('camera_make')
    camera_model = metadata.get('camera_model')

    if camera_make and camera_model:
        display_info['camera_info'] = f"{camera_make} {camera_model}"
    elif camera_make:
        display_info['camera_info'] = camera_make
    elif camera_model:
        display_info['camera_info'] = camera_model
    else:
        display_info['camera_info'] = "Unknown camera"

    # File info
    if metadata.get('dimensions'):
        display_info['dimensions'] = metadata['dimensions']
    if metadata.get('format'):
        display_info['format'] = metadata['format']

    return display_info
