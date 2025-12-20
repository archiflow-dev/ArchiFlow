"""
Unit tests for Google Image Provider.

These tests verify the initialization, configuration, and basic functionality
of the Google Image Provider without making actual API calls.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Import the classes under test
from src.agent_framework.llm.google_image_provider import GoogleImageProvider, GOOGLE_AVAILABLE
from src.agent_framework.llm.image_provider_base import ImageProvider
try:
    from google.genai import types
except ImportError:
    types = None


class TestGoogleImageProvider:
    """Test cases for GoogleImageProvider class."""

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key_123")

            assert provider.api_key == "test_key_123"
            assert provider.model_name == "gemini-3-pro-image-preview"
            assert provider.reference_image is None
            assert provider.provider_name == "google"
            assert provider.api_base is None
            assert isinstance(provider, ImageProvider)
            mock_genai.Client.assert_called_once_with(api_key="test_key_123")

    @pytest.mark.skipif(not GOOGLE_AVAILABLE or not types, reason="google-genai or types not available")
    def test_init_with_custom_parameters(self):
        """Test initialization with custom API base and model."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(
                api_key="test_key_456",
                api_base="https://custom.googleapis.com",
                model="custom-model-v1"
            )

            assert provider.api_key == "test_key_456"
            assert provider.model_name == "custom-model-v1"
            assert provider.api_base == "https://custom.googleapis.com"
            mock_genai.Client.assert_called_once_with(
                api_key="test_key_456",
                http_options=types.HttpOptions(base_url="https://custom.googleapis.com")
            )

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_init_with_env_var(self):
        """Test initialization using environment variable."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'env_key_456'}):
            with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client

                provider = GoogleImageProvider()

                assert provider.api_key == "env_key_456"
                assert provider.model_name == "gemini-3-pro-image-preview"  # default
                assert provider.api_base is None  # default
                mock_genai.Client.assert_called_once_with(api_key="env_key_456")

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-generativeai not installed")
    def test_init_no_api_key_raises_error(self):
        """Test that initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):  # Remove GOOGLE_API_KEY
            with pytest.raises(ValueError, match="Google API key is required"):
                GoogleImageProvider(api_key=None)

    def test_init_no_google_package_raises_error(self):
        """Test that initialization fails when google-generativeai is not installed."""
        with patch('src.agent_framework.llm.google_image_provider.GOOGLE_AVAILABLE', False):
            with pytest.raises(ImportError, match="google.genai package is required"):
                GoogleImageProvider(api_key="test_key")

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_init_connection_failure(self):
        """Test handling of connection failure during initialization."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            mock_genai.Client.side_effect = Exception("Connection failed")

            with pytest.raises(RuntimeError, match="Failed to connect to Google API"):
                GoogleImageProvider(api_key="test_key")

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_repr(self):
        """Test string representation of the provider."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key")
            repr_str = repr(provider)

            assert "GoogleImageProvider" in repr_str
            assert "gemini-3-pro-image-preview" in repr_str
            assert "has_reference=False" in repr_str

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_validate_connection_success(self):
        """Test successful connection validation."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            # Mock client and models
            mock_client = MagicMock()
            mock_model = MagicMock()
            mock_model.name = "models/gemini-3-pro-image-preview"
            mock_client.models.list.return_value = [mock_model]
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key")
            result = provider.validate_connection()

            assert result is True
            mock_client.models.list.assert_called_once()

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_validate_connection_no_gemini_models(self):
        """Test connection validation when no Gemini image models are found."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            # Mock client and models
            mock_client = MagicMock()
            mock_model = MagicMock()
            mock_model.name = "models/text-bison-001"
            mock_client.models.list.return_value = [mock_model]
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key")
            result = provider.validate_connection()

            assert result is False

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_validate_connection_api_error(self):
        """Test connection validation when API call fails."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            # Mock client with error
            mock_client = MagicMock()
            mock_client.models.list.side_effect = Exception("API error")
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key")

            with pytest.raises(RuntimeError, match="Cannot connect to Google API"):
                provider.validate_connection()

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_get_supported_sizes(self):
        """Test getting supported image sizes."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key")
            sizes = provider.get_supported_sizes()

            assert isinstance(sizes, list)
            assert (1024, 1024) in sizes
            assert (1920, 1080) in sizes
            assert (1080, 1920) in sizes

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_get_supported_styles(self):
        """Test getting supported styles."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key")
            styles = provider.get_supported_styles()

            assert isinstance(styles, list)
            assert "natural" in styles
            assert "presentation" in styles
            assert "photorealistic" in styles

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_generate_first_slide(self):
        """Test first slide generation method."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key")

            # Mock the generate_image method
            with patch.object(provider, 'generate_image') as mock_generate:
                mock_image = MagicMock()
                mock_generate.return_value = mock_image

                result = provider.generate_first_slide("Solar panels on roof")

                mock_generate.assert_called_once()
                # All arguments are keyword arguments
                kwargs = mock_generate.call_args.kwargs
                assert "Professional presentation slide image" in kwargs['prompt']
                assert kwargs.get('aspect_ratio') == "16:9"
                assert kwargs.get('resolution') == "2K"
                assert provider.reference_image == mock_image
                assert result == mock_image

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_generate_subsequent_slide(self):
        """Test subsequent slide generation with reference."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key")

            # Set up a reference image
            provider.reference_image = MagicMock()

            # Mock the generate_image method
            with patch.object(provider, 'generate_image') as mock_generate:
                mock_image = MagicMock()
                mock_generate.return_value = mock_image

                result = provider.generate_subsequent_slide(
                    "Wind turbines",
                    slide_number=2
                )

                mock_generate.assert_called_once()
                # All arguments are keyword arguments
                kwargs = mock_generate.call_args.kwargs
                assert "Professional presentation slide #2" in kwargs['prompt']
                assert kwargs.get('aspect_ratio') == "16:9"
                assert kwargs.get('resolution') == "2K"
                assert kwargs.get('ref_images') == [provider.reference_image]
                assert result == mock_image

    @pytest.mark.skipif(not GOOGLE_AVAILABLE, reason="google-genai not installed")
    def test_generate_subsequent_slide_no_reference(self):
        """Test subsequent slide generation without reference falls back to first slide."""
        with patch('src.agent_framework.llm.google_image_provider.genai') as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            provider = GoogleImageProvider(api_key="test_key")

            # Mock generate_first_slide method
            with patch.object(provider, 'generate_first_slide') as mock_first:
                mock_image = MagicMock()
                mock_first.return_value = mock_image

                result = provider.generate_subsequent_slide(
                    "Wind turbines",
                    slide_number=2
                )

                mock_first.assert_called_once_with(
                    "Wind turbines",
                    aspect_ratio="16:9",
                    resolution="2K"
                )
                assert result == mock_image


if __name__ == "__main__":
    # Run tests when script is executed directly
    pytest.main([__file__, "-v"])