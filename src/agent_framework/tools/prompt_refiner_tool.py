"""Prompt Refiner Tool - Analyzes and refines prompts for better quality.

This tool uses a meta-prompt to evaluate user prompts across multiple quality dimensions
and provides refined versions when needed, following a minimal intervention philosophy.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any

from pydantic import Field

from .tool_base import BaseTool, ToolResult
from ..llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class PromptRefinerTool(BaseTool):
    """Analyzes and refines user prompts using intelligent meta-prompting.

    This tool:
    - Automatically detects task type from prompt content
    - Evaluates quality across 5 dimensions (clarity, specificity, actionability, completeness, structure)
    - Uses 3-level refinement: pass-through (9-10), light enhancement (7-8.9), full transformation (<7)
    - Applies CRAFT framework for full transformations
    - Uses placeholder syntax [BRACKETS] for missing user information

    Meta-prompts are loaded hierarchically:
    1. Project-specific: ./.archiflow/tools/prompt_refiner/system_prompt.md
    2. User-global: ~/.archiflow/tools/prompt_refiner/system_prompt.md
    3. Framework default: src/.../prompts/prompt_refiner/system_prompt.md
    4. Embedded fallback
    """

    name: str = "refine_prompt"
    description: str = (
        "Analyze and refine a user prompt for clarity, structure, and actionability. "
        "Automatically detects task type and intent from prompt content. "
        "Use this when a prompt is vague, ambiguous, or missing critical information. "
        "Returns quality analysis and an improved prompt if needed."
    )

    parameters: Dict = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The user's original prompt to analyze and potentially refine"
            },
            "session_context": {
                "type": "string",
                "description": (
                    "Optional context about the current conversation or session state "
                    "that might help understand the prompt better (e.g., 'user is working on a Python web app', "
                    "'previous discussion about database design')"
                ),
                "default": ""
            }
        },
        "required": ["prompt"]
    }

    # LLM provider for meta-prompting (excluded from schema)
    llm: Optional[LLMProvider] = Field(default=None, exclude=True)

    # Cached meta-prompt template (excluded from schema, internal use only)
    meta_prompt_template_cache: Optional[str] = Field(default=None, exclude=True)

    def __init__(self, llm: Optional[LLMProvider] = None, **data):
        """Initialize the PromptRefinerTool.

        Args:
            llm: Optional LLM provider for meta-prompting.
                 If None, will auto-create from environment configuration.
            **data: Additional fields for BaseTool
        """
        # Auto-create LLM provider from environment if not provided
        if llm is None:
            llm = self._create_llm_from_env()

        if llm is not None:
            data['llm'] = llm
        super().__init__(**data)

    def _create_llm_from_env(self) -> Optional[LLMProvider]:
        """Create LLM provider from environment configuration.

        Uses environment variables to configure provider:
        - DEFAULT_LLM_PROVIDER: Provider name (openai, anthropic, glm, mock)
        - DEFAULT_{PROVIDER}_MODEL: Model for the provider
        - PROMPT_REFINER_MODEL: Override model specifically for prompt refinement

        Returns:
            LLMProvider instance or None if creation fails
        """
        try:
            # Import here to avoid circular imports
            from agent_cli.agents.llm_provider_factory import create_llm_provider

            # Check for prompt-refiner specific model override
            refiner_model = os.getenv("PROMPT_REFINER_MODEL")

            # Create provider using factory (will use env defaults)
            provider = create_llm_provider(model=refiner_model)

            logger.info(
                f"Auto-created LLM provider for PromptRefinerTool: "
                f"{provider.__class__.__name__} with model={provider.model}"
            )
            return provider

        except Exception as e:
            logger.warning(
                f"Failed to auto-create LLM provider from environment: {e}. "
                f"Tool will require explicit LLM provider to be set."
            )
            return None

    async def execute(
        self,
        prompt: str,
        session_context: str = ""
    ) -> ToolResult:
        """Execute prompt refinement analysis.

        Args:
            prompt: The user's original prompt to analyze
            session_context: Optional context about the current conversation

        Returns:
            ToolResult containing JSON with:
                - detected_task_type: Inferred task category
                - detected_domain: Specific domain
                - user_intent: What user is trying to accomplish
                - quality_score: Overall quality (1-10)
                - refinement_level: pass_through | light_enhancement | full_transformation
                - assessment_summary: Brief human-readable summary
                - quality_analysis: Scores for 5 dimensions
                - issues_identified: List of specific issues
                - original_prompt: User's input
                - refined_prompt: Improved version or unchanged
                - refinement_rationale: Explanation of changes
                - suggested_follow_up_questions: Actionable clarifying questions
        """
        try:
            # Validate input
            if not prompt or not prompt.strip():
                return self.fail_response("Prompt cannot be empty")

            # Check LLM provider
            if not self.llm:
                return self.fail_response(
                    "PromptRefinerTool requires an LLM provider to be configured. "
                    "Ensure DEFAULT_LLM_PROVIDER is set in environment, or "
                    "initialize with: PromptRefinerTool(llm=your_llm_provider)"
                )

            # Build meta-prompt
            meta_prompt = self._build_meta_prompt(
                prompt=prompt,
                session_context=session_context
            )

            # Call LLM with meta-prompt
            messages = [
                {"role": "user", "content": meta_prompt}
            ]

            logger.info(f"Analyzing prompt with {self.llm.__class__.__name__}: {prompt[:100]}...")
            response = self.llm.generate(messages)

            # Parse JSON response (handle markdown code blocks and other formats)
            try:
                analysis = self._parse_json_response(response.content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.debug(f"LLM response: {response.content}")
                return self.fail_response(
                    f"Failed to parse refinement analysis. LLM returned invalid JSON: {str(e)}\n"
                    f"Response preview: {response.content[:200]}..."
                )

            # Validate required fields
            required_fields = [
                "detected_task_type", "detected_domain", "user_intent",
                "quality_score", "refinement_level", "assessment_summary",
                "quality_analysis", "issues_identified", "original_prompt",
                "refined_prompt", "refinement_rationale", "suggested_follow_up_questions"
            ]

            missing_fields = [f for f in required_fields if f not in analysis]
            if missing_fields:
                logger.warning(f"LLM response missing fields: {missing_fields}")
                # Add default values for missing fields
                for field in missing_fields:
                    if field == "quality_analysis":
                        analysis[field] = {
                            "clarity": 5, "specificity": 5, "actionability": 5,
                            "completeness": 5, "structure": 5
                        }
                    elif field in ["issues_identified", "suggested_follow_up_questions"]:
                        analysis[field] = []
                    else:
                        analysis[field] = "N/A"

            # Format result for display
            result = self._format_result(analysis)

            logger.info(
                f"Prompt analysis complete: {analysis.get('refinement_level', 'unknown')} "
                f"(score: {analysis.get('quality_score', 0)})"
            )

            return self.success_response(result)

        except Exception as e:
            logger.error(f"Prompt refinement failed: {e}", exc_info=True)
            return self.fail_response(f"Prompt refinement failed: {str(e)}")

    def _parse_json_response(self, content: str) -> dict:
        """Parse JSON from LLM response, handling common formats.

        Handles:
        - Pure JSON
        - Markdown code blocks (```json ... ```)
        - Text before/after JSON
        - Multiple JSON objects (takes first valid one)

        Args:
            content: Raw LLM response content

        Returns:
            Parsed JSON dictionary

        Raises:
            json.JSONDecodeError: If no valid JSON found
        """
        import re

        # Strip leading/trailing whitespace
        content = content.strip()

        # Try parsing as-is first (pure JSON)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        # Pattern: ```json ... ``` or ``` ... ```
        code_block_patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
        ]

        for pattern in code_block_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue

        # Try finding JSON object boundaries { ... }
        # Look for first { and last }
        start_idx = content.find('{')
        end_idx = content.rfind('}')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            potential_json = content[start_idx:end_idx + 1]
            try:
                return json.loads(potential_json)
            except json.JSONDecodeError:
                pass

        # Try finding JSON array boundaries [ ... ]
        start_idx = content.find('[')
        end_idx = content.rfind(']')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            potential_json = content[start_idx:end_idx + 1]
            try:
                return json.loads(potential_json)
            except json.JSONDecodeError:
                pass

        # If all attempts fail, raise the original error
        raise json.JSONDecodeError(
            "No valid JSON found in LLM response",
            content,
            0
        )

    def _load_meta_prompt_template(self) -> str:
        """Load meta-prompt template with hierarchical override system.

        Loading priority (highest to lowest - most specific wins):
        1. Project-specific: ./.archiflow/tools/prompt_refiner/system_prompt.md
        2. User-global: ~/.archiflow/tools/prompt_refiner/system_prompt.md
        3. Framework default: src/.../prompts/prompt_refiner/system_prompt.md
        4. Embedded fallback (should rarely be used)

        This pattern matches Claude Code's ~/.claude → ./.claude hierarchy
        and sets foundation for future ARCHIFLOW.md support.

        Returns:
            Meta-prompt template string
        """
        # Return cached if already loaded
        if self.meta_prompt_template_cache is not None:
            return self.meta_prompt_template_cache

        tool_name = "prompt_refiner"

        # 1. Project-specific (HIGHEST priority - team settings)
        if self.execution_context and self.execution_context.working_directory:
            project_path = (
                Path(self.execution_context.working_directory)
                / ".archiflow"
                / "tools"
                / tool_name
                / "system_prompt.md"
            )
            if project_path.exists():
                logger.info(f"Using project-specific meta-prompt: {project_path}")
                self.meta_prompt_template_cache = project_path.read_text(encoding='utf-8')
                return self.meta_prompt_template_cache

        # 2. User-global (personal preferences across all projects)
        user_path = (
            Path.home()
            / ".archiflow"
            / "tools"
            / tool_name
            / "system_prompt.md"
        )
        if user_path.exists():
            logger.info(f"Using user-global meta-prompt: {user_path}")
            self.meta_prompt_template_cache = user_path.read_text(encoding='utf-8')
            return self.meta_prompt_template_cache

        # 3. Framework default (out-of-box baseline)
        tool_dir = Path(__file__).parent
        default_path = (
            tool_dir
            / "prompts"
            / tool_name
            / "system_prompt.md"
        )
        if default_path.exists():
            logger.info(f"Using framework default meta-prompt: {default_path}")
            self.meta_prompt_template_cache = default_path.read_text(encoding='utf-8')
            return self.meta_prompt_template_cache

        # 4. Embedded fallback (should rarely happen)
        logger.warning(
            "No meta-prompt file found at any level. Using embedded fallback. "
            f"Consider creating {default_path}"
        )
        self.meta_prompt_template_cache = self._get_embedded_meta_prompt()
        return self.meta_prompt_template_cache

    def _get_embedded_meta_prompt(self) -> str:
        """Return embedded meta-prompt as fallback.

        This is a minimal version used only if no files are found.
        The full meta-prompt should be in system_prompt.md files.
        """
        return """# Universal Prompt Refinement System

You are an expert prompt engineer. Analyze the user's prompt and return a JSON response.

## Your Task

1. Detect the task type and domain
2. Score the prompt quality (1-10) across: clarity, specificity, actionability, completeness, structure
3. Determine refinement level:
   - pass_through (score >= 9.0): Return unchanged
   - light_enhancement (score 7.0-8.9): Minor improvements
   - full_transformation (score < 7.0): Major restructuring

## Output Format (JSON only)

```json
{
    "detected_task_type": "task category",
    "detected_domain": "specific domain",
    "user_intent": "what user wants to accomplish",
    "quality_score": 7.5,
    "refinement_level": "light_enhancement",
    "assessment_summary": "Brief assessment",
    "quality_analysis": {"clarity": 8, "specificity": 7, "actionability": 7, "completeness": 8, "structure": 8},
    "issues_identified": ["issue 1", "issue 2"],
    "original_prompt": "user's prompt",
    "refined_prompt": "improved version or same",
    "refinement_rationale": "explanation",
    "suggested_follow_up_questions": ["question 1", "question 2"]
}
```

## User Prompt

{prompt}

## Session Context

{session_context}

Provide your analysis as JSON:"""

    def _build_meta_prompt(self, prompt: str, session_context: str) -> str:
        """Build the meta-prompt for analysis.

        Args:
            prompt: The user's original prompt
            session_context: Optional conversation context

        Returns:
            Formatted meta-prompt string
        """
        # Load template (checks hierarchy: project → user → framework → embedded)
        template = self._load_meta_prompt_template()

        # Replace placeholders
        formatted = template.replace('{prompt}', prompt)
        formatted = formatted.replace(
            '{session_context}',
            session_context or "No additional session context provided"
        )

        return formatted

    def _format_result(self, analysis: Dict[str, Any]) -> str:
        """Format analysis result for display.

        Args:
            analysis: Parsed JSON analysis from LLM

        Returns:
            Formatted string with JSON pretty-printed
        """
        # Return formatted JSON for easy parsing
        return json.dumps(analysis, indent=2)
