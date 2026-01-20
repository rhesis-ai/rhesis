"""Quickstart: Multimodal Image Analysis with Gemini

A simple example to get started with image analysis using Gemini's vision capabilities.
"""

from pathlib import Path

# Load environment variables from parent .env file
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed.")

from rhesis.sdk.models import ImageContent, Message, TextContent, get_model

print("🖼️  Multimodal Quickstart with Gemini\n")

# Get Gemini vision model
vision_model = get_model("gemini", "gemini-2.0-flash")
print(f"✅ Using {vision_model.model_name}\n")

# 1. Simple image analysis
print("📸 Analyzing image...")
image_path = Path(__file__).parent / "images" / "scones.jpg"

analysis = vision_model.analyze_content(
    ImageContent.from_file(image_path), "Describe what you see in this image."
)

print(f"Analysis: {analysis[:250]}...\n")

# 2. Ask follow-up questions
print("❓ Asking follow-up question...")
messages = [
    Message(
        role="user",
        content=[
            ImageContent.from_file(image_path),
            TextContent("What ingredients are visible or implied in this image?"),
        ],
    )
]

ingredients = vision_model.generate_multimodal(messages)
print(f"Ingredients: {ingredients[:200]}...\n")

# 3. Compare two images
print("🔄 Comparing two images...")
comparison = vision_model.generate_multimodal(
    [
        Message(
            role="user",
            content=[
                TextContent("What are the main differences between these two baked goods?"),
                ImageContent.from_file(Path(__file__).parent / "images" / "scones.jpg"),
                ImageContent.from_file(Path(__file__).parent / "images" / "croissant.jpg"),
            ],
        )
    ]
)

print(f"Comparison: {comparison[:200]}...\n")

print("✅ Done! Try the other examples for more advanced use cases.")
