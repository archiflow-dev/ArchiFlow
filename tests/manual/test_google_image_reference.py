"""
Test script for experimenting with Google GenAI API reference image capabilities.

This script helps validate which approaches work for passing reference images
to maintain character consistency in comic generation.

Run with: python tests/manual/test_google_image_reference.py
"""

import os
import sys
import logging
from pathlib import Path
from PIL import Image
import io

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent_framework.config.env_loader import load_env

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_env()

try:
    import google.genai as genai
    from google.genai import types
    from google.genai.types import Part, Content
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.error("google.genai not available. Install with: pip install google-genai")
    sys.exit(1)


def test_1_text_only_generation():
    """Test 1: Baseline text-only generation (current implementation)."""
    print("\n" + "="*80)
    print("TEST 1: Text-Only Generation (Baseline)")
    print("="*80)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in environment")
        return False

    try:
        client = genai.Client(api_key=api_key)

        prompt = "A friendly robot character with glowing blue eyes, chrome body, standing in a laboratory"

        logger.info("Calling GenAI API with text-only prompt...")
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE'],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1",
                    image_size="1K"
                ),
            )
        )

        logger.info("Response received. Extracting image...")
        for i, part in enumerate(response.parts):
            if part.text:
                logger.info(f"Part {i}: TEXT - {part.text}")
            else:
                try:
                    image = part.as_image()
                    if image:
                        output_path = "test_output_text_only.png"
                        image.save(output_path)
                        logger.info(f"✅ SUCCESS: Image saved to {output_path}")
                        return True
                except Exception as e:
                    logger.error(f"Part {i}: Failed - {e}")

        logger.error("❌ FAILED: No image in response")
        return False

    except Exception as e:
        logger.error(f"❌ FAILED: {e}", exc_info=True)
        return False


def test_2_image_reference_base64():
    """Test 2: Try passing reference image as base64 string."""
    print("\n" + "="*80)
    print("TEST 2: Image Reference via Base64")
    print("="*80)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in environment")
        return False

    try:
        # Create a simple test reference image
        ref_image = Image.new('RGB', (100, 100), color='blue')
        img_byte_arr = io.BytesIO()
        ref_image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        import base64
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        client = genai.Client(api_key=api_key)

        prompt = "Generate an image in the same style as the reference"

        logger.info("Attempting to pass reference image as base64...")

        # Try format 1: List with dict
        try:
            contents = [
                prompt,
                {
                    "mime_type": "image/png",
                    "data": img_base64
                }
            ]

            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio="1:1",
                        image_size="1K"
                    ),
                )
            )

            logger.info("✅ Base64 format accepted by API!")
            return True

        except Exception as e:
            logger.warning(f"Base64 format failed: {e}")
            return False

    except Exception as e:
        logger.error(f"❌ FAILED: {e}", exc_info=True)
        return False


def test_3_image_reference_inline_data():
    """Test 3: Try passing reference image as inline_data Part."""
    print("\n" + "="*80)
    print("TEST 3: Image Reference via inline_data Part")
    print("="*80)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in environment")
        return False

    try:
        # Create a simple test reference image
        ref_image = Image.new('RGB', (100, 100), color='red')
        img_byte_arr = io.BytesIO()
        ref_image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        client = genai.Client(api_key=api_key)

        prompt_text = "Generate an image in the same style as the reference"

        logger.info("Attempting to pass reference image as Part with inline_data...")

        try:
            contents = [
                Content(parts=[
                    Part(text=prompt_text),
                    Part(inline_data={
                        "mime_type": "image/png",
                        "data": img_bytes
                    })
                ])
            ]

            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio="1:1",
                        image_size="1K"
                    ),
                )
            )

            logger.info("✅ inline_data Part format accepted by API!")

            # Try to extract image
            for i, part in enumerate(response.parts):
                if not part.text:
                    try:
                        image = part.as_image()
                        if image:
                            output_path = "test_output_with_reference.png"
                            image.save(output_path)
                            logger.info(f"✅ SUCCESS: Image saved to {output_path}")
                            return True
                    except Exception as e:
                        logger.error(f"Part {i}: {e}")

            return True  # API accepted format even if no image

        except Exception as e:
            logger.warning(f"inline_data Part format failed: {e}")
            return False

    except Exception as e:
        logger.error(f"❌ FAILED: {e}", exc_info=True)
        return False


def test_4_vision_model_analysis():
    """Test 4: Use vision model to analyze reference image."""
    print("\n" + "="*80)
    print("TEST 4: Vision Model Analysis (Fallback Approach)")
    print("="*80)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in environment")
        return False

    try:
        # Create a simple test reference image
        ref_image = Image.new('RGB', (200, 200), color='green')
        # Add some visual elements
        from PIL import ImageDraw
        draw = ImageDraw.Draw(ref_image)
        draw.rectangle([50, 50, 150, 150], fill='yellow', outline='black', width=3)

        img_byte_arr = io.BytesIO()
        ref_image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        client = genai.Client(api_key=api_key)

        logger.info("Using vision model to analyze reference image...")

        try:
            contents = [
                Content(parts=[
                    Part(text="""Analyze this image and provide an extremely detailed visual description.

                    Include:
                    - Colors and color palette
                    - Shapes and composition
                    - Style and artistic approach
                    - Any distinctive visual elements

                    Format as a detailed description suitable for recreating similar images."""),
                    Part(inline_data={
                        "mime_type": "image/png",
                        "data": img_bytes
                    })
                ])
            ]

            response = client.models.generate_content(
                model="gemini-2.0-flash",  # Vision model
                contents=contents
            )

            description = response.text
            logger.info(f"✅ Vision analysis successful!")
            logger.info(f"Description: {description}")

            # Now try to use this description for generation
            logger.info("Using description to generate new image...")

            gen_prompt = f"""Create an image with the following visual characteristics:

{description}

Generate in the same style and with similar visual elements."""

            gen_response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=[gen_prompt],
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio="1:1",
                        image_size="1K"
                    ),
                )
            )

            for i, part in enumerate(gen_response.parts):
                if not part.text:
                    try:
                        image = part.as_image()
                        if image:
                            output_path = "test_output_vision_approach.png"
                            image.save(output_path)
                            logger.info(f"✅ SUCCESS: Generated image saved to {output_path}")
                            return True
                    except Exception as e:
                        logger.error(f"Part {i}: {e}")

            return True  # Vision analysis worked even if generation didn't

        except Exception as e:
            logger.warning(f"Vision analysis failed: {e}")
            return False

    except Exception as e:
        logger.error(f"❌ FAILED: {e}", exc_info=True)
        return False


def main():
    """Run all tests and summarize results."""
    print("\n" + "="*80)
    print("GOOGLE GENAI IMAGE REFERENCE TESTING")
    print("="*80)
    print("\nThis script tests different approaches for passing reference images")
    print("to Google's Gemini image generation API.\n")

    if not GOOGLE_AVAILABLE:
        print("❌ google.genai package not available")
        return

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export GOOGLE_API_KEY=your-api-key")
        return

    results = {
        "Test 1: Text-Only (Baseline)": test_1_text_only_generation(),
        "Test 2: Base64 Reference": test_2_image_reference_base64(),
        "Test 3: inline_data Part Reference": test_3_image_reference_inline_data(),
        "Test 4: Vision Model Analysis": test_4_vision_model_analysis(),
    }

    # Summary
    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")

    # Recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    if results["Test 3: inline_data Part Reference"]:
        print("✅ Use inline_data Part format for reference images (Option 1)")
        print("   This is the optimal approach - direct image reference.")
    elif results["Test 2: Base64 Reference"]:
        print("✅ Use base64 format for reference images (Option 1 variant)")
        print("   Direct reference works, just different format.")
    elif results["Test 4: Vision Model Analysis"]:
        print("⚠️  Use vision model analysis approach (Option 3)")
        print("   Image generation model doesn't support direct references.")
        print("   Use vision model to analyze, then generate from description.")
    else:
        print("⚠️  Fall back to enhanced text prompts (Option 2)")
        print("   API doesn't support image references.")
        print("   Use very detailed character descriptions in prompts.")

    print("\nFor full details, see:")
    print("  docs/research/comic_character_consistency_research.md")


if __name__ == "__main__":
    main()
