"""Example 1: Image Analysis with Gemini

Demonstrates how to analyze images using vision-capable models.
"""

from pathlib import Path

# Load environment variables from parent .env file
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed. Make sure environment variables are set manually.")

from rhesis.sdk.models import ImageContent, Message, TextContent, get_model

print("=" * 60)
print("Image Analysis Examples")
print("=" * 60)

# Get a vision-capable model
model = get_model("gemini", "gemini-2.0-flash")
print(f"\n✅ Using model: {model.model_name}")
print(f"   Vision support: {model.supports_vision}")

# Example 1: Analyze local image
print("\n" + "-" * 60)
print("Example 1: Analyze a local image")
print("-" * 60)

image_path = Path(__file__).parent / "images" / "scones.jpg"
response = model.analyze_content(
    ImageContent.from_file(image_path),
    "Describe this image in detail, focusing on the food items.",
)
print(f"Response: {response[:300]}...\n")

# Example 2: Compare two images
print("-" * 60)
print("Example 2: Compare two images")
print("-" * 60)

messages = [
    Message(
        role="user",
        content=[
            TextContent("Compare these two baked goods:"),
            ImageContent.from_file(Path(__file__).parent / "images" / "scones.jpg"),
            ImageContent.from_file(Path(__file__).parent / "images" / "croissant.jpg"),
            TextContent("What are the key differences?"),
        ],
    )
]

response = model.generate_multimodal(messages)
print(f"Response: {response[:400]}...\n")

# Example 3: Structured analysis with schema
print("-" * 60)
print("Example 3: Structured image analysis")
print("-" * 60)

from pydantic import BaseModel, Field


class FoodAnalysis(BaseModel):
    """Schema for food image analysis."""

    food_name: str = Field(description="Name of the food item")
    ingredients: list[str] = Field(description="Visible or likely ingredients")
    colors: list[str] = Field(description="Dominant colors in the image")
    occasion: str = Field(description="Typical occasion for this food")


messages = [
    Message(
        role="user",
        content=[
            ImageContent.from_file(Path(__file__).parent / "images" / "scones.jpg"),
            TextContent("Analyze this food image and provide structured information."),
        ],
    )
]

result = model.generate_multimodal(messages, schema=FoodAnalysis)
print(f"Food Name: {result['food_name']}")
print(f"Ingredients: {', '.join(result['ingredients'])}")
print(f"Colors: {', '.join(result['colors'])}")
print(f"Occasion: {result['occasion']}\n")

print("=" * 60)
print("✅ Image analysis examples complete!")
print("=" * 60)
