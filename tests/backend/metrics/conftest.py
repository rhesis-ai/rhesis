"""
🧪 Metrics Test Configuration

This conftest.py makes all metrics fixtures available to test modules.
"""

# Import all fixtures from the local fixtures package (relative import)
from .fixtures import *

# Explicit imports to ensure availability

# This makes all fixtures automatically available to any test file
# in the metrics/ directory without explicit imports
