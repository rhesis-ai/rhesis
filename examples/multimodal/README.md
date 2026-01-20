# Multimodal Examples

This folder contains examples demonstrating **multimodal capabilities** including image analysis and image generation using Google's AI models.

## Setup

1. Make sure you have your API keys in `../.env`:
   ```bash
   # For image analysis (Gemini)
   GEMINI_API_KEY=your_gemini_key_here
   
   # For image generation - Choose one:
   
   # Option 1: Gemini (Recommended - Simpler)
   GEMINI_API_KEY=your_gemini_key_here  # Same key as above
   
   # Option 2: Vertex AI Imagen (Advanced)
   GOOGLE_APPLICATION_CREDENTIALS=your_service_account_json_or_base64
   VERTEX_AI_LOCATION=us-central1
   VERTEX_AI_PROJECT=your_project_id
   ```

2. Install dependencies (if not already installed):
   ```bash
   cd ../../sdk
   uv sync
   ```

## Examples

### Quickstart (`quickstart.py`)
A simple introduction to Gemini's vision capabilities.

```bash
cd examples/multimodal
uv run --project ../../sdk python quickstart.py
```

**What it does:**
- Analyzes a local image
- Asks follow-up questions with context
- Compares two images side-by-side

### 1. Image Analysis (`1_analyze_images.py`)
Demonstrates core vision capabilities:
- Analyze local images with detailed descriptions
- Compare multiple images
- Extract structured data with Pydantic schemas

```bash
uv run --project ../../sdk python 1_analyze_images.py
```

**Features:**
- Single image analysis with detailed descriptions
- Side-by-side image comparison
- Structured extraction (ingredients, colors, occasions)

### 2. Advanced Analysis (`2_advanced_analysis.py`)
Shows advanced vision analysis techniques with Gemini:
- Multi-turn conversations with image context
- Creative storytelling from images
- Technical photography analysis
- Detailed scene descriptions

```bash
uv run --project ../../sdk python 2_advanced_analysis.py
```

**Demonstrates:**
- Context-aware follow-up questions
- Photography technique analysis
- Creative content generation from images
- Comprehensive scene understanding

### 3. Image Generation (`3_image_generation.py`)
Generate images using Google's Imagen models via Gemini or Vertex AI:
- Single image generation from text prompts
- Multiple variations of an image
- Analyze-then-generate workflow

```bash
uv run --project ../../sdk python 3_image_generation.py
```

**Two Options:**

**Option 1: Gemini (Recommended)**
- Simpler setup - just needs `GEMINI_API_KEY`
- Model: `gemini/imagen-4.0-generate-001`
- Get API key from [Google AI Studio](https://aistudio.google.com/apikey)

**Option 2: Vertex AI (Advanced)**
- Requires Google Cloud credentials
- Model: `vertex_ai/imagegeneration@006`
- Environment variables: `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEX_AI_LOCATION`, `VERTEX_AI_PROJECT`

**Demonstrates:**
- Text-to-image generation
- Multiple image variations
- Combining vision analysis with image generation
- Automatic fallback between providers

### 4. Practical Use Cases (`4_practical_use_cases.py`)
Real-world applications with structured outputs:
- Product catalog generation
- Quality inspection reports
- Educational content creation
- Accessibility alt-text generation
- Content moderation

```bash
uv run --project ../../sdk python 4_practical_use_cases.py
```

**Use Cases:**
- 📦 **E-commerce**: Extract product info for catalogs
- 🔍 **Quality Control**: Automated quality inspections
- 📚 **Education**: Generate lesson plans from images
- ♿ **Accessibility**: Create alt-text for screen readers
- 🛡️ **Moderation**: Check content safety and appropriateness

## Sample Images

### Included Images (`images/`)
- `scones.jpg` - Blueberry scones with coffee
- `croissant.jpg` - Fresh croissants

These images are used throughout the examples to demonstrate various analysis capabilities.

## Features Demonstrated

### Vision Analysis (Gemini)
✅ **Image Analysis**: Detailed understanding of image content  
✅ **Multi-Image Comparison**: Side-by-side analysis  
✅ **Structured Extraction**: Pydantic schemas for reliable data  
✅ **Context Retention**: Multi-turn conversations with images  
✅ **Multiple Input Methods**: Files, URLs, or bytes  
✅ **Photography Analysis**: Technical camera and lighting insights  
✅ **Creative Generation**: Stories and descriptions from images  
✅ **Quality Inspection**: Automated quality checks  
✅ **Accessibility**: Alt-text and descriptions for screen readers  
✅ **Content Safety**: Moderation and age-appropriateness checks

### Image Generation (Gemini & Vertex AI Imagen)
✅ **Text-to-Image**: Generate images from detailed text prompts  
✅ **Multiple Variations**: Generate multiple versions of an image  
✅ **High Quality**: 1024x1024 and other resolutions  
✅ **Analyze & Generate**: Combine vision analysis with image creation  
✅ **Flexible Setup**: Works with both Gemini API and Vertex AI  

## API Quick Reference

### Basic Analysis
```python
from rhesis.sdk.models import get_model, ImageContent

model = get_model("gemini", "gemini-2.0-flash")

# Analyze a single image
response = model.analyze_content(
    ImageContent.from_file("image.jpg"),
    "Describe this image in detail"
)
```

### Structured Extraction
```python
from pydantic import BaseModel

class ImageData(BaseModel):
    main_subject: str
    colors: list[str]
    mood: str

result = model.generate_multimodal(messages, schema=ImageData)
```

### Multi-Image Analysis
```python
from rhesis.sdk.models import Message, TextContent, ImageContent

messages = [
    Message(role="user", content=[
        TextContent("Compare these images:"),
        ImageContent.from_file("image1.jpg"),
        ImageContent.from_file("image2.jpg"),
        TextContent("What are the differences?")
    ])
]

response = model.generate_multimodal(messages)
```

### Multi-Turn Conversations
```python
# First question with image
messages = [
    Message(role="user", content=[
        ImageContent.from_file("image.jpg"),
        TextContent("What's in this image?")
    ])
]

response1 = model.generate_multimodal(messages)

# Follow-up question (image stays in context)
messages.append(Message(role="assistant", content=response1))
messages.append(Message(role="user", content="How would I make this?"))

response2 = model.generate_multimodal(messages)
```

### Image Generation
```python
from rhesis.sdk.models import get_model

# Option 1: Using Gemini (simpler)
model = get_model("gemini", "imagen-3.0-generate-002")

# Option 2: Using Vertex AI (advanced)
model = get_model("vertex_ai", "imagegeneration@006")

# Generate a single image
image_url = model.generate_image(
    "A cozy bakery with fresh pastries",
    n=1,
    size="1024x1024"
)

# Generate multiple variations
image_urls = model.generate_image(
    "A minimalist workspace",
    n=3,
    size="1024x1024"
)
```

## Troubleshooting

### Missing API Key (Gemini)
If you see `GEMINI_API_KEY is not set`:
- Check that `../.env` exists with your API key
- Keys should not be quoted in .env
- Try: `export GEMINI_API_KEY=your_key`

### Vertex AI Authentication (Image Generation)
If you see authentication errors:
1. Install Google Cloud SDK: `pip install google-cloud-aiplatform`
2. Set up credentials in `../.env`:
   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=base64_encoded_json_or_/path/to/file.json
   VERTEX_AI_LOCATION=us-central1
   VERTEX_AI_PROJECT=your-project-id
   ```
3. Enable Vertex AI API in your Google Cloud Console

### File Not Found Errors
- Run examples from `examples/multimodal/` directory
- Or use: `uv run --project ../../sdk python quickstart.py`

### Rate Limiting
If you hit rate limits:
- Add delays between requests
- Use a paid API tier
- Reduce the number of images per request

## Next Steps

1. **Modify Prompts**: Try different analysis questions
2. **Add Your Images**: Place your own images in `images/`
3. **Custom Schemas**: Create Pydantic models for your use case
4. **Build Applications**: Use these patterns in production apps
5. **Explore Audio/Video**: Gemini 2.0 also supports audio and video analysis

## Model Capabilities

### Gemini 2.0 Flash (Vision Analysis)
- ✅ **Images**: JPEG, PNG, WebP, GIF
- ✅ **Audio**: MP3, WAV, OGG (use `AudioContent`)
- ✅ **Video**: MP4, MOV, AVI (use `VideoContent`)  
- ✅ **PDFs**: Document analysis (use `FileContent`)
- ✅ **Multiple Modalities**: Mix text, images, audio, video in one request

### Google Imagen (Image Generation)
Available via **Gemini** or **Vertex AI**:

**Gemini (gemini/imagen-3.0-generate-002)**
- ✅ **Simple Setup**: Only needs GEMINI_API_KEY
- ✅ **Text-to-Image**: Generate images from text descriptions
- ✅ **High Resolution**: 1024x1024 and other sizes
- ✅ **Batch Generation**: Generate multiple variations at once

**Vertex AI (vertex_ai/imagegeneration@006)**
- ✅ **Enterprise Features**: Full Google Cloud integration
- ✅ **Base64 Output**: Images returned as data URLs for easy saving
- ✅ **Advanced Configuration**: Custom project/location settings

For more information, see the [SDK documentation](../../docs/).
