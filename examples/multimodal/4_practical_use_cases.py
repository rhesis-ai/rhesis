"""Example 3: Practical Use Cases with Gemini Vision

Demonstrates real-world applications of multimodal analysis:
- Document understanding and extraction
- Product catalog analysis
- Quality inspection
- Educational content analysis
"""

from pathlib import Path

# Load environment variables from parent .env file
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed.")

from pydantic import BaseModel, Field

from rhesis.sdk.models import ImageContent, Message, TextContent, get_model

print("=" * 60)
print("Practical Use Cases with Gemini Vision")
print("=" * 60)

model = get_model("gemini", "gemini-2.0-flash")
print(f"\n✅ Using model: {model.model_name}\n")

# Use Case 1: Product Catalog - Extract structured information
print("-" * 60)
print("Use Case 1: Product Catalog Generation")
print("-" * 60)


class ProductInfo(BaseModel):
    """Structured product information for catalog."""

    product_name: str = Field(description="Name of the product")
    category: str = Field(description="Product category")
    description: str = Field(description="Detailed product description")
    key_features: list[str] = Field(description="List of key features")
    suggested_price_range: str = Field(description="Suggested retail price range")
    target_audience: str = Field(description="Primary target customer demographic")
    occasion: list[str] = Field(description="Suitable occasions for this product")


image_path = Path(__file__).parent / "images" / "scones.jpg"

messages = [
    Message(
        role="system",
        content=(
            "You are a product catalog assistant. Analyze images and provide "
            "structured product information for e-commerce."
        ),
    ),
    Message(
        role="user",
        content=[
            ImageContent.from_file(image_path),
            TextContent(
                "Extract comprehensive product information from this image for our catalog."
            ),
        ],
    ),
]

product_data = model.generate_multimodal(messages, schema=ProductInfo)

print("📦 Product Catalog Entry:")
print(f"   Name: {product_data['product_name']}")
print(f"   Category: {product_data['category']}")
print(f"   Description: {product_data['description'][:100]}...")
print(f"   Key Features: {', '.join(product_data['key_features'][:3])}")
print(f"   Price Range: {product_data['suggested_price_range']}")
print(f"   Target Audience: {product_data['target_audience']}")
print(f"   Occasions: {', '.join(product_data['occasion'])}\n")

# Use Case 2: Quality Inspection - Check for issues
print("-" * 60)
print("Use Case 2: Food Quality Inspection")
print("-" * 60)


class QualityCheck(BaseModel):
    """Quality inspection results."""

    overall_quality: str = Field(description="Overall quality rating: Excellent, Good, Fair, Poor")
    freshness_indicators: list[str] = Field(description="Signs of freshness observed")
    potential_issues: list[str] = Field(description="Any quality concerns or defects")
    presentation_score: int = Field(description="Presentation score from 1-10")
    recommendations: list[str] = Field(description="Recommendations for improvement")


inspection_messages = [
    Message(
        role="system",
        content=(
            "You are a food quality inspector. Analyze images and provide "
            "detailed quality assessments."
        ),
    ),
    Message(
        role="user",
        content=[
            ImageContent.from_file(image_path),
            TextContent(
                "Perform a quality inspection of this food item. Check for freshness, "
                "presentation, and any concerns."
            ),
        ],
    ),
]

quality_report = model.generate_multimodal(inspection_messages, schema=QualityCheck)

print("🔍 Quality Inspection Report:")
print(f"   Overall Quality: {quality_report['overall_quality']}")
print(f"   Presentation Score: {quality_report['presentation_score']}/10")
print("   Freshness Indicators:")
for indicator in quality_report["freshness_indicators"][:3]:
    print(f"      - {indicator}")
if quality_report["potential_issues"]:
    print("   Potential Issues:")
    for issue in quality_report["potential_issues"]:
        print(f"      - {issue}")
print("   Recommendations:")
for rec in quality_report["recommendations"][:2]:
    print(f"      - {rec}")
print()

# Use Case 3: Educational Content - Create learning materials
print("-" * 60)
print("Use Case 3: Educational Content Generation")
print("-" * 60)

educational_prompt = """Create educational content from this image for a culinary school:

1. **Lesson Topic**: Identify what culinary topic this image illustrates
2. **Learning Objectives**: List 3-4 key learning objectives
3. **Technical Points**: Explain 3-4 technical aspects students should notice
4. **Discussion Questions**: Provide 3 thought-provoking questions for class discussion
5. **Practice Exercise**: Suggest a hands-on exercise based on this image

Format as a structured lesson plan."""

lesson_plan = model.analyze_content(ImageContent.from_file(image_path), educational_prompt)

print("📚 Educational Content:")
print(lesson_plan[:600])
print("...\n")

# Use Case 4: Accessibility - Generate alt text
print("-" * 60)
print("Use Case 4: Accessibility - Alt Text Generation")
print("-" * 60)


class AltTextOutput(BaseModel):
    """Accessibility-friendly image descriptions."""

    short_alt_text: str = Field(description="Brief alt text (100 chars max) for screen readers")
    long_description: str = Field(description="Detailed description for extended accessibility")
    key_elements: list[str] = Field(description="List of key visual elements in reading order")


alt_text_messages = [
    Message(
        role="system",
        content=(
            "You are an accessibility specialist. Generate clear, descriptive alt text for images."
        ),
    ),
    Message(
        role="user",
        content=[
            ImageContent.from_file(image_path),
            TextContent(
                "Generate comprehensive alt text and descriptions for accessibility purposes."
            ),
        ],
    ),
]

alt_text_data = model.generate_multimodal(alt_text_messages, schema=AltTextOutput)

print("♿ Accessibility Content:")
print(f"   Short Alt Text: {alt_text_data['short_alt_text']}")
print(f"   Long Description: {alt_text_data['long_description'][:150]}...")
print("   Key Elements (in order):")
for element in alt_text_data["key_elements"][:4]:
    print(f"      - {element}")
print()

# Use Case 5: Content Moderation
print("-" * 60)
print("Use Case 5: Content Moderation Check")
print("-" * 60)


class ModerationCheck(BaseModel):
    """Content moderation analysis."""

    is_safe: bool = Field(description="Whether content is safe for general audiences")
    content_type: str = Field(description="Type of content (food, product, scene, etc.)")
    age_appropriateness: str = Field(description="Age rating: All Ages, Teen, Adult")
    concerns: list[str] = Field(description="Any content concerns or flags")
    context_notes: str = Field(description="Additional context for moderation decision")


moderation_messages = [
    Message(
        role="system",
        content="You are a content moderator. Analyze images for safety and appropriateness.",
    ),
    Message(
        role="user",
        content=[
            ImageContent.from_file(image_path),
            TextContent("Check this image for content safety and appropriateness."),
        ],
    ),
]

moderation_result = model.generate_multimodal(moderation_messages, schema=ModerationCheck)

print("🛡️  Content Moderation Result:")
print(f"   Safe for Platform: {'✅ Yes' if moderation_result['is_safe'] else '❌ No'}")
print(f"   Content Type: {moderation_result['content_type']}")
print(f"   Age Rating: {moderation_result['age_appropriateness']}")
if moderation_result["concerns"]:
    print(f"   Concerns: {', '.join(moderation_result['concerns'])}")
else:
    print("   Concerns: None")
print(f"   Notes: {moderation_result['context_notes'][:100]}...")
print()

print("=" * 60)
print("✅ All practical use cases demonstrated!")
print("=" * 60)
