"""Example 3: Image Generation with Google Imagen

Demonstrates image generation capabilities using both Gemini and Vertex AI:
- Gemini: Simple setup with just GEMINI_API_KEY
- Vertex AI: Advanced setup with Google Cloud credentials
- Single image generation and multiple variations
- Analyze existing image and generate similar
"""

import base64
from pathlib import Path

# Load environment variables from parent .env file
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed.")

import requests

from rhesis.sdk.models import ImageContent, get_model

print("=" * 60)
print("Image Generation with Google Imagen")
print("=" * 60)

# Prepare output directory
output_dir = Path(__file__).parent / "images" / "generated"
output_dir.mkdir(parents=True, exist_ok=True)

# Try Gemini first (simpler setup), fallback to Vertex AI
try:
    # Option 1: Gemini - simpler setup, just needs GEMINI_API_KEY
    print("\n🎨 Attempting to use Gemini for image generation...")
    print("   (Requires only GEMINI_API_KEY environment variable)")
    imagen_model = get_model("gemini", "imagen-3.0-generate-002")
    provider = "Gemini"
    print(f"✅ Using {provider}: {imagen_model.model_name}\n")

except Exception as e:
    # Option 2: Vertex AI - more complex setup but fully managed
    print(f"⚠️  Gemini not available: {e}")
    print("\n🎨 Falling back to Vertex AI Imagen...")
    print("   (Requires Google Cloud credentials)")
    try:
        imagen_model = get_model("vertex_ai", "imagegeneration@006")
        provider = "Vertex AI"
        print(f"✅ Using {provider}: {imagen_model.model_name}\n")
    except Exception as vertex_e:
        print(f"❌ Vertex AI also not available: {vertex_e}")
        print("\nPlease set up either:")
        print("  1. GEMINI_API_KEY for Gemini (simpler)")
        print("  2. Google Cloud credentials for Vertex AI")
        exit(1)

try:
    # Example 1: Generate a single image
    print("-" * 60)
    print("Example 1: Generate a single image")
    print("-" * 60)

    # Generate a simple image
    prompt1 = "A cozy bakery display with fresh pastries, warm lighting, rustic wooden shelves"
    print(f"Prompt: {prompt1}")

    image_url = imagen_model.generate_image(prompt1, n=1, size="1024x1024")
    print(f"✅ Generated: {image_url[:100]}...")

    # Download and save (handle both URL and base64)
    output_path = output_dir / "bakery_display.png"

    if image_url.startswith("data:image"):
        # Base64 encoded image
        base64_data = image_url.split(",")[1]
        img_data = base64.b64decode(base64_data)
    else:
        # URL - download it
        img_data = requests.get(image_url).content

    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"💾 Saved to: {output_path}\n")

    # Example 2: Generate multiple variations
    print("-" * 60)
    print("Example 2: Generate multiple variations")
    print("-" * 60)

    prompt2 = "A minimalist workspace with laptop and coffee, morning light, clean aesthetic"
    print(f"Prompt: {prompt2}")
    print("Generating 2 variations...")

    image_urls = imagen_model.generate_image(prompt2, n=2, size="1024x1024")
    for i, url in enumerate(image_urls, 1):
        if url.startswith("data:image"):
            base64_data = url.split(",")[1]
            img_data = base64.b64decode(base64_data)
        else:
            img_data = requests.get(url).content

        output_path = output_dir / f"workspace_v{i}.png"
        with open(output_path, "wb") as f:
            f.write(img_data)
        print(f"💾 Variation {i} saved to: {output_path}")

    print(f"\n📁 All generated images saved to: {output_dir}\n")

    # Example 3: Analyze existing image and generate similar
    print("-" * 60)
    print("Example 3: Analyze existing image and generate similar")
    print("-" * 60)

    # First, analyze the image with vision model
    vision_model = get_model("gemini", "gemini-2.0-flash")

    print("Step 1: Analyze the original image")
    analysis_prompt = """Describe this image in detail for image generation purposes.
Focus on:
- Main subjects and their arrangement
- Visual style and aesthetic
- Colors and lighting
- Mood and atmosphere
- Composition and framing

Format the description as a detailed image generation prompt."""

    original_image_path = Path(__file__).parent / "images" / "scones.jpg"
    generation_prompt = vision_model.analyze_content(
        ImageContent.from_file(original_image_path), analysis_prompt
    )
    print(f"Generated prompt: {generation_prompt[:200]}...\n")

    print("Step 2: Generate new image based on analysis")
    try:
        image_url = imagen_model.generate_image(generation_prompt, n=1, size="1024x1024")

        if image_url.startswith("data:image"):
            base64_data = image_url.split(",")[1]
            img_data = base64.b64decode(base64_data)
        else:
            img_data = requests.get(image_url).content

        output_path = output_dir / "recreated_scene.png"
        with open(output_path, "wb") as f:
            f.write(img_data)

        print(f"✅ Generated similar image: {output_path}\n")

    except Exception as e:
        print(f"⚠️  Skipping generation: {e}\n")

    print("=" * 60)
    print("✅ Image generation examples complete!")
    print(f"📁 Check the generated images in: {output_dir}")
    print("=" * 60)

except ValueError as e:
    print(f"⚠️  Image generation failed: {e}")
    print("\n" + "=" * 60)
    print("Setup Instructions")
    print("=" * 60)
    print("\n📋 Option 1: Gemini (Recommended - Simpler Setup)")
    print("1. Get an API key from https://aistudio.google.com/apikey")
    print("2. Set environment variable: GEMINI_API_KEY=your_key")
    print("3. Model: gemini/imagen-3.0-generate-002")
    print("\n📋 Option 2: Vertex AI (Advanced)")
    print("1. Install: pip install google-cloud-aiplatform")
    print("2. Authenticate: gcloud auth application-default login")
    print("3. Enable Vertex AI API in your Google Cloud project")
    print("4. Set environment variables:")
    print("   - GOOGLE_APPLICATION_CREDENTIALS (base64 or file path)")
    print("   - VERTEX_AI_LOCATION (e.g., 'us-central1')")
    print("   - VERTEX_AI_PROJECT (your GCP project ID)")
    print("5. Model: vertex_ai/imagegeneration@006")
