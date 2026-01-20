"""Multimodal SDK Example

This example demonstrates how to use the Rhesis SDK with multimodal content
including images, audio, video, and files.
"""

import os
from pathlib import Path

# Load environment variables from .env file in examples directory
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed. Make sure environment variables are set manually.")

from rhesis.sdk.models import (
    ImageContent,
    Message,
    TextContent,
    get_model,
)


def main():
    # Get a vision-capable model
    print("🤖 Getting Gemini model...")
    model = get_model("gemini", "gemini-2.0-flash")

    # Check model capabilities
    print(f"\n✅ Model: {model.model_name}")
    print(f"   Vision support: {model.supports_vision}")
    print(f"   Audio support: {model.supports_audio}")
    print(f"   Video support: {model.supports_video}")
    print(f"   PDF support: {model.supports_pdf}")

    # Example 1: Simple image analysis (convenience method)
    print("\n" + "=" * 60)
    print("Example 1: Analyze a single image from URL")
    print("=" * 60)

    if model.supports_vision:
        response = model.analyze_content(
            ImageContent.from_url(
                "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"
            ),
            "Describe what you see in this image.",
        )
        print(f"Response: {response[:200]}...")

    # Example 2: Multiple images comparison
    print("\n" + "=" * 60)
    print("Example 2: Compare multiple images")
    print("=" * 60)

    messages = [
        Message(role="system", content="You are a helpful image analyst."),
        Message(
            role="user",
            content=[
                TextContent("Compare these two images:"),
                ImageContent.from_url(
                    "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"
                ),
                ImageContent.from_url(
                    "https://storage.googleapis.com/generativeai-downloads/images/croissant.jpg"
                ),
                TextContent("What are the differences and similarities?"),
            ],
        ),
    ]

    if model.supports_vision:
        response = model.generate_multimodal(messages)
        print(f"Response: {response[:300]}...")

    # Example 3: With structured output (schema)
    print("\n" + "=" * 60)
    print("Example 3: Structured image analysis")
    print("=" * 60)

    from pydantic import BaseModel

    class ImageAnalysis(BaseModel):
        """Schema for structured image analysis."""

        main_subjects: list[str]
        colors: list[str]
        setting: str
        mood: str

    if model.supports_vision:
        messages = [
            Message(
                role="user",
                content=[
                    ImageContent.from_url(
                        "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"
                    ),
                    TextContent("Analyze this image and provide structured output."),
                ],
            )
        ]

        response = model.generate_multimodal(messages, schema=ImageAnalysis)
        print(f"Structured response: {response}")

    # Example 4: Local file (if you have one)
    print("\n" + "=" * 60)
    print("Example 4: Analyze a local image file")
    print("=" * 60)

    # This would work with a local file:
    # if model.supports_vision:
    #     response = model.analyze_content(
    #         ImageContent.from_file("path/to/your/image.jpg"),
    #         "What's in this image?"
    #     )
    #     print(f"Response: {response}")

    print("(Skipped - requires local file)")

    # Example 5: Audio analysis (if model supports it)
    print("\n" + "=" * 60)
    print("Example 5: Audio analysis")
    print("=" * 60)

    if model.supports_audio:
        print("Model supports audio! You could use:")
        print("""
        messages = [
            Message(role="user", content=[
                AudioContent.from_url("https://example.com/audio.mp3"),
                TextContent("Transcribe and summarize this audio.")
            ])
        ]
        response = model.generate_multimodal(messages)
        """)
    else:
        print(f"Model {model.model_name} doesn't support audio input.")

    # Example 6: Video analysis
    print("\n" + "=" * 60)
    print("Example 6: Video analysis")
    print("=" * 60)

    if model.supports_video:
        print("Model supports video! You could use:")
        print("""
        messages = [
            Message(role="user", content=[
                VideoContent.from_url("https://example.com/video.mp4"),
                TextContent("What happens in this video?")
            ])
        ]
        response = model.generate_multimodal(messages)
        """)
    else:
        print(f"Model {model.model_name} doesn't support video input.")

    # Example 7: PDF/Document analysis
    print("\n" + "=" * 60)
    print("Example 7: PDF/Document analysis")
    print("=" * 60)

    if model.supports_pdf:
        print("Model supports PDFs! You could use:")
        print("""
        messages = [
            Message(role="user", content=[
                FileContent.from_file("document.pdf"),
                TextContent("Summarize this document.")
            ])
        ]
        response = model.generate_multimodal(messages)
        """)
    else:
        print(f"Model {model.model_name} doesn't support PDF input.")

    # Example 8: Error handling
    print("\n" + "=" * 60)
    print("Example 8: Error handling for unsupported models")
    print("=" * 60)

    try:
        # Try to use a text-only model with images
        text_model = get_model("openai", "gpt-3.5-turbo")

        if not text_model.supports_vision:
            print(f"⚠️  {text_model.model_name} doesn't support vision")

            # This would raise an error:
            # text_model.analyze_content(
            #     ImageContent.from_url("https://example.com/image.jpg"),
            #     "Describe this"
            # )
            print("(Skipped - would raise ValueError)")
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)
    print("✅ Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    # Make sure you have your API keys set
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Please set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")
        print("   export GEMINI_API_KEY='your-api-key-here'")
        exit(1)

    main()
