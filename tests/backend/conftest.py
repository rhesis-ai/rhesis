import os
import pytest
from dotenv import load_dotenv

# Load environment variables from test directory first, then backend
load_dotenv()  # Try current directory first
load_dotenv("tests/.env")  # Load from test directory where RHESIS_API_KEY should be
load_dotenv("apps/backend/.env")  # Then backend directory for other vars

# Set test mode environment variable BEFORE importing any backend modules
os.environ["SQLALCHEMY_DB_MODE"] = "test"

# Import all modular fixtures
from tests.backend.fixtures import *

# Import all entity fixtures to make them available to tests
from tests.backend.routes.fixtures.entities import *



# Simple fixtures for testing markers functionality

@pytest.fixture
def sample_prompt():
    """🧠 Sample AI prompt for testing"""
    return "Generate tests for a financial chatbot that helps with loans"

@pytest.fixture
def mock_test_data():
    """📝 Mock test data structure"""
    return {
        "test_cases": [
            {"input": "What's my balance?", "expected": "account_inquiry"},
            {"input": "How do I apply for a loan?", "expected": "loan_application"}
        ]
    }

# All modular fixtures are now imported from tests.backend.fixtures
