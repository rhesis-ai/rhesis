"""Advanced Multimodal Examples

Demonstrates advanced use cases including:
- Multi-turn conversations with images
- Structured output with schemas
- Mixed content (text + images + audio)
- Batch image processing
"""

from pathlib import Path

# Load environment variables from .env file in examples directory
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed. Make sure environment variables are set manually.")

from pydantic import BaseModel, Field

from rhesis.sdk.models import (
    ImageContent,
    Message,
    TextContent,
    get_model,
)


class ProductAnalysis(BaseModel):
    """Schema for structured product analysis from images."""

    product_name: str = Field(description="The name of the product")
    category: str = Field(description="Product category")
    key_features: list[str] = Field(description="Key visible features")
    estimated_price_range: str = Field(description="Estimated price range")
    target_audience: str = Field(description="Target customer demographic")


def multi_turn_conversation():
    """Example: Multi-turn conversation with image context."""
    print("\n📝 Multi-turn conversation with images\n")

    model = get_model("gemini", "gemini-2.0-flash")

    # Start conversation with an image
    messages = [
        Message(
            role="user",
            content=[
                ImageContent.from_url(
                    "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"
                ),
                TextContent("What's in this image?"),
            ],
        )
    ]

    response = model.generate_multimodal(messages)
    print(f"Assistant: {response}\n")

    # Continue the conversation
    messages.append(Message(role="assistant", content=response))
    messages.append(Message(role="user", content="What ingredients would I need to make these?"))

    response = model.generate_multimodal(messages)
    print(f"Assistant: {response}\n")


def structured_product_analysis():
    """Example: Extract structured data from product images."""
    print("\n🏷️  Structured product analysis\n")

    model = get_model("gemini", "gemini-2.0-flash")

    messages = [
        Message(
            role="system",
            content="You are a product analyst. Analyze images and provide structured information.",
        ),
        Message(
            role="user",
            content=[
                ImageContent.from_url(
                    "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"
                ),
                TextContent("Analyze this product image and provide structured information."),
            ],
        ),
    ]

    # Get structured response
    result = model.generate_multimodal(messages, schema=ProductAnalysis)

    print("Product Analysis:")
    print(f"  Name: {result['product_name']}")
    print(f"  Category: {result['category']}")
    print(f"  Features: {', '.join(result['key_features'])}")
    print(f"  Price Range: {result['estimated_price_range']}")
    print(f"  Target Audience: {result['target_audience']}\n")


def batch_image_comparison():
    """Example: Compare multiple images in a batch."""
    print("\n🔄 Batch image comparison\n")

    model = get_model("gemini", "gemini-2.0-flash")

    image_urls = [
        "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg",
        "https://storage.googleapis.com/generativeai-downloads/images/croissant.jpg",
    ]

    # Build content with multiple images
    content = [TextContent("Compare these baked goods:")]
    for i, url in enumerate(image_urls, 1):
        content.append(ImageContent.from_url(url))
    content.append(
        TextContent("What are the key differences in appearance, preparation, and typical serving?")
    )

    messages = [Message(role="user", content=content)]

    response = model.generate_multimodal(messages)
    print(f"Comparison: {response}\n")


def image_question_answering():
    """Example: Answer specific questions about images."""
    print("\n❓ Image question answering\n")

    model = get_model("gemini", "gemini-2.0-flash")

    questions = [
        "How many items are visible?",
        "What is the dominant color?",
        "What time of day does this appear to be?",
    ]

    for question in questions:
        response = model.analyze_content(
            ImageContent.from_url(
                "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"
            ),
            question,
        )
        print(f"Q: {question}")
        print(f"A: {response}\n")


def local_file_processing():
    """Example: Process local images (commented out - requires actual files)."""
    print("\n📁 Local file processing\n")

    print("To process local files, use:")
    print("""
    from rhesis.sdk.models import get_model, ImageContent
    
    model = get_model("gemini", "gemini-2.0-flash")
    
    # Process a single local file
    response = model.analyze_content(
        ImageContent.from_file("/path/to/your/image.jpg"),
        "Describe this image"
    )
    
    # Or create from bytes (useful for uploaded files)
    with open("/path/to/image.jpg", "rb") as f:
        image_bytes = f.read()
    
    response = model.analyze_content(
        ImageContent.from_bytes(image_bytes, mime_type="image/jpeg"),
        "What's in this image?"
    )
    """)


def main():
    """Run all advanced examples."""
    print("=" * 60)
    print("Advanced Multimodal Examples")
    print("=" * 60)

    try:
        multi_turn_conversation()
        structured_product_analysis()
        batch_image_comparison()
        image_question_answering()
        local_file_processing()

        print("=" * 60)
        print("✅ All examples completed!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
