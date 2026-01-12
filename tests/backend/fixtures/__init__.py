"""
🧪 Backend Test Fixtures Package

This package contains modular test fixtures organized by functionality:

- `auth.py`: Authentication-related fixtures (users, organizations, API keys)
- `client.py`: FastAPI test client fixtures
- `cleanup.py`: Database cleanup logic for test isolation
- `database.py`: Database setup, configuration, and session management

All fixtures are imported and available through the main conftest.py file.
"""

# Import all fixtures to make them available when importing from this package
from .auth import *
from .cleanup import *
from .client import *
from .database import *
