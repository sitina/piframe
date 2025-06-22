#!/usr/bin/env python3
"""
Test script for image metadata extraction
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from image_metadata import extract_image_metadata, format_metadata_for_display
import io

def test_metadata_extraction():
    """Test metadata extraction with a sample image"""
    print("Testing metadata extraction...")
    
    # Test with a sample image URL (you can replace this with a local test image)
    try:
        import requests
        
        # Download a sample image for testing
        print("Downloading sample image for testing...")
        response = requests.get("https://picsum.photos/800/600", timeout=10)
        if response.status_code == 200:
            image_data = io.BytesIO(response.content)
            
            # Extract metadata
            metadata = extract_image_metadata(image_data)
            display_info = format_metadata_for_display(metadata)
            
            print("\nExtracted Metadata:")
            print(f"Creation Date: {display_info.get('creation_date', 'Unknown')}")
            print(f"Creation Time: {display_info.get('creation_time', 'Unknown')}")
            print(f"Camera Info: {display_info.get('camera_info', 'Unknown')}")
            print(f"Dimensions: {display_info.get('dimensions', 'Unknown')}")
            print(f"Format: {display_info.get('format', 'Unknown')}")
            
            print("\nRaw Metadata:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")
                
        else:
            print("Failed to download test image")
            
    except Exception as e:
        print(f"Error during testing: {e}")
        print("You can test with a local image file instead")

if __name__ == "__main__":
    test_metadata_extraction() 