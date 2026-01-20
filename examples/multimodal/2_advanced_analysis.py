"""Example 2: Advanced Image Analysis with Gemini

Demonstrates advanced vision capabilities:
- Multi-turn conversations with images
- Asking follow-up questions
- Extracting detailed information
- Creative use cases
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

print("=" * 60)
print("Advanced Image Analysis Examples")
print("=" * 60)

model = get_model("gemini", "gemini-2.0-flash")
print(f"\n✅ Using model: {model.model_name}\n")

# Example 1: Multi-turn conversation with an image
print("-" * 60)
print("Example 1: Multi-turn conversation about an image")
print("-" * 60)

image_path = Path(__file__).parent / "images" / "scones.jpg"

# Start with the image
messages = [
    Message(
        role="user",
        content=[
            ImageContent.from_file(image_path),
            TextContent("What do you see in this image?"),
        ],
    )
]

response = model.generate_multimodal(messages)
print(f"Assistant: {response[:300]}...\n")

# Follow-up question (image stays in context)
messages.append(Message(role="assistant", content=response))
messages.append(Message(role="user", content="What ingredients would I need to make these?"))

response = model.generate_multimodal(messages)
print(f"Assistant: {response[:300]}...\n")

# Another follow-up
messages.append(Message(role="assistant", content=response))
messages.append(Message(role="user", content="Can you suggest a recipe?"))

response = model.generate_multimodal(messages)
print(f"Assistant: {response[:400]}...\n")

# Example 2: Detailed image description
print("-" * 60)
print("Example 2: Detailed scene description")
print("-" * 60)

prompt = """Provide a detailed description of this image including:
1. Overall composition and layout
2. Every visible object and its position
3. Colors, lighting, and mood
4. Textures and materials
5. Estimated time of day and setting
Be as thorough as possible."""

response = model.analyze_content(ImageContent.from_file(image_path), prompt)
print(f"Detailed description: {response[:500]}...\n")

# Example 3: Creative analysis
print("-" * 60)
print("Example 3: Creative storytelling from image")
print("-" * 60)

creative_prompt = """Look at this image and write a short story (2-3 paragraphs) about:
- Who might have prepared this food
- What occasion this might be for
- The story behind this moment
Be creative and descriptive!"""

story = model.analyze_content(ImageContent.from_file(image_path), creative_prompt)
print(f"Story:\n{story}\n")

# Example 4: Technical analysis
print("-" * 60)
print("Example 4: Photography technique analysis")
print("-" * 60)

photo_prompt = """Analyze this image from a photography perspective:
- Camera angle and perspective
- Lighting setup and direction
- Depth of field and focus
- Composition techniques used
- Post-processing style
Provide professional insights."""

photo_analysis = model.analyze_content(ImageContent.from_file(image_path), photo_prompt)
print(f"Photography analysis: {photo_analysis[:400]}...\n")

# Example 5: Comparison and contrast
print("-" * 60)
print("Example 5: Detailed comparison of two images")
print("-" * 60)

comparison_messages = [
    Message(
        role="user",
        content=[
            TextContent("Compare and contrast these two images in detail:"),
            TextContent("\nImage 1:"),
            ImageContent.from_file(Path(__file__).parent / "images" / "scones.jpg"),
            TextContent("\nImage 2:"),
            ImageContent.from_file(Path(__file__).parent / "images" / "croissant.jpg"),
            TextContent(
                """\nProvide a detailed comparison covering:
- Visual differences in presentation
- Food preparation differences
- Cultural context and origins
- Typical serving occasions
- Nutritional considerations"""
            ),
        ],
    )
]

comparison = model.generate_multimodal(comparison_messages)
print(f"Detailed comparison: {comparison[:500]}...\n")

print("=" * 60)
print("✅ Advanced analysis examples complete!")
print("=" * 60)

