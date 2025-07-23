#!/usr/bin/env python3
"""
Test script to verify Google Drive connection and image loading
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_drive_connection():
    """Test Google Drive connection and list images"""
    try:
        print("Testing Google Drive connection...")
        
        # Import drive_pictures module
        import drive_pictures
        
        # Test service creation
        print("Creating Google Drive service...")
        service = drive_pictures.get_service()
        print("✅ Service created successfully")
        
        # Test listing images
        folder_id = '1USBfMHxXEZiL1XS562A6WlApGBobVp3q'
        print(f"Listing images from folder: {folder_id}")
        
        files = drive_pictures.list_images_in_folder(folder_id)
        
        if not files:
            print("❌ No images found in folder")
            return False
        
        print(f"✅ Found {len(files)} images in folder")
        
        # Show first few images
        for i, file_info in enumerate(files[:5]):
            print(f"  {i+1}. {file_info['name']} ({file_info['type']})")
        
        # Test downloading one image
        if files:
            test_file = files[0]
            print(f"\nTesting download of: {test_file['name']}")
            
            file_data = drive_pictures.download_file(test_file['id'])
            
            if file_data:
                print(f"✅ Successfully downloaded {test_file['name']}")
                print(f"   File size: {file_data.getbuffer().nbytes} bytes")
                return True
            else:
                print(f"❌ Failed to download {test_file['name']}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Drive connection: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_image_metadata():
    """Test image metadata extraction"""
    try:
        print("\nTesting image metadata extraction...")
        
        import drive_pictures
        import image_metadata
        from PIL import Image
        import io
        
        # Create a test image
        test_image = Image.new('RGB', (800, 600), color='red')
        image_data = io.BytesIO()
        test_image.save(image_data, format='JPEG')
        image_data.seek(0)
        
        # Test metadata extraction
        metadata = image_metadata.extract_image_metadata(image_data)
        print(f"✅ Metadata extraction successful")
        print(f"   Dimensions: {metadata.get('dimensions', 'Unknown')}")
        print(f"   Format: {metadata.get('format', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing metadata extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("PiFrame Google Drive Connection Test")
    print("=" * 40)
    
    # Test Drive connection
    drive_ok = test_drive_connection()
    
    # Test metadata extraction
    metadata_ok = test_image_metadata()
    
    print("\n" + "=" * 40)
    if drive_ok and metadata_ok:
        print("✅ All tests passed! Google Drive connection is working.")
        return 0
    else:
        print("❌ Some tests failed. Check the error messages above.")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 