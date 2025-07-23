#!/usr/bin/env python3
"""
Test script to verify metadata and image synchronization
"""
import requests
import json
import time

def test_synchronization():
    """Test that metadata and image are synchronized"""
    base_url = "http://localhost:5001"
    
    print("Testing metadata and image synchronization...")
    
    # Get metadata
    print("1. Fetching metadata...")
    metadata_response = requests.get(f"{base_url}/random-picture/metadata")
    
    if metadata_response.status_code != 200:
        print(f"Error getting metadata: {metadata_response.status_code}")
        return False
    
    metadata = metadata_response.json()
    print(f"Metadata received: {json.dumps(metadata, indent=2)}")
    
    # Get the synchronized image
    print("2. Fetching synchronized image...")
    image_url = metadata['picture_url']
    image_response = requests.get(f"{base_url}{image_url}")
    
    if image_response.status_code != 200:
        print(f"Error getting image: {image_response.status_code}")
        return False
    
    print(f"Image received: {len(image_response.content)} bytes")
    
    # Check if image ID is in headers
    image_id = image_response.headers.get('X-Image-ID')
    if image_id:
        print(f"Image ID from headers: {image_id}")
    else:
        print("Warning: No image ID in headers")
    
    # Check metadata headers
    metadata_headers = {
        'X-Image-Date': image_response.headers.get('X-Image-Date'),
        'X-Image-Time': image_response.headers.get('X-Image-Time'),
        'X-Camera-Info': image_response.headers.get('X-Camera-Info'),
        'X-Image-Dimensions': image_response.headers.get('X-Image-Dimensions')
    }
    
    print(f"Image metadata headers: {json.dumps(metadata_headers, indent=2)}")
    
    # Verify synchronization
    print("3. Verifying synchronization...")
    
    # The metadata from the JSON should match the headers from the image
    metadata_matches = (
        metadata['creation_date'] == metadata_headers['X-Image-Date'] and
        metadata['creation_time'] == metadata_headers['X-Image-Time'] and
        metadata['camera_info'] == metadata_headers['X-Camera-Info'] and
        metadata['dimensions'] == metadata_headers['X-Image-Dimensions']
    )
    
    if metadata_matches:
        print("✅ SUCCESS: Metadata and image are synchronized!")
        return True
    else:
        print("❌ FAILURE: Metadata and image are NOT synchronized!")
        print("Metadata from JSON:", metadata)
        print("Metadata from headers:", metadata_headers)
        return False

if __name__ == "__main__":
    try:
        success = test_synchronization()
        exit(0 if success else 1)
    except Exception as e:
        print(f"Test failed with exception: {e}")
        exit(1) 