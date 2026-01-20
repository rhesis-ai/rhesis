"""Example 2: Advanced Analysis and Image Generation

Demonstrates advanced multimodal capabilities:
- Multi-turn conversations with images
- Detailed image analysis and understanding
- Creative storytelling from images
- Image generation using Vertex AI Imagen
- Analyze-then-generate workflow
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

# Example 6: Image Generation with Vertex AI Imagen
print("-" * 60)
print("Example 6: Generate images from text prompts")
print("-" * 60)

# Create output directory
output_dir = Path(__file__).parent / "images" / "generated"
output_dir.mkdir(exist_ok=True)

print("\n🎨 Using Vertex AI Imagen for image generation")
print("   Note: Requires Google Cloud authentication\n")

try:
    # Get Vertex AI Imagen model
    imagen_model = get_model("vertex_ai", "imagegeneration@006")
    print(f"✅ Image generation model: {imagen_model.model_name}\n")

    # Generate a simple image
    prompt1 = "A cozy bakery display with fresh pastries, warm lighting, rustic wooden shelves"
    print(f"Prompt 1: {prompt1}")

    image_url = imagen_model.generate_image(prompt1, n=1, size="1024x1024")
    print(f"✅ Generated: {image_url}")

    # Download and save
    import requests

    img_data = requests.get(image_url).content
    output_path = output_dir / "bakery_display.png"
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"💾 Saved to: {output_path}\n")

    # Generate multiple variations
    prompt2 = "A minimalist workspace with laptop and coffee, morning light, clean aesthetic"
    print(f"Prompt 2: {prompt2}")
    print("Generating 2 variations...")

    image_urls = imagen_model.generate_image(prompt2, n=2, size="1024x1024")
    for i, url in enumerate(image_urls, 1):
        img_data = requests.get(url).content
        output_path = output_dir / f"workspace_v{i}.png"
        with open(output_path, "wb") as f:
            f.write(img_data)
        print(f"💾 Variation {i} saved to: {output_path}")

    print(f"\n📁 All generated images saved to: {output_dir}")

except Exception as e:
    print(f"⚠️  Image generation requires Vertex AI setup: {e}")
    print("\nSetup instructions:")
    print("1. Install: pip install google-cloud-aiplatform")
    print("2. Authenticate: gcloud auth application-default login")
    print("3. Enable Vertex AI API in your Google Cloud project")
    print("\nSkipping image generation...\n")

# Example 7: Analyze-then-Generate workflow
print("-" * 60)
print("Example 7: Analyze existing image and generate similar")
print("-" * 60)

print("Step 1: Analyze the original image")
analysis_prompt = """Create a detailed image generation prompt based on this image.
Focus on: composition, lighting, color palette, mood, and style.
Format as a concise prompt suitable for image generation (2-3 sentences)."""

generation_prompt = model.analyze_content(ImageContent.from_file(image_path), analysis_prompt)
print(f"Generated prompt: {generation_prompt[:200]}...\n")

print("Step 2: Generate new image based on analysis")
try:
    imagen_model = get_model("vertex_ai", "imagegeneration@006")

    image_url = imagen_model.generate_image(generation_prompt, n=1, size="1024x1024")

    img_data = requests.get(image_url).content
    output_path = output_dir / "recreated_scene.png"
    with open(output_path, "wb") as f:
        f.write(img_data)

    print(f"✅ Generated similar image: {output_path}\n")

except Exception as e:
    print(f"⚠️  Skipping generation: {e}\n")

print("=" * 60)
print("✅ Advanced analysis and generation examples complete!")
print("=" * 60)
