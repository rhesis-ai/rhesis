"""
🧪 Route-Specific Test Configuration

This conftest.py file provides fixtures specific to route testing.
It automatically discovers and provides fixtures to all test files in the routes/ directory.
"""

# Import all fixtures from the fixtures module to make them available
# to all test files in the routes/ directory
from .fixtures import *

# This makes all fixtures from fixtures.py automatically available
# to any test file in the routes/ directory without explicit imports
