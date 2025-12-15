"""
Unit tests for LLMPromptImprover.

Tests Phase 2: LLM-based Prompt Auto-Improvement
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from agent_cli.prompt_improvement import (
    LLMPromptImprover,
    ImprovedPrompt,
    PromptImprovementResult,
    improve_prompt_llm
)


class TestLLMPromptImprover:
    """Test suite for LLMPromptImprover class."""

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_initialization_success(self, mock_provider):
        """Test successful initialization with valid API key."""
        improver = LLMPromptImprover()
        assert improver.num_improvements == 3
        assert improver.llm is not None

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_initialization_with_custom_num_improvements(self, mock_provider):
        """Test initialization with custom number of improvements."""
        improver = LLMPromptImprover(num_improvements=5)
        assert improver.num_improvements == 5

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_empty_prompt(self, mock_provider):
        """Test that empty prompts return empty result."""
        improver = LLMPromptImprover()
        result = improver.improve("")

        assert result.original_prompt == ""
        assert len(result.improvements) == 0
        assert result.detected_intent == "Unknown"
        assert result.detected_domain == "Unknown"

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_llm_response_parsing(self, mock_provider):
        """Test parsing of LLM JSON response."""
        # Mock LLM response
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "improvements": [
                {
                    "prompt": "Review src/auth/middleware.py for SQL injection vulnerabilities",
                    "explanation": "Added specific file path and security focus",
                    "confidence": 95
                },
                {
                    "prompt": "Analyze authentication logic in src/auth/ for security issues",
                    "explanation": "Specified directory and objective",
                    "confidence": 85
                }
            ],
            "detected_intent": "Code review for security",
            "detected_domain": "authentication"
        }
        '''
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        improver = LLMPromptImprover()
        result = improver.improve("review auth code")

        assert result.original_prompt == "review auth code"
        assert len(result.improvements) == 2
        assert result.improvements[0].prompt == "Review src/auth/middleware.py for SQL injection vulnerabilities"
        assert result.improvements[0].confidence == 95
        assert result.detected_intent == "Code review for security"
        assert result.detected_domain == "authentication"

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_best_improvement_property(self, mock_provider):
        """Test that best_improvement returns highest confidence improvement."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "improvements": [
                {
                    "prompt": "Improvement 1",
                    "explanation": "First",
                    "confidence": 75
                },
                {
                    "prompt": "Improvement 2",
                    "explanation": "Second",
                    "confidence": 95
                },
                {
                    "prompt": "Improvement 3",
                    "explanation": "Third",
                    "confidence": 85
                }
            ],
            "detected_intent": "Test",
            "detected_domain": "Test"
        }
        '''
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        improver = LLMPromptImprover()
        result = improver.improve("test")

        assert result.best_improvement.prompt == "Improvement 2"
        assert result.best_improvement.confidence == 95

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_best_improvement_empty_list(self, mock_provider):
        """Test best_improvement with no improvements."""
        improver = LLMPromptImprover()
        result = PromptImprovementResult(
            original_prompt="test",
            improvements=[],
            detected_intent="Unknown",
            detected_domain="Unknown"
        )

        best = result.best_improvement
        assert best.prompt == "test"
        assert best.confidence == 0

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_llm_called_with_correct_parameters(self, mock_provider):
        """Test that LLM is called with correct parameters."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '{"improvements": [], "detected_intent": "test", "detected_domain": "test"}'
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        improver = LLMPromptImprover()
        improver.improve("test prompt")

        # Verify LLM was called
        mock_llm_instance.generate.assert_called_once()

        # Verify parameters
        call_args = mock_llm_instance.generate.call_args
        assert call_args.kwargs['temperature'] == 0.7  # Creative for variations
        assert call_args.kwargs['max_tokens'] == 1000
        messages = call_args.kwargs['messages']
        assert len(messages) == 1
        assert messages[0]['role'] == 'user'
        assert 'test prompt' in messages[0]['content']

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_json_parse_error_handling(self, mock_provider):
        """Test fallback when JSON parsing fails."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = "This is not JSON but here's a suggestion: Review the authentication module in src/auth for security vulnerabilities"
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        improver = LLMPromptImprover()
        result = improver.improve("review auth")

        # Should extract improvement from free-form text
        assert result.original_prompt == "review auth"
        assert result.detected_intent == "Unknown (parse error)"

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_api_error_handling(self, mock_provider):
        """Test error handling when API call fails."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate.side_effect = Exception("API error")
        mock_provider.return_value = mock_llm_instance

        improver = LLMPromptImprover()
        result = improver.improve("test")

        # Should return empty result on error
        assert result.original_prompt == "test"
        assert len(result.improvements) == 0
        assert "error" in result.detected_intent.lower()

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_limits_number_of_improvements(self, mock_provider):
        """Test that number of improvements is limited."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        # Return 5 improvements but only 3 should be used
        mock_response.content = '''
        {
            "improvements": [
                {"prompt": "1", "explanation": "1", "confidence": 90},
                {"prompt": "2", "explanation": "2", "confidence": 85},
                {"prompt": "3", "explanation": "3", "confidence": 80},
                {"prompt": "4", "explanation": "4", "confidence": 75},
                {"prompt": "5", "explanation": "5", "confidence": 70}
            ],
            "detected_intent": "test",
            "detected_domain": "test"
        }
        '''
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        improver = LLMPromptImprover(num_improvements=3)
        result = improver.improve("test")

        assert len(result.improvements) == 3
        assert result.improvements[0].prompt == "1"
        assert result.improvements[2].prompt == "3"

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_improved_prompt_str_method(self, mock_provider):
        """Test ImprovedPrompt __str__ method."""
        imp = ImprovedPrompt(
            prompt="Review src/auth.py",
            explanation="Added file path",
            confidence=90
        )

        assert str(imp) == "Review src/auth.py"

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_real_world_vague_prompts(self, mock_provider):
        """Test with real-world vague prompts."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "improvements": [
                {
                    "prompt": "Debug the authentication timeout issue in src/auth/session.py where users are logged out after 5 minutes",
                    "explanation": "Made it specific with file, issue, and context",
                    "confidence": 90
                }
            ],
            "detected_intent": "Bug fixing",
            "detected_domain": "authentication"
        }
        '''
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        improver = LLMPromptImprover()

        # Test various vague prompts
        vague_prompts = [
            "fix the bug",
            "help me",
            "review my code",
            "make it better"
        ]

        for prompt in vague_prompts:
            result = improver.improve(prompt)
            assert isinstance(result, PromptImprovementResult)
            assert result.original_prompt == prompt

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_custom_model_selection(self, mock_provider):
        """Test that custom model can be specified."""
        improver = LLMPromptImprover(model="claude-3-haiku-20240307")
        assert improver.model == "claude-3-haiku-20240307"

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_fallback_extraction_with_prefix(self, mock_provider):
        """Test fallback extraction with common prefixes."""
        improver = LLMPromptImprover()

        # Test various prefixes
        test_cases = [
            ("IMPROVED: Review src/auth.py for security", "Review src/auth.py for security"),
            ("Suggestion: Implement login in src/auth/login.py", "Implement login in src/auth/login.py"),
            ("Better: Fix bug in src/api/users.py line 45", "Fix bug in src/api/users.py line 45"),
            ("- Refactor database queries in src/db/", "Refactor database queries in src/db/"),
            ("* Test authentication flow in tests/auth/", "Test authentication flow in tests/auth/")
        ]

        for llm_text, expected_prompt in test_cases:
            result = improver._extract_fallback_improvement(llm_text, "test")
            if result:
                assert result.prompt == expected_prompt


class TestPromptImprovementConvenienceFunction:
    """Test the convenience function."""

    @patch('agent_cli.prompt_improvement.llm_prompt_improver.AnthropicProvider')
    def test_improve_prompt_llm_function(self, mock_provider):
        """Test the improve_prompt_llm convenience function."""
        mock_llm_instance = MagicMock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "improvements": [
                {"prompt": "Test", "explanation": "Test", "confidence": 80}
            ],
            "detected_intent": "test",
            "detected_domain": "test"
        }
        '''
        mock_llm_instance.generate.return_value = mock_response
        mock_provider.return_value = mock_llm_instance

        result = improve_prompt_llm("test prompt")

        assert isinstance(result, PromptImprovementResult)
        assert result.original_prompt == "test prompt"
        assert len(result.improvements) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
