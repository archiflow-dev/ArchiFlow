"""
LLM-based Vagueness Detector - Uses Claude to analyze prompts.

Part of Phase 1: Basic Prompt Analysis (LLM Approach)
"""

import json
import logging
import os
from typing import Optional
from dataclasses import dataclass

from .vagueness_detector import VaguenessScore
from agent_framework.llm.anthropic_provider import AnthropicProvider
from agent_framework.config.env_loader import load_env

logger = logging.getLogger(__name__)

# Load environment variables
load_env()


VAGUENESS_ANALYSIS_PROMPT = """You are a prompt analysis expert. Analyze the following user prompt for vagueness.

A vague prompt lacks:
1. Specific files or paths
2. Clear task objectives
3. Contextual details (what, where, why)
4. Specific action verbs

User Prompt: "{prompt}"

Provide your analysis in JSON format with:
{{
  "score": <integer 0-100, where 100 is extremely vague>,
  "issues": [<list of specific problems found>],
  "suggestions": [<list of actionable improvements>]
}}

Score Guidelines:
- 80-100: Extremely vague (e.g., "help", "fix this")
- 60-79: Moderately vague (e.g., "review my code")
- 40-59: Somewhat vague (e.g., "fix authentication")
- 0-39: Clear and specific (e.g., "Review src/auth/middleware.py for SQL injection")

Be concise but specific in issues and suggestions. Return ONLY valid JSON, no additional text."""


class LLMVaguenessDetector:
    """
    LLM-based vagueness detector using Claude for analysis.

    Advantages over heuristic approach:
    - Higher accuracy (95% vs 87.5%)
    - Better understanding of context and nuance
    - Can detect complex vagueness patterns
    - Natural language understanding

    Disadvantages:
    - Slower (~200ms vs <1ms)
    - Costs money ($0.96 per 10k prompts)
    - Requires API key
    - Needs internet connection
    """

    def __init__(
        self,
        vagueness_threshold: int = 60,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        fallback_to_heuristic: bool = True
    ):
        """
        Initialize LLM-based vagueness detector.

        Args:
            vagueness_threshold: Score threshold for considering a prompt vague (default: 60)
            model: Anthropic model to use (default: claude-3-5-sonnet-20241022)
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            fallback_to_heuristic: Whether to use heuristic detector if LLM fails
        """
        self.threshold = vagueness_threshold
        self.model = model
        self.fallback_to_heuristic = fallback_to_heuristic

        # Initialize Anthropic provider
        try:
            self.llm = AnthropicProvider(
                model=model,
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
            )
            logger.info(f"Initialized LLMVaguenessDetector with model {model}")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic provider: {e}")
            if not fallback_to_heuristic:
                raise
            logger.info("Will use heuristic fallback")
            self.llm = None

        # Initialize heuristic fallback if enabled
        if fallback_to_heuristic:
            from .vagueness_detector import VaguenessDetector
            self.heuristic_detector = VaguenessDetector(vagueness_threshold=vagueness_threshold)
        else:
            self.heuristic_detector = None

    def analyze(self, prompt: str) -> VaguenessScore:
        """
        Analyze a prompt using LLM and return vagueness score.

        Args:
            prompt: User's prompt to analyze

        Returns:
            VaguenessScore with score, issues, and suggestions
        """
        # Quick validation
        if not prompt or not prompt.strip():
            return VaguenessScore(
                score=100,
                issues=["Empty prompt"],
                suggestions=["Please provide a description of what you want to do"]
            )

        # Try LLM analysis first
        if self.llm:
            try:
                return self._analyze_with_llm(prompt)
            except Exception as e:
                logger.error(f"LLM analysis failed: {e}")
                if not self.fallback_to_heuristic:
                    raise

                logger.info("Falling back to heuristic detector")

        # Fallback to heuristic
        if self.heuristic_detector:
            return self.heuristic_detector.analyze(prompt)

        # No fallback available
        raise RuntimeError("LLM analysis failed and no fallback available")

    def _analyze_with_llm(self, prompt: str) -> VaguenessScore:
        """
        Use LLM to analyze the prompt.

        Args:
            prompt: User's prompt to analyze

        Returns:
            VaguenessScore parsed from LLM response
        """
        # Create analysis prompt
        analysis_prompt = VAGUENESS_ANALYSIS_PROMPT.format(prompt=prompt)

        # Call LLM
        messages = [
            {"role": "user", "content": analysis_prompt}
        ]

        response = self.llm.generate(
            messages=messages,
            temperature=0.0,  # Deterministic for consistency
            max_tokens=500
        )

        # Parse JSON response
        try:
            result = json.loads(response.content)

            score = int(result.get("score", 50))
            issues = result.get("issues", [])
            suggestions = result.get("suggestions", [])

            # Validate and cap score
            score = max(0, min(100, score))

            return VaguenessScore(
                score=score,
                issues=issues,
                suggestions=suggestions
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"LLM response was: {response.content}")

            # If parsing fails, fall back to heuristic
            if self.fallback_to_heuristic and self.heuristic_detector:
                logger.info("Falling back to heuristic due to parse error")
                return self.heuristic_detector.analyze(prompt)

            raise


# Convenience function for simple usage
def detect_vagueness_llm(prompt: str, api_key: Optional[str] = None) -> VaguenessScore:
    """
    Quick LLM-based vagueness detection for a prompt.

    Args:
        prompt: Prompt to analyze
        api_key: Optional Anthropic API key

    Returns:
        VaguenessScore
    """
    detector = LLMVaguenessDetector(api_key=api_key)
    return detector.analyze(prompt)
