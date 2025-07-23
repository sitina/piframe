#!/usr/bin/env python3
"""
Simple setup script for PiFrame
"""
import json
import os
import sys

def main():
    print("=== PiFrame Setup ===")
    print()
    
    # Check if client_secret.json exists
    if not os.path.exists("client_secret.json"):
        print("❌ client_secret.json not found!")
        print("Please download your Google Drive API credentials from:")
        print("https://console.developers.google.com/apis/credentials")
        print("and save them as 'client_secret.json' in this directory")
        sys.exit(1)
    
    # Load current config
    config = {}
    if os.path.exists("config/config.json"):
        try:
            with open("config/config.json", "r") as f:
                config = json.load(f)
        except json.JSONDecodeError:
            print("⚠️  Warning: Invalid config/config.json, creating new one")
            config = {}
    
    print("Current configuration:")
    print(f"  Album ID: {config.get('album', 'NOT SET')}")
    print(f"  Weather API Key: {'SET' if config.get('weather_api_key') else 'NOT SET'}")
    print(f"  Weather Location: {config.get('weather_location', 'NOT SET')}")
    print(f"  Background Refresh Interval: {config.get('background_refresh_interval', 300)} seconds")
    print(f"  Preload Interval: {config.get('preload_interval', 900)} seconds")
    print(f"  Error Retry Interval: {config.get('error_retry_interval', 60)} seconds")
    print(f"  Preload Error Retry Interval: {config.get('preload_error_retry_interval', 300)} seconds")
    print(f"  Frontend Refresh Interval: {config.get('frontend_refresh_interval', 30)} seconds")
    print()
    
    # Get album ID
    print("To find your Google Drive folder ID:")
    print("1. Open Google Drive in your browser")
    print("2. Navigate to the folder containing your photos")
    print("3. Copy the URL from the address bar")
    print("4. The folder ID is the long string after '/folders/' in the URL")
    print("   Example: https://drive.google.com/drive/folders/1ABC123DEF456GHI789JKL")
    print("   The folder ID would be: 1ABC123DEF456GHI789JKL")
    print()
    
    album_id = input("Enter your Google Drive folder ID (or press Enter to skip): ").strip()
    
    if album_id:
        # Extract folder ID from URL if user pasted full URL
        if '/folders/' in album_id:
            album_id = album_id.split('/folders/')[1].split('/')[0]
            print(f"Extracted folder ID: {album_id}")
        
        config['album'] = album_id
    
    # Get weather API key
    weather_key = input("Enter your OpenWeatherMap API key (or press Enter to skip): ").strip()
    if weather_key:
        config['weather_api_key'] = weather_key
    
    # Get weather location
    weather_location = input("Enter your location (e.g., 'Prague, CZ') (or press Enter to skip): ").strip()
    if weather_location:
        config['weather_location'] = weather_location
    
    # Get refresh intervals
    print("\nRefresh Interval Configuration:")
    print("These control how often the application refreshes data and retries on errors.")
    
    background_interval = input(f"Background refresh interval in seconds (default: 300): ").strip()
    if background_interval and background_interval.isdigit():
        config['background_refresh_interval'] = int(background_interval)
    
    preload_interval = input(f"Preload interval in seconds (default: 900): ").strip()
    if preload_interval and preload_interval.isdigit():
        config['preload_interval'] = int(preload_interval)
    
    error_retry_interval = input(f"Error retry interval in seconds (default: 60): ").strip()
    if error_retry_interval and error_retry_interval.isdigit():
        config['error_retry_interval'] = int(error_retry_interval)
    
    preload_error_interval = input(f"Preload error retry interval in seconds (default: 300): ").strip()
    if preload_error_interval and preload_error_interval.isdigit():
        config['preload_error_retry_interval'] = int(preload_error_interval)
    
    frontend_interval = input(f"Frontend refresh interval in seconds (default: 30): ").strip()
    if frontend_interval and frontend_interval.isdigit():
        config['frontend_refresh_interval'] = int(frontend_interval)
    
    # Save config
    os.makedirs("config", exist_ok=True)
    with open("config/config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print()
    print("✅ Configuration saved!")
    print()
    
    # Test album access if album ID was provided
    if config.get('album'):
        print("Testing Google Drive connection...")
        try:
            import legacy.drive_pictures as drive_pictures
            files = drive_pictures.list_images_in_folder(config['album'])
            print(f"✅ Successfully connected! Found {len(files)} images.")
        except Exception as e:
            print(f"❌ Error connecting to Google Drive: {e}")
            print("Please check your folder ID and try again.")
    
    print()
    print("You can now run the application with:")
    print("  ./start-install.sh")
    print()
    print("Or manually with:")
    print("  python app.py")

if __name__ == "__main__":
    main() 