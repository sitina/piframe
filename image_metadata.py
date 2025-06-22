"""
Image metadata extraction module for PiFrame
"""
import exifread
import io
from datetime import datetime
from PIL import Image
import os

def extract_image_metadata(image_data):
    """
    Extract metadata from image data (BytesIO object)
    Returns a dictionary with metadata information
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
        
        # Extract date/time information
        if 'EXIF DateTimeOriginal' in tags:
            # Format: 2023:12:25 14:30:45
            date_str = str(tags['EXIF DateTimeOriginal'])
            try:
                dt = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                metadata['creation_date'] = dt.strftime("%-d.%-m.%Y")
                metadata['creation_time'] = dt.strftime("%H:%M:%S")
            except ValueError:
                pass
        elif 'EXIF DateTime' in tags:
            date_str = str(tags['EXIF DateTime'])
            try:
                dt = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                metadata['creation_date'] = dt.strftime("%-d.%-m.%Y")
                metadata['creation_time'] = dt.strftime("%H:%M:%S")
            except ValueError:
                pass
        elif 'Image DateTime' in tags:
            date_str = str(tags['Image DateTime'])
            try:
                dt = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                metadata['creation_date'] = dt.strftime("%-d.%-m.%Y")
                metadata['creation_time'] = dt.strftime("%H:%M:%S")
            except ValueError:
                pass
        
        # Extract camera information
        if 'Image Make' in tags:
            metadata['camera_make'] = str(tags['Image Make']).strip()
        if 'Image Model' in tags:
            metadata['camera_model'] = str(tags['Image Model']).strip()
        
        # If no EXIF date found, try to use file modification time
        if not metadata['creation_date']:
            # For Google Drive files, we might not have file modification time
            # This would need to be handled differently
            pass
            
    except Exception as e:
        print(f"Error extracting metadata: {e}")
    
    return metadata

def format_metadata_for_display(metadata):
    """
    Format metadata for display in templates
    """
    display_info = {}
    
    # Date and time
    if metadata['creation_date']:
        display_info['creation_date'] = metadata['creation_date']
        display_info['creation_time'] = metadata['creation_time']
    else:
        display_info['creation_date'] = "Unknown"
        display_info['creation_time'] = "Unknown"
    
    # Camera info
    if metadata['camera_make'] and metadata['camera_model']:
        display_info['camera_info'] = f"{metadata['camera_make']} {metadata['camera_model']}"
    elif metadata['camera_make']:
        display_info['camera_info'] = metadata['camera_make']
    elif metadata['camera_model']:
        display_info['camera_info'] = metadata['camera_model']
    else:
        display_info['camera_info'] = "Unknown camera"
    
    # File info
    if metadata['dimensions']:
        display_info['dimensions'] = metadata['dimensions']
    if metadata['format']:
        display_info['format'] = metadata['format']
    
    return display_info 