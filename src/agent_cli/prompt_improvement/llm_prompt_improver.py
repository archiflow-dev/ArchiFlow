"""
LLM-based Prompt Improver - Uses Claude to auto-improve vague prompts.

Part of Phase 2: Simple Auto-Improvement (LLM Approach)
"""

import json
import logging
import os
from typing import Optional, List
from dataclasses import dataclass

from agent_framework.llm.anthropic_provider import AnthropicProvider
from agent_framework.config.env_loader import load_env

logger = logging.getLogger(__name__)

# Load environment variables
load_env()


PROMPT_IMPROVEMENT_SYSTEM = """You are an expert at improving vague software development prompts.

Your task is to transform vague, unclear prompts into specific, actionable requests.

A good prompt should include:
1. Specific files, directories, or modules
2. Clear action verbs (review, implement, refactor, fix, etc.)
3. Specific objectives or goals
4. Context about what, where, and why
5. Success criteria or expected outcomes

Examples of improvements:

VAGUE: "help me"
IMPROVED: "Review the authentication logic in src/auth/middleware.py and suggest improvements for security"

VAGUE: "fix the bug"
IMPROVED: "Debug the login timeout issue in src/auth/session.py line 45 where users are logged out after 5 minutes instead of 30 minutes"

VAGUE: "review my code"
IMPROVED: "Review src/api/users.py for SQL injection vulnerabilities and suggest parameterized query improvements"

VAGUE: "make it better"
IMPROVED: "Refactor the database query logic in src/db/queries.py to use async/await for improved performance under high load"

IMPORTANT:
- Preserve the user's original intent
- Don't add features they didn't ask for
- Stay focused on their domain (if unclear, assume web development)
- Be specific but concise
- Use real-looking file paths (src/, tests/, etc.)"""


PROMPT_IMPROVEMENT_USER_TEMPLATE = """Original prompt: "{original_prompt}"

Generate 3 improved versions of this prompt, ranked from most to least recommended.

Return your response as valid JSON only:
{{
  "improvements": [
    {{
      "prompt": "<improved prompt text>",
      "explanation": "<brief explanation of what was improved>",
      "confidence": <0-100, how confident you are this matches user intent>
    }}
  ],
  "detected_intent": "<what you think the user wants to do>",
  "detected_domain": "<the technical domain, e.g., authentication, database, API, UI>"
}}

Focus on being specific and actionable while preserving the user's original intent."""


@dataclass
class ImprovedPrompt:
    """Represents an improved version of a prompt."""

    prompt: str
    explanation: str
    confidence: int  # 0-100

    def __str__(self) -> str:
        return self.prompt


@dataclass
class PromptImprovementResult:
    """Result of prompt improvement analysis."""

    original_prompt: str
    improvements: List[ImprovedPrompt]
    detected_intent: str
    detected_domain: str

    @property
    def best_improvement(self) -> ImprovedPrompt:
        """Get the highest-confidence improvement."""
        if not self.improvements:
            return ImprovedPrompt(
                prompt=self.original_prompt,
                explanation="No improvements available",
                confidence=0
            )
        return max(self.improvements, key=lambda x: x.confidence)


class LLMPromptImprover:
    """
    LLM-based prompt improver using Claude.

    Takes vague prompts and generates specific, actionable alternatives.
    """

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        num_improvements: int = 3
    ):
        """
        Initialize LLM-based prompt improver.

        Args:
            model: Anthropic model to use (default: claude-3-5-sonnet-20241022)
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            num_improvements: Number of improved prompts to generate (default: 3)
        """
        self.model = model
        self.num_improvements = num_improvements

        # Initialize Anthropic provider
        try:
            self.llm = AnthropicProvider(
                model=model,
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
            )
            logger.info(f"Initialized LLMPromptImprover with model {model}")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic provider: {e}")
            raise

    def improve(self, original_prompt: str) -> PromptImprovementResult:
        """
        Generate improved versions of a prompt.

        Args:
            original_prompt: The original vague prompt

        Returns:
            PromptImprovementResult with improved versions
        """
        # Quick validation
        if not original_prompt or not original_prompt.strip():
            return PromptImprovementResult(
                original_prompt=original_prompt,
                improvements=[],
                detected_intent="Unknown",
                detected_domain="Unknown"
            )

        # Call LLM to improve prompt
        try:
            result = self._improve_with_llm(original_prompt)
            return result
        except Exception as e:
            logger.error(f"Prompt improvement failed: {e}")
            # Return empty result on failure
            return PromptImprovementResult(
                original_prompt=original_prompt,
                improvements=[],
                detected_intent="Unknown (error occurred)",
                detected_domain="Unknown"
            )

    def _improve_with_llm(self, original_prompt: str) -> PromptImprovementResult:
        """
        Use LLM to improve the prompt.

        Args:
            original_prompt: The original prompt

        Returns:
            PromptImprovementResult with improved versions
        """
        # Create improvement request
        user_message = PROMPT_IMPROVEMENT_USER_TEMPLATE.format(
            original_prompt=original_prompt
        )

        # Call LLM
        messages = [
            {"role": "user", "content": PROMPT_IMPROVEMENT_SYSTEM + "\n\n" + user_message}
        ]

        response = self.llm.generate(
            messages=messages,
            temperature=0.7,  # Some creativity for variations
            max_tokens=1000
        )

        # Parse JSON response
        try:
            result = json.loads(response.content)

            improvements = []
            for imp in result.get("improvements", [])[:self.num_improvements]:
                improvements.append(ImprovedPrompt(
                    prompt=imp.get("prompt", ""),
                    explanation=imp.get("explanation", ""),
                    confidence=int(imp.get("confidence", 50))
                ))

            return PromptImprovementResult(
                original_prompt=original_prompt,
                improvements=improvements,
                detected_intent=result.get("detected_intent", "Unknown"),
                detected_domain=result.get("detected_domain", "Unknown")
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"LLM response was: {response.content}")

            # Try to extract at least one improvement from free-form text
            fallback_improvement = self._extract_fallback_improvement(
                response.content,
                original_prompt
            )

            return PromptImprovementResult(
                original_prompt=original_prompt,
                improvements=[fallback_improvement] if fallback_improvement else [],
                detected_intent="Unknown (parse error)",
                detected_domain="Unknown"
            )

    def _extract_fallback_improvement(
        self,
        llm_response: str,
        original_prompt: str
    ) -> Optional[ImprovedPrompt]:
        """
        Try to extract an improvement from free-form LLM response.

        Args:
            llm_response: The LLM's response text
            original_prompt: The original prompt

        Returns:
            ImprovedPrompt if extraction successful, None otherwise
        """
        # Simple heuristic: look for lines that seem like improved prompts
        lines = llm_response.split('\n')

        for line in lines:
            line = line.strip()
            # Skip empty lines and JSON-like lines
            if not line or line.startswith('{') or line.startswith('['):
                continue

            # Look for lines that are longer and more specific than original
            if len(line) > len(original_prompt) * 1.5:
                # Clean up common prefixes
                for prefix in ['IMPROVED:', 'Suggestion:', 'Better:', '-', '*']:
                    if line.startswith(prefix):
                        line = line[len(prefix):].strip()

                return ImprovedPrompt(
                    prompt=line,
                    explanation="Extracted from free-form response",
                    confidence=50
                )

        return None


# Convenience function for simple usage
def improve_prompt_llm(
    prompt: str,
    api_key: Optional[str] = None
) -> PromptImprovementResult:
    """
    Quick LLM-based prompt improvement.

    Args:
        prompt: Prompt to improve
        api_key: Optional Anthropic API key

    Returns:
        PromptImprovementResult
    """
    improver = LLMPromptImprover(api_key=api_key)
    return improver.improve(prompt)
