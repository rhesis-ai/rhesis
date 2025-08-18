"""
🧪 Route-Specific Test Configuration

This conftest.py file provides fixtures specific to route testing.
It automatically discovers and provides fixtures to all test files in the routes/ directory.

The fixtures are now organized in modular packages:
- fixtures/entities.py: Individual business entity fixtures
- fixtures/relationships.py: Complex entity relationship fixtures  
- fixtures/utilities.py: Common test utilities
- fixtures/mocks.py: External service and dependency mocks
"""

# Import all fixtures from the fixtures package to make them available
# to all test files in the routes/ directory
from .fixtures import *

# This makes all fixtures from the fixtures package automatically available
# to any test file in the routes/ directory without explicit imports
