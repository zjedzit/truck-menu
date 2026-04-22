#!/usr/bin/env python3
"""
Simple test to verify the application can start
"""

import os
import sys
from unittest.mock import patch

# Mock the database connection to avoid hanging
with patch('main.MongoClient') as mock_mongo:
    # Mock the database connection
    mock_db = mock_mongo.return_value.__getitem__.return_value
    mock_mongo.return_value.__getitem__.return_value = mock_db
    
    try:
        # Import the main application
        import main
        print("✓ Application imported successfully")
        
        # Check if the app object exists
        if hasattr(main, 'app'):
            print("✓ FastAPI app object found")
            
            # Print available routes
            print("Available routes:")
            for route in main.app.routes:
                print(f"  {route.methods} {route.path}")
                
        else:
            print("✗ FastAPI app object not found")
            
    except Exception as e:
        print(f"✗ Error importing application: {e}")
        import traceback
        traceback.print_exc()