import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
import io

from agent_framework.llm.google_image_provider import GoogleImageProvider

# Mock google.genai classes
@pytest.fixture
def mock_genai():
    with patch("agent_framework.llm.google_image_provider.genai") as mock:
        # Mock Client and models.generate_content
        mock_client = MagicMock()
        mock.Client.return_value = mock_client
        
        # Mock response structure
        mock_response = MagicMock()
        mock_part = MagicMock()
        
        # Create a valid mock image return
        mock_image = Image.new("RGB", (100, 100), "blue")
        mock_part.text = None
        mock_part.as_image.return_value = mock_image
        
        mock_response.parts = [mock_part]
        mock_client.models.generate_content.return_value = mock_response
        
        # Mock types
        with patch("agent_framework.llm.google_image_provider.types") as mock_types:
            mock_types.GenerateContentConfig = MagicMock()
            mock_types.ImageConfig = MagicMock()
            yield mock

@pytest.fixture
def provider(mock_genai):
    return GoogleImageProvider(api_key="test_key")

def test_generate_image_with_reference(provider, mock_genai):
    """Test generating image with reference images."""
    # Create valid PIL image
    ref_image = Image.new("RGB", (50, 50), "red")
    prompt = "Draw a blue version of this"
    
    # Call generate_image
    result = provider.generate_image(
        prompt=prompt,
        ref_images=[ref_image],
        aspect_ratio="1:1"
    )
    
    # Verify client was called correctly
    mock_client = provider.client
    mock_client.models.generate_content.assert_called_once()
    
    # Check arguments passed to API
    call_args = mock_client.models.generate_content.call_args
    assert call_args is not None
    
    # Check contents payload
    # Should contain [prompt, ref_image]
    kwargs = call_args.kwargs
    contents = kwargs["contents"]
    assert len(contents) == 2
    assert contents[0] == prompt
    assert contents[1] == ref_image
    
    # Verify result
    assert isinstance(result, Image.Image)

def test_generate_image_without_reference(provider, mock_genai):
    """Test generating image without reference images."""
    prompt = "Draw a cat"
    
    result = provider.generate_image(
        prompt=prompt,
        ref_images=None
    )
    
    # Verify contents only has prompt
    mock_client = provider.client
    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs["contents"]
    
    assert len(contents) == 1
    assert contents[0] == prompt

def test_skip_invalid_reference(provider, mock_genai):
    """Test that non-PIL images are skipped."""
    prompt = "Draw something"
    invalid_ref = "not an image"

    result = provider.generate_image(
        prompt=prompt,
        ref_images=[invalid_ref]
    )

    # Verify skipped
    mock_client = provider.client
    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs["contents"]

    assert len(contents) == 1
    assert contents[0] == prompt

def test_response_parts_is_none(provider, mock_genai):
    """Test handling when API returns response with None parts."""
    # Mock response with None parts (API error case)
    mock_response = MagicMock()
    mock_response.parts = None  # Simulate API error/empty response

    mock_client = provider.client
    mock_client.models.generate_content.return_value = mock_response

    prompt = "Draw a cat"

    # Should raise Exception with descriptive message (ValueError is caught and re-wrapped)
    with pytest.raises(Exception, match="API response has no parts"):
        provider.generate_image(prompt=prompt)
