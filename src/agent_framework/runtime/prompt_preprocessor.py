"""
Prompt Preprocessor for Auto-Refinement.

This module provides a pre-processing hook that refines user prompts
before they reach the agent, ensuring zero contamination of the agent's
system prompt and conversation history.

Architecture (Option 3 - Pre-Processing Hook):
    User sends message
        ↓
    PromptPreprocessor.process() runs (if AUTO_REFINE_PROMPTS=true)
        ↓
    PromptRefinerTool analyzes quality
        ↓
    If quality < threshold: Replace with refined version
    If quality >= threshold: Pass through unchanged
        ↓
    Agent receives clean prompt (no refinement meta-conversation)
"""
import asyncio
import json
import logging
import os
from dataclasses import replace
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from ..messages.types import UserMessage
from ..llm.provider import LLMProvider
from ..tools.prompt_refiner_tool import PromptRefinerTool

if TYPE_CHECKING:
    from ..config.hierarchy import ConfigSnapshot

logger = logging.getLogger(__name__)


class PromptPreprocessor:
    """
    Pre-processor for automatic prompt refinement.

    This class provides a clean separation between prompt refinement
    and task execution by running refinement BEFORE the agent sees
    the message.

    Benefits:
    - Zero contamination of agent's system prompt
    - Zero contamination of agent's memory/history
    - Single hook point for all UserMessages
    - Easy to enable/disable via environment variable

    Usage:
        preprocessor = PromptPreprocessor(llm=agent.llm)
        processed_message = await preprocessor.process(user_message)
        # Then pass to agent.step()
    """

    # Default configuration
    DEFAULT_THRESHOLD = 8.0
    DEFAULT_MIN_LENGTH = 10
    DEFAULT_MAX_ITERATIONS = 1  # Single pass for Option 3

    def __init__(
        self,
        llm: LLMProvider,
        threshold: Optional[float] = None,
        min_length: Optional[int] = None,
        enabled: Optional[bool] = None,
        config_snapshot: Optional['ConfigSnapshot'] = None,
        enabled_callback: Optional[callable] = None,
    ):
        """
        Initialize the prompt preprocessor.

        Args:
            llm: LLM provider for PromptRefinerTool
            threshold: Quality threshold (0-10). Prompts >= threshold pass through.
                      If not provided, reads from ConfigHierarchy or AUTO_REFINE_THRESHOLD
                      env var or defaults to 9.0.
            min_length: Minimum message length to consider for refinement.
                       Shorter messages are always passed through.
                       If not provided, reads from ConfigHierarchy or AUTO_REFINE_MIN_LENGTH
                       env var or defaults to 10.
            enabled: Whether refinement is enabled. If None, checks ConfigHierarchy or
                     AUTO_REFINE_PROMPTS env variable (defaults to False).
                     If enabled_callback is provided, this is ignored.
            config_snapshot: Optional ConfigSnapshot from ConfigHierarchy. If provided,
                            settings are read from the merged configuration hierarchy.
            enabled_callback: Optional callable that returns bool (current enabled state).
                             If provided, this is called on each process() to check if
                             refinement is enabled (allows runtime toggling via session config).
        """
        self.llm = llm
        self._config_snapshot = config_snapshot
        self._enabled_callback = enabled_callback

        # Configuration precedence:
        # 1. Direct parameter (highest)
        # 2. ConfigHierarchy (if key exists)
        # 3. Environment variable (backward compatibility)
        # 4. Default (lowest)

        # Helper to get value from snapshot with proper fallback
        def get_from_snapshot_or_fallback(key: str, env_var: str, default, converter=None):
            """Get value from config_snapshot or fall back to env var or default."""
            if config_snapshot is not None:
                # Check if the key exists in the snapshot
                auto_refine = config_snapshot.settings.get("autoRefinement", {})
                if key in auto_refine:
                    value = auto_refine[key]
                    return converter(value) if converter else value
                # Key doesn't exist in snapshot, fall through to env var

            # Fall back to environment variable
            env_value = os.getenv(env_var)
            if env_value is not None:
                return converter(env_value) if converter else env_value

            # Fall back to default
            return default

        # Get threshold
        if threshold is not None:
            self.threshold = threshold
        else:
            self.threshold = get_from_snapshot_or_fallback(
                "threshold",
                "AUTO_REFINE_THRESHOLD",
                self.DEFAULT_THRESHOLD,
                float
            )

        # Get min_length
        if min_length is not None:
            self.min_length = min_length
        else:
            self.min_length = get_from_snapshot_or_fallback(
                "minLength",
                "AUTO_REFINE_MIN_LENGTH",
                self.DEFAULT_MIN_LENGTH,
                int
            )

        # Get enabled flag (if not using callback)
        if enabled_callback is None:
            if enabled is not None:
                self._static_enabled = enabled
            else:
                # For enabled, we need special handling since env var is "true"/"false" string
                if config_snapshot is not None:
                    auto_refine = config_snapshot.settings.get("autoRefinement", {})
                    if "enabled" in auto_refine:
                        self._static_enabled = auto_refine["enabled"]
                    else:
                        # Fall back to env var
                        env_val = os.getenv("AUTO_REFINE_PROMPTS", "false")
                        self._static_enabled = env_val.lower() == "true"
                else:
                    # No config snapshot, use env var
                    env_val = os.getenv("AUTO_REFINE_PROMPTS", "false")
                    self._static_enabled = env_val.lower() == "true"
        else:
            # Using callback, enabled state is dynamic
            self._static_enabled = None

        # Create refiner tool (lazy initialization on first use)
        self._refiner: Optional[PromptRefinerTool] = None

        # Log initialization
        initial_enabled = self.is_enabled
        if initial_enabled:
            logger.warning(
                "⚠️  AUTO-REFINEMENT IS ENABLED ⚠️  "
                "This DOUBLES cost and latency of every interaction. "
                f"(threshold={self.threshold}, min_length={self.min_length}) "
                "Disable with AUTO_REFINE_PROMPTS=false unless this is intentional."
            )
        else:
            logger.info(
                f"PromptPreprocessor initialized: "
                f"enabled={initial_enabled}, threshold={self.threshold}, "
                f"min_length={self.min_length}, "
                f"config_source={'callback' if enabled_callback else ('hierarchy' if config_snapshot else 'env')}"
            )

    @property
    def is_enabled(self) -> bool:
        """Get current enabled state (supports runtime toggling via callback)."""
        if self._enabled_callback is not None:
            return self._enabled_callback()
        return self._static_enabled if self._static_enabled is not None else False

    @property
    def refiner(self) -> PromptRefinerTool:
        """Lazy initialization of PromptRefinerTool."""
        if self._refiner is None:
            self._refiner = PromptRefinerTool(llm=self.llm)
        return self._refiner

    async def process(self, message: UserMessage) -> UserMessage:
        """
        Process a UserMessage and potentially refine its content.

        This method:
        1. Checks if refinement is enabled
        2. Validates message length
        3. Calls PromptRefinerTool to analyze quality
        4. If quality < threshold, replaces content with refined version
        5. Otherwise, returns original message unchanged

        Args:
            message: Incoming UserMessage from the user

        Returns:
            UserMessage with potentially refined content

        Example:
            preprocessor = PromptPreprocessor(llm=agent.llm)
            processed = await preprocessor.process(user_message)
            refined_content = processed.content
        """
        # Fast path: disabled or empty message
        if not self.is_enabled:
            return message

        if not message.content or len(message.content.strip()) < self.min_length:
            return message

        # Skip commands (they start with /)
        content = message.content.strip()
        if content.startswith("/"):
            logger.debug(f"Skipping command: {content[:50]}...")
            return message

        # Perform refinement analysis
        try:
            result = await self.refiner.execute(prompt=content)

            if result.error:
                logger.warning(f"PromptRefinerTool failed: {result.error}")
                return message

            # Parse analysis
            analysis = self._parse_analysis(result.output)
            if analysis is None:
                return message

            quality_score = analysis.get("quality_score", 10.0)
            refined_prompt = analysis.get("refined_prompt", content)
            task_type = analysis.get("task_type", "unknown")
            refinement_level = analysis.get("refinement_level", "unknown")

            logger.info(
                f"Prompt analysis: quality={quality_score}/10, "
                f"task_type={task_type}, level={refinement_level}"
            )

            # Check if refinement is needed
            if quality_score >= self.threshold:
                logger.info(
                    f"Prompt quality {quality_score} >= threshold {self.threshold}, "
                    "passing through unchanged"
                )
                return message

            # Apply refinement
            if refined_prompt and refined_prompt != content:
                logger.info(
                    f"Applying refinement: quality {quality_score} -> "
                    f"using refined version (threshold is {self.threshold})"
                )

                # Store refinement action for notification
                _set_last_refinement_action(
                    original=content,
                    refined=refined_prompt,
                    quality=quality_score,
                    task_type=task_type,
                    refinement_level=refinement_level
                )

                # Return message with refined content
                # Note: We publish a notification, but don't add to history
                self._publish_refinement_notification(
                    original=content,
                    refined=refined_prompt,
                    quality=quality_score,
                    task_type=task_type,
                    refinement_level=refinement_level,
                    message=message
                )

                return replace(message, content=refined_prompt)

            # No meaningful refinement possible
            logger.info("Refinement produced no meaningful change, using original")
            return message

        except Exception as e:
            logger.error(f"PromptPreprocessor.process() failed: {e}", exc_info=True)
            return message

    def _parse_analysis(self, output: str) -> Optional[dict]:
        """
        Parse the JSON analysis from PromptRefinerTool.

        Args:
            output: Raw output from PromptRefinerTool (JSON or markdown-wrapped JSON)

        Returns:
            Parsed analysis dict, or None if parsing fails
        """
        if not output:
            return None

        # Try parsing as-is first
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        if "```json" in output:
            try:
                start = output.index("```json") + 7
                end = output.index("```", start)
                return json.loads(output[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                pass

        if "```" in output:
            try:
                start = output.index("```") + 3
                end = output.index("```", start)
                return json.loads(output[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                pass

        logger.warning(f"Failed to parse PromptRefinerTool output: {output[:200]}...")
        return None

    def _publish_refinement_notification(
        self,
        original: str,
        refined: str,
        quality: float,
        task_type: str,
        refinement_level: str,
        message: UserMessage
    ):
        """
        Publish a notification about applied refinement.

        Note: This publishes a lightweight notification message
        that is NOT added to the agent's conversation history.

        Args:
            original: Original prompt content
            refined: Refined prompt content
            quality: Quality score of refined prompt
            task_type: Detected task type
            refinement_level: Level of refinement applied
            message: Original UserMessage (for sequence/session info)
        """
        # In the current architecture, we don't have a direct way to publish
        # notifications from here. The notification would be published by
        # the AgentController or REPL layer.
        #
        # For now, we'll just log the information. The REPL or UI layer
        # could query the preprocessor for the last refinement action.

        logger.info(
            f"Refinement applied:\n"
            f"  Original: {original[:100]}...\n"
            f"  Refined: {refined[:100]}...\n"
            f"  Quality: {quality}/10\n"
            f"  Task Type: {task_type}\n"
            f"  Level: {refinement_level}"
        )


def create_refinement_notification(
    original: str,
    refined: str,
    quality: float,
    task_type: str,
    refinement_level: str
) -> str:
    """
    Create a user-facing notification about applied refinement.

    This function is provided for the UI/REPL layer to format
    refinement notifications for the user.

    Args:
        original: Original prompt content
        refined: Refined prompt content
        quality: Quality score of refined prompt
        task_type: Detected task type
        refinement_level: Level of refinement applied

    Returns:
        Formatted notification string

    Example:
        notification = create_refinement_notification(
            original="Fix the bug",
            refined="Fix the authentication timeout bug...",
            quality=8.5,
            task_type="coding",
            refinement_level="light_enhancement"
        )
        print(notification)
    """
    return (
        f"\n📝 **Auto-Refinement Applied**\n\n"
        f"**Quality:** {quality:.1f}/10 | **Task Type:** {task_type} | **Level:** {refinement_level}\n\n"
        f"**Original Prompt:**\n{original}\n\n"
        f"**Refined Prompt (being used):**\n{refined}\n\n"
        f"_Set AUTO_REFINE_PROMPTS=false to disable._\n"
    )


# Store last refinement action for UI/REPL layer to query
_last_refinement_action: Optional[dict] = None


def get_last_refinement_action() -> Optional[dict]:
    """
    Get the last refinement action for notification purposes.

    Returns:
        Dict with keys: original, refined, quality, task_type, refinement_level
        or None if no refinement has occurred
    """
    return _last_refinement_action


def _set_last_refinement_action(
    original: str,
    refined: str,
    quality: float,
    task_type: str,
    refinement_level: str
):
    """Store the last refinement action (internal use)."""
    global _last_refinement_action
    _last_refinement_action = {
        "original": original,
        "refined": refined,
        "quality": quality,
        "task_type": task_type,
        "refinement_level": refinement_level,
    }
