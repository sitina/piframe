"""
Tests for image metadata extraction
"""
import unittest
import io
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from legacy.image_metadata import extract_image_metadata, format_metadata_for_display
from PIL import Image


class TestImageMetadata(unittest.TestCase):
    """Test cases for image metadata extraction"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a simple test image
        self.test_image = Image.new('RGB', (800, 600), color='red')
        self.test_image_data = io.BytesIO()
        self.test_image.save(self.test_image_data, format='JPEG')
        self.test_image_data.seek(0)

    def test_extract_basic_metadata(self):
        """Test basic metadata extraction without EXIF data"""
        metadata = extract_image_metadata(self.test_image_data)
        
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata['dimensions'], '800 x 600')
        self.assertEqual(metadata['format'], 'JPEG')
        self.assertIsNotNone(metadata['file_size'])
        self.assertIsNone(metadata['creation_date'])
        self.assertIsNone(metadata['camera_make'])

    def test_format_metadata_for_display(self):
        """Test metadata formatting for display"""
        metadata = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45',
            'camera_make': 'Canon',
            'camera_model': 'EOS R5',
            'dimensions': '4000 x 3000',
            'format': 'JPEG'
        }
        
        display_info = format_metadata_for_display(metadata)
        
        self.assertEqual(display_info['creation_date'], '25.12.2023')
        self.assertEqual(display_info['creation_time'], '14:30:45')
        self.assertEqual(display_info['camera_info'], 'Canon EOS R5')
        self.assertEqual(display_info['dimensions'], '4000 x 3000')

    def test_format_metadata_with_missing_data(self):
        """Test metadata formatting with missing data"""
        metadata = {
            'creation_date': None,
            'creation_time': None,
            'camera_make': None,
            'camera_model': None,
            'dimensions': None,
            'format': None
        }
        
        display_info = format_metadata_for_display(metadata)
        
        self.assertEqual(display_info['creation_date'], 'Unknown')
        self.assertEqual(display_info['creation_time'], 'Unknown')
        self.assertEqual(display_info['camera_info'], 'Unknown camera')
        self.assertNotIn('dimensions', display_info)

    def test_format_metadata_partial_camera_info(self):
        """Test metadata formatting with partial camera info"""
        metadata = {
            'creation_date': '25.12.2023',
            'creation_time': '14:30:45',
            'camera_make': 'Canon',
            'camera_model': None,
            'dimensions': '4000 x 3000',
            'format': 'JPEG'
        }
        
        display_info = format_metadata_for_display(metadata)
        
        self.assertEqual(display_info['camera_info'], 'Canon')

    @patch('legacy.image_metadata.exifread.process_file')
    def test_extract_metadata_with_exif(self, mock_exifread):
        """Test metadata extraction with EXIF data"""
        # Mock EXIF data
        mock_tags = {
            'EXIF DateTimeOriginal': '2023:12:25 14:30:45',
            'Image Make': 'Canon',
            'Image Model': 'EOS R5'
        }
        mock_exifread.return_value = mock_tags
        
        metadata = extract_image_metadata(self.test_image_data)
        
        self.assertEqual(metadata['creation_date'], '25.12.2023')
        self.assertEqual(metadata['creation_time'], '14:30:45')
        self.assertEqual(metadata['camera_make'], 'Canon')
        self.assertEqual(metadata['camera_model'], 'EOS R5')

    @patch('legacy.image_metadata.exifread.process_file')
    def test_extract_metadata_fallback_date(self, mock_exifread):
        """Test metadata extraction with fallback date fields"""
        # Mock EXIF data with fallback date
        mock_tags = {
            'EXIF DateTime': '2023:12:25 14:30:45',
            'Image Make': 'Nikon'
        }
        mock_exifread.return_value = mock_tags
        
        metadata = extract_image_metadata(self.test_image_data)
        
        self.assertEqual(metadata['creation_date'], '25.12.2023')
        self.assertEqual(metadata['creation_time'], '14:30:45')
        self.assertEqual(metadata['camera_make'], 'Nikon')

    def test_extract_metadata_invalid_date_format(self):
        """Test metadata extraction with invalid date format"""
        with patch('legacy.image_metadata.exifread.process_file') as mock_exifread:
            mock_tags = {
                'EXIF DateTimeOriginal': 'invalid-date-format',
                'Image Make': 'Canon'
            }
            mock_exifread.return_value = mock_tags
            
            metadata = extract_image_metadata(self.test_image_data)
            
            self.assertIsNone(metadata['creation_date'])
            self.assertIsNone(metadata['creation_time'])
            self.assertEqual(metadata['camera_make'], 'Canon')

    def test_extract_metadata_exception_handling(self):
        """Test metadata extraction with exception handling"""
        with patch('legacy.image_metadata.exifread.process_file') as mock_exifread:
            mock_exifread.side_effect = Exception("EXIF read error")
            
            metadata = extract_image_metadata(self.test_image_data)
            
            # Should still get basic metadata
            self.assertEqual(metadata['dimensions'], '800 x 600')
            self.assertEqual(metadata['format'], 'JPEG')

    def test_extract_metadata_empty_bytesio(self):
        """Test metadata extraction with empty BytesIO"""
        empty_data = io.BytesIO()
        
        # Should handle empty BytesIO gracefully
        metadata = extract_image_metadata(empty_data)
        
        # Should return basic structure even for empty data
        self.assertIsInstance(metadata, dict)
        self.assertIn('dimensions', metadata)
        self.assertIn('format', metadata)

    @patch('legacy.image_metadata.exifread.process_file')
    def test_extract_metadata_fallback_to_file_created_time(self, mock_exifread):
        """Test metadata extraction falls back to file created time when EXIF is not available"""
        # Mock EXIF data without date/time
        mock_tags = {
            'Image Make': 'Canon'
        }
        mock_exifread.return_value = mock_tags
        
        # Test with RFC 3339 format with microseconds and Z
        file_created_time = '2023-12-25T14:30:45.123Z'
        metadata = extract_image_metadata(self.test_image_data, file_created_time=file_created_time)
        
        self.assertEqual(metadata['creation_date'], '25.12.2023')
        self.assertEqual(metadata['creation_time'], '14:30:45')
        self.assertEqual(metadata['camera_make'], 'Canon')

    @patch('legacy.image_metadata.exifread.process_file')
    def test_extract_metadata_fallback_to_file_created_time_no_microseconds(self, mock_exifread):
        """Test metadata extraction with file created time without microseconds"""
        # Mock EXIF data without date/time
        mock_tags = {}
        mock_exifread.return_value = mock_tags
        
        # Test with RFC 3339 format without microseconds
        file_created_time = '2023-12-25T14:30:45Z'
        metadata = extract_image_metadata(self.test_image_data, file_created_time=file_created_time)
        
        self.assertEqual(metadata['creation_date'], '25.12.2023')
        self.assertEqual(metadata['creation_time'], '14:30:45')

    @patch('legacy.image_metadata.exifread.process_file')
    def test_extract_metadata_exif_takes_precedence(self, mock_exifread):
        """Test that EXIF date takes precedence over file created time"""
        # Mock EXIF data with date
        mock_tags = {
            'EXIF DateTimeOriginal': '2023:12:25 14:30:45',
            'Image Make': 'Canon'
        }
        mock_exifread.return_value = mock_tags
        
        # Provide file created time (should be ignored)
        file_created_time = '2020-01-01T10:00:00Z'
        metadata = extract_image_metadata(self.test_image_data, file_created_time=file_created_time)
        
        # Should use EXIF date, not file created time
        self.assertEqual(metadata['creation_date'], '25.12.2023')
        self.assertEqual(metadata['creation_time'], '14:30:45')

    @patch('legacy.image_metadata.exifread.process_file')
    def test_extract_metadata_fallback_invalid_file_time(self, mock_exifread):
        """Test metadata extraction with invalid file created time format"""
        # Mock EXIF data without date/time
        mock_tags = {}
        mock_exifread.return_value = mock_tags
        
        # Test with invalid format
        file_created_time = 'invalid-date-format'
        metadata = extract_image_metadata(self.test_image_data, file_created_time=file_created_time)
        
        # Should not crash and should not set date
        self.assertIsNone(metadata['creation_date'])
        self.assertIsNone(metadata['creation_time'])

    @patch('legacy.image_metadata.exifread.process_file')
    def test_extract_metadata_fallback_with_timezone_offset(self, mock_exifread):
        """Test metadata extraction with file created time including timezone offset"""
        # Mock EXIF data without date/time
        mock_tags = {}
        mock_exifread.return_value = mock_tags
        
        # Test with RFC 3339 format with timezone offset
        file_created_time = '2023-12-25T14:30:45+02:00'
        metadata = extract_image_metadata(self.test_image_data, file_created_time=file_created_time)
        
        self.assertEqual(metadata['creation_date'], '25.12.2023')
        self.assertEqual(metadata['creation_time'], '14:30:45')


if __name__ == '__main__':
    unittest.main() 