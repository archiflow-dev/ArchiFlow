"""
Tests for OpenAI Image Provider.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import io
import requests

from agent_framework.llm.openai_image_provider import OpenAIImageProvider
from agent_framework.llm.image_provider_base import ImageProvider


class TestOpenAIImageProvider:
    """Test cases for OpenAIImageProvider."""

    @pytest.fixture
    def mock_openai(self):
        """Mock the openai module."""
        with patch('agent_framework.llm.openai_image_provider.OpenAI') as mock:
            yield mock

    @pytest.fixture
    def provider(self, mock_openai):
        """Create a provider instance for testing."""
        # Set up mock client
        mock_client = Mock()
        mock_openai.return_value = mock_client

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            provider = OpenAIImageProvider()
            # Override the client with our mock
            provider.client = mock_client
            yield provider

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        with patch('os.environ', {}):
            provider = OpenAIImageProvider(api_key="test-key")
            assert provider.api_key == "test-key"
            assert provider.provider_name == "openai"
            assert provider.model_name == "gpt-image-1.5"  # Updated default model

    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with patch('os.environ', {}):
            with pytest.raises(ValueError, match="OpenAI API key is required"):
                OpenAIImageProvider()

    @patch('agent_framework.llm.openai_image_provider.OPENAI_AVAILABLE', False)
    def test_init_without_openai_package(self):
        """Test initialization fails without openai package."""
        with pytest.raises(ImportError, match="openai package is required"):
            OpenAIImageProvider(api_key="test-key")

    def test_provider_properties(self, provider):
        """Test provider properties."""
        assert provider.provider_name == "openai"
        assert provider.model_name == "gpt-image-1.5"  # Updated default model
        assert "OpenAIImageProvider" in repr(provider)

    def test_get_supported_sizes(self, provider):
        """Test get supported sizes."""
        sizes = provider.get_supported_sizes()
        assert isinstance(sizes, list)
        assert (1024, 1024) in sizes
        assert (1792, 1024) in sizes
        assert (1024, 1792) in sizes

    def test_get_supported_styles(self, provider):
        """Test get supported styles."""
        styles = provider.get_supported_styles()
        assert isinstance(styles, list)
        # gpt-image-1.5 supports more styles
        assert "natural" in styles
        assert "vivid" in styles
        assert "photorealistic" in styles
        assert "digital-art" in styles
        assert "presentation" in styles
        assert "minimalist" in styles

    def test_map_resolution_to_size(self, provider):
        """Test mapping resolution to OpenAI size format."""
        # Test with 'x' format (already correct)
        assert provider._map_resolution_to_size("1024x1024", "1:1") == "1024x1024"
        assert provider._map_resolution_to_size("1792x1024", "16:9") == "1792x1024"

        # Test aspect ratio mapping
        assert provider._map_resolution_to_size("2K", "16:9") == "1792x1024"
        assert provider._map_resolution_to_size("2K", "9:16") == "1024x1792"
        assert provider._map_resolution_to_size("2K", "1:1") == "1024x1024"

    def test_enhance_prompt_with_reference(self, provider):
        """Test prompt enhancement with reference style."""
        provider.reference_description = "Modern blue theme with minimal design"
        provider.reference_image = Mock(spec=Image.Image)  # Need this for the condition

        # First call should include slide number 1
        prompt = "A bar chart"
        enhanced = provider._enhance_prompt_with_reference(prompt, ref_images=[provider.reference_image])
        assert "bar chart" in enhanced
        assert "Modern blue theme" in enhanced
        assert "slide #1" in enhanced

        # Second call should increment slide number
        enhanced = provider._enhance_prompt_with_reference(prompt, ref_images=[provider.reference_image])
        assert "slide #2" in enhanced

    def test_enhance_prompt_without_reference(self, provider):
        """Test prompt enhancement without reference style."""
        prompt = "A pie chart"
        enhanced = provider._enhance_prompt_with_reference(prompt)
        assert "pie chart" in enhanced
        assert "Professional presentation slide" in enhanced
        assert "Clean, modern design" in enhanced

    def test_generate_image_success(self, provider):
        """Test successful image generation."""
        # Since default model is gpt-image-1.5, test DALL-E style generation
        # Create a provider with DALL-E model for this test
        with patch('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            dalle_provider = OpenAIImageProvider(model="dall-e-3")
            dalle_provider.client = provider.client

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.data = [Mock(url="http://example.com/image.png")]
        dalle_provider.client.images.generate.return_value = mock_response

        # Mock requests response
        mock_image_data = b"fake_image_data"
        mock_img_response = Mock()
        mock_img_response.content = mock_image_data
        mock_img_response.raise_for_status.return_value = None

        # Mock PIL Image.open
        mock_image = Mock(spec=Image.Image)

        with patch('requests.get', return_value=mock_img_response):
            with patch('PIL.Image.open', return_value=mock_image):
                # Generate image
                result = dalle_provider.generate_image("Test prompt")

                # Verify
                assert result == mock_image
                dalle_provider.client.images.generate.assert_called_once()
                # Note: requests.get is called within the function, so we can't easily verify the exact call
                # without more complex mocking

    def test_generate_with_gpt_image(self, provider):
        """Test gpt-image-1.5 specific generation with reference images."""
        # Create a new provider with gpt-image-1.5 model
        with patch('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            gpt_provider = OpenAIImageProvider(model="gpt-image-1.5")
            gpt_provider.client = provider.client

        # Mock the chat completions response
        mock_response = Mock()
        mock_response.choices = [Mock(
            message=Mock(
                content="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
        )]
        gpt_provider.client.chat.completions.create.return_value = mock_response

        # Create a mock reference image
        mock_ref_image = Mock(spec=Image.Image)
        mock_ref_image.save = Mock()
        buffered = io.BytesIO()
        mock_ref_image.save.return_value = None

        # Test generation with reference image
        result = gpt_provider._generate_with_gpt_image(
            prompt="Test prompt",
            ref_images=[mock_ref_image],
            aspect_ratio="16:9",
            resolution="1024x1024"
        )

        # Verify the API was called correctly
        gpt_provider.client.chat.completions.create.assert_called_once()
        call_args = gpt_provider.client.chat.completions.create.call_args
        assert call_args[1]['model'] == "gpt-image-1.5"
        assert len(call_args[1]['messages'][0]['content']) == 2  # Image + text
        assert call_args[1]['response_format'] == {"type": "image"}

    def test_generate_image_api_failure(self, provider):
        """Test image generation with API failure."""
        provider.client.images.generate.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="Error generating image with OpenAI"):
            provider.generate_image("Test prompt")

    def test_validate_connection_success(self, provider):
        """Test successful connection validation."""
        # Mock models response for gpt-image-1.5
        mock_model = Mock(id="gpt-image-1.5")
        provider.client.models.list.return_value.data = [mock_model]

        result = provider.validate_connection()
        assert result is True

    def test_validate_connection_gpt_image_model(self, provider):
        """Test connection validation with gpt-image model."""
        # Create a new provider with gpt-image-1.5 model
        with patch('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            gpt_provider = OpenAIImageProvider(model="gpt-image-1.5")
            gpt_provider.client = provider.client

        # Mock models response
        mock_model = Mock(id="gpt-image-1.5")
        gpt_provider.client.models.list.return_value.data = [mock_model]

        result = gpt_provider.validate_connection()
        assert result is True

    def test_validate_connection_no_models(self, provider):
        """Test connection validation with no DALL-E models."""
        provider.client.models.list.return_value.data = []

        result = provider.validate_connection()
        assert result is False

    def test_validate_connection_failure(self, provider):
        """Test connection validation with failure."""
        provider.client.models.list.side_effect = Exception("Connection failed")

        with pytest.raises(RuntimeError, match="Cannot connect to OpenAI API"):
            provider.validate_connection()

    @patch.object(OpenAIImageProvider, 'generate_image')
    def test_generate_first_slide(self, mock_generate, provider):
        """Test generating first slide."""
        # Mock the generated image
        mock_image = Mock(spec=Image.Image)
        mock_generate.return_value = mock_image

        # Generate first slide
        result = provider.generate_first_slide("Test title slide")

        # Verify
        assert result == mock_image
        assert provider.reference_image == mock_image
        assert provider.reference_description is not None
        assert "VISUAL STYLE GUIDE" in provider.reference_description
        assert provider._slide_counter == 1

        # Verify the prompt was enhanced
        call_args = mock_generate.call_args
        assert "professional presentation slide" in call_args[1]['prompt'].lower()
        assert "establish the visual style" in call_args[1]['prompt'].lower()

    @patch.object(OpenAIImageProvider, 'generate_first_slide')
    @patch.object(OpenAIImageProvider, 'generate_image')
    def test_generate_subsequent_slide_without_reference(self, mock_generate, mock_first, provider):
        """Test generating subsequent slide without reference."""
        # No reference image or description
        provider.reference_description = None
        provider.reference_image = None

        # Mock first slide generation
        mock_image = Mock(spec=Image.Image)
        mock_first.return_value = mock_image

        # Generate subsequent slide
        result = provider.generate_subsequent_slide("Test content", slide_number=2)

        # Verify fallback to first slide
        mock_first.assert_called_once()
        assert result == mock_image

    @patch.object(OpenAIImageProvider, 'generate_image')
    def test_generate_subsequent_slide_with_reference(self, mock_generate, provider):
        """Test generating subsequent slide with reference."""
        # Set up reference - need both description and image for the condition
        provider.reference_description = "Test style guide"
        provider.reference_image = Mock(spec=Image.Image)

        # Mock the generated image
        mock_image = Mock(spec=Image.Image)
        mock_generate.return_value = mock_image

        # Generate subsequent slide
        result = provider.generate_subsequent_slide("Test content", slide_number=3)

        # Verify
        assert result == mock_image
        assert provider._slide_counter == 3

        # Verify the generate_image was called with correct parameters
        mock_generate.assert_called_once_with(
            prompt="Test content",
            ref_images=[provider.reference_image],
            aspect_ratio="16:9",
            resolution="1792x1024"
        )

    def test_generate_image_download_failure(self, provider):
        """Test image generation with download failure."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.data = [Mock(url="http://example.com/image.png")]
        provider.client.images.generate.return_value = mock_response

        # Mock requests failure
        with patch('requests.get', side_effect=requests.RequestException("Download failed")):
            with pytest.raises(Exception, match="Error generating image with OpenAI"):
                provider.generate_image("Test prompt")