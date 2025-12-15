"""
Unit tests for LLMVaguenessDetector.

Tests Phase 1: LLM-based Prompt Analysis
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from agent_cli.prompt_improvement import LLMVaguenessDetector, VaguenessScore


class TestLLMVaguenessDetector:
    """Test suite for LLMVaguenessDetector class."""

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_initialization_success(self, mock_provider):
        """Test successful initialization with valid API key."""
        detector = LLMVaguenessDetector()
        assert detector.threshold == 60
        assert detector.fallback_to_heuristic is True
        assert detector.llm is not None

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_initialization_with_custom_threshold(self, mock_provider):
        """Test initialization with custom threshold."""
        detector = LLMVaguenessDetector(vagueness_threshold=70)
        assert detector.threshold == 70

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_empty_prompt(self, mock_provider):
        """Test that empty prompts get maximum vagueness score."""
        detector = LLMVaguenessDetector()
        result = detector.analyze("")
        assert result.score == 100
        assert result.is_vague
        assert "Empty prompt" in result.issues

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_llm_response_parsing(self, mock_provider):
        """Test parsing of LLM JSON response."""
        # Mock LLM response
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "score": 75,
            "issues": ["No specific files mentioned", "Vague verb 'help'"],
            "suggestions": ["Specify which files to review", "Use specific action verbs"]
        }
        '''
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        detector = LLMVaguenessDetector()
        result = detector.analyze("help me")

        assert result.score == 75
        assert len(result.issues) == 2
        assert len(result.suggestions) == 2
        assert result.is_vague

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_llm_response_score_capping(self, mock_provider):
        """Test that scores are capped at 100."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '{"score": 150, "issues": [], "suggestions": []}'
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        detector = LLMVaguenessDetector()
        result = detector.analyze("test")

        assert result.score == 100  # Capped at 100

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_llm_response_negative_score(self, mock_provider):
        """Test that negative scores are set to 0."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '{"score": -10, "issues": [], "suggestions": []}'
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        detector = LLMVaguenessDetector()
        result = detector.analyze("test")

        assert result.score == 0  # Capped at 0

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_fallback_to_heuristic_on_llm_failure(self, mock_provider):
        """Test fallback to heuristic when LLM fails."""
        # Mock LLM to raise exception
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate.side_effect = Exception("API error")
        mock_provider.return_value = mock_llm_instance

        detector = LLMVaguenessDetector(fallback_to_heuristic=True)
        result = detector.analyze("help")

        # Should fall back to heuristic detector
        assert isinstance(result, VaguenessScore)
        assert result.score >= 0  # Valid score from heuristic

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_no_fallback_raises_on_llm_failure(self, mock_provider):
        """Test that exception is raised when fallback is disabled."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate.side_effect = Exception("API error")
        mock_provider.return_value = mock_llm_instance

        detector = LLMVaguenessDetector(fallback_to_heuristic=False)

        with pytest.raises(Exception):
            detector.analyze("help")

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_fallback_on_json_parse_error(self, mock_provider):
        """Test fallback to heuristic when JSON parsing fails."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = "This is not JSON"
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        detector = LLMVaguenessDetector(fallback_to_heuristic=True)
        result = detector.analyze("help")

        # Should fall back to heuristic
        assert isinstance(result, VaguenessScore)
        assert result.score >= 0

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_clear_prompt_low_score(self, mock_provider):
        """Test that clear prompts get low vagueness scores from LLM."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "score": 15,
            "issues": [],
            "suggestions": []
        }
        '''
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        detector = LLMVaguenessDetector()
        result = detector.analyze("Review src/auth/middleware.py for SQL injection")

        assert result.score == 15
        assert not result.is_vague
        assert result.severity == "low"

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_vague_prompt_high_score(self, mock_provider):
        """Test that vague prompts get high vagueness scores from LLM."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "score": 95,
            "issues": ["Extremely short", "No files", "Vague verb"],
            "suggestions": ["Be more specific", "Include file paths"]
        }
        '''
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        detector = LLMVaguenessDetector()
        result = detector.analyze("help")

        assert result.score == 95
        assert result.is_vague
        assert result.severity == "high"
        assert len(result.issues) == 3
        assert len(result.suggestions) == 2

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_llm_called_with_correct_parameters(self, mock_provider):
        """Test that LLM is called with correct parameters."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '{"score": 50, "issues": [], "suggestions": []}'
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        detector = LLMVaguenessDetector()
        detector.analyze("test prompt")

        # Verify LLM was called
        mock_llm_instance.generate.assert_called_once()

        # Verify parameters
        call_args = mock_llm_instance.generate.call_args
        assert call_args.kwargs['temperature'] == 0.0  # Deterministic
        assert call_args.kwargs['max_tokens'] == 500
        messages = call_args.kwargs['messages']
        assert len(messages) == 1  # One message
        assert messages[0]['role'] == 'user'
        assert 'test prompt' in messages[0]['content']


class TestLLMVaguenessDetectorInitialization:
    """Test initialization edge cases."""

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_initialization_without_anthropic_installed(self, mock_provider):
        """Test initialization when anthropic package is not installed."""
        # Mock ImportError
        mock_provider.side_effect = ImportError("No module named 'anthropic'")

        # Should fall back to heuristic silently
        detector = LLMVaguenessDetector(fallback_to_heuristic=True)
        assert detector.heuristic_detector is not None
        assert detector.llm is None

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_custom_model_selection(self, mock_provider):
        """Test that custom model can be specified."""
        detector = LLMVaguenessDetector(model="claude-3-opus-20240229")
        assert detector.model == "claude-3-opus-20240229"


class TestLLMVaguenessConvenienceFunction:
    """Test the convenience function."""

    @patch('agent_cli.prompt_improvement.llm_vagueness_detector.AnthropicProvider')
    def test_detect_vagueness_llm_function(self, mock_provider):
        """Test the detect_vagueness_llm convenience function."""
        from agent_cli.prompt_improvement import detect_vagueness_llm

        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '{"score": 60, "issues": ["test"], "suggestions": ["test"]}'
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        result = detect_vagueness_llm("test prompt")

        assert isinstance(result, VaguenessScore)
        assert result.score == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
