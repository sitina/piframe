"""
Simple fallback Flask application for PiFrame.
This is a minimal version that works if the refactored modules aren't available.
"""

try:
    # Try to use the new refactored app
    from app import create_app
    app = create_app(start_background_tasks=True)
    
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5001, debug=False)
        
except ImportError:
    print("Refactored modules not available, using original app...")
    try:
        # Fall back to original app
        import app_original
        if hasattr(app_original, 'app'):
            app = app_original.app
            if __name__ == '__main__':
                app.run(host='0.0.0.0', port=5001, debug=False)
        else:
            print("Original app also not available")
    except ImportError:
        print("Neither refactored nor original app available")
        raise