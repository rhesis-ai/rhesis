"""Quick Start: Multimodal Image Analysis

A simple example to get started with image analysis using the Rhesis SDK.
"""

from pathlib import Path

# Load environment variables from .env file in examples directory
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed. Make sure environment variables are set manually.")

from rhesis.sdk.models import ImageContent, get_model

# Get a vision-capable model (make sure GEMINI_API_KEY is set)
model = get_model("gemini", "gemini-2.0-flash")

# Quick image analysis - just provide URL and prompt
response = model.analyze_content(
    ImageContent.from_url(
        "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"
    ),
    "Describe this image in detail.",
)

print(response)
