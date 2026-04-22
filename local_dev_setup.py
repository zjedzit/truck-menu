#!/usr/bin/env python3
"""
Local development setup for Elvis application
This script helps set up a local development environment
"""

import os
import subprocess
import sys
from pathlib import Path

def check_python_packages():
    """Check if required packages are installed"""
    required_packages = ['fastapi', 'uvicorn', 'pymongo']
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is installed")
        except ImportError:
            print(f"✗ {package} is not installed")
            return False
    return True

def setup_environment():
    """Setup local environment variables"""
    env_file = ".env.local"
    if not os.path.exists(env_file):
        print("Creating .env.local file...")
        with open(env_file, 'w') as f:
            f.write("""# Local development environment
MONGO_URI=mongodb://localhost:27017
OVH_AI_ENDPOINTS_ACCESS_TOKEN=
AI_MODEL_NAME=gpt-oss-120b
""")
        print("Created .env.local file")
    else:
        print(".env.local file already exists")

def check_mongodb():
    """Check if MongoDB is available"""
    try:
        # Try to connect to MongoDB
        from pymongo import MongoClient
        client = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
        client.server_info()
        print("✓ MongoDB is available")
        return True
    except Exception as e:
        print(f"✗ MongoDB not available: {e}")
        return False

def run_application():
    """Run the FastAPI application"""
    print("Starting the application...")
    try:
        # Run with uvicorn
        subprocess.run([
            sys.executable, '-m', 'uvicorn', 
            'main:app', 
            '--host', '0.0.0.0', 
            '--port', '8080',
            '--reload'
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to start application: {e}")

def main():
    print("=== Elvis Application Local Development Setup ===")
    
    # Check if we have required packages
    if not check_python_packages():
        print("Please install required packages first:")
        print("pip install fastapi uvicorn pymongo")
        return
    
    # Setup environment
    setup_environment()
    
    # Check MongoDB
    mongodb_available = check_mongodb()
    
    print("\n=== Setup Complete ===")
    print("To run the application:")
    print("1. Make sure MongoDB is running (if you want database functionality)")
    print("2. Run: python local_dev_setup.py run")
    print("\nApplication will be available at http://localhost:8080")
    
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        run_application()

if __name__ == "__main__":
    main()