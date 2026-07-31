"""
Pytest configuration for backend tests.
Adds the backend directory to sys.path so all imports resolve correctly.
"""
import os
import sys

# Ensure backend/ is on the path for all test modules
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
BACKEND_DIR = os.path.abspath(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
