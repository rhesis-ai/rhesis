import os
import pytest
# Commenting out FastAPI imports for now to test markers independently
# from fastapi.testclient import TestClient
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from rhesis.backend.app.main import app
# from rhesis.backend.app.database import Base, get_db

from dotenv import load_dotenv

load_dotenv()

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

@pytest.fixture
def rhesis_api_key():
    """🔑 Mock API key for testing"""
    return "rh-test1234567890abcdef"

# Uncomment when dependencies are available:
# SQLALCHEMY_DATABASE_TEST_URL = os.getenv("SQLALCHEMY_DATABASE_TEST_URL", "sqlite:///./test.db")
# engine = create_engine(SQLALCHEMY_DATABASE_TEST_URL)
# TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# 
# Base.metadata.create_all(bind=engine)
# 
# def override_get_db():
#     try:
#         db = TestingSessionLocal()
#         yield db
#     finally:
#         db.close()
# 
# app.dependency_overrides[get_db] = override_get_db
# 
# @pytest.fixture(scope="module")
# def client():
#     with TestClient(app) as c:
#         yield c
