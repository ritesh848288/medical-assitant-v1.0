#!/usr/bin/env python3
"""
Run script for DoctorAI website
"""
import os
import sys
import subprocess
import webbrowser
import time

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import flask
        import torch
        import transformers
        print("✅ All dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False

def install_dependencies():
    """Install required packages"""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt"])

def setup_database():
    """Initialize database"""
    from backend.app import app
    from backend.database import db

    with app.app_context():
        db.create_all()
        print("✅ Database initialized")

def main():
    """Main entry point"""
    print("=" * 50)
    print("🚀 Starting DoctorAI Website")
    print("=" * 50)
    
    # Check if running for the first time
    if not os.path.exists('instance'):
        os.makedirs('instance')
    
    # Check dependencies
    if not check_dependencies():
        print("\nInstalling dependencies...")
        install_dependencies()
    
    # Setup database
    setup_database()
    
    # Start the Flask app
   

if __name__ == '__main__':
     
     print("\n🌐 Starting web server...")
    # Run the app
     from backend.app import app
     app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
     print("⌛ Loading Mistral model (this may take a few minutes on first run)...")
     print("=" * 50)
     print("📱 Open http://localhost:5000 in your browser")
    # Open browser after a short delay
     time.sleep(2)
     webbrowser.open('http://localhost:5000')
    
   
     try:
        main()
     except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        sys.exit(0)
     except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)