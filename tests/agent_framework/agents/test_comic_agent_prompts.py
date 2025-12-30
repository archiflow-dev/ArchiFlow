"""
Tests for ComicAgent System Prompts (Phase 3).

Comprehensive test coverage for system prompt content, structure,
mode detection logic, and prompt completeness.
"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import Mock

from agent_framework.agents.comic_agent import ComicAgent
from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, response_content="Test response", **kwargs):
        """Initialize mock provider."""
        self.response_content = response_content
        super().__init__(model="mock-model", usage_tracker=None)

    def generate(self, messages, tools=None, **kwargs):
        """Mock generate method."""
        return LLMResponse(
            content=self.response_content,
            finish_reason=FinishReason.STOP,
            tool_calls=None
        )

    def stream(self, messages, tools=None, **kwargs):
        """Mock stream method - not used in tests."""
        raise NotImplementedError("Streaming not implemented in mock")


class TestComicAgentPrompts(unittest.TestCase):
    """Test suite for ComicAgent system prompts."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()
        self.google_api_key = "fake_api_key"

        # Create agent
        self.agent = ComicAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            google_api_key=self.google_api_key,
            project_directory=self.temp_dir
        )

    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    # ===== Core Identity Tests =====

    def test_core_identity_defines_role(self):
        """Test that core identity clearly defines the agent's role."""
        core_identity = self.agent.CORE_IDENTITY

        # Should define role
        self.assertIn("Comic Book Creator", core_identity)
        self.assertIn("Visual Storyteller", core_identity)

        # Should explain capabilities
        self.assertIn("Transform ideas", core_identity)
        self.assertIn("visual storytelling", core_identity.lower())

    def test_core_identity_mentions_session_directory(self):
        """Test that core identity mentions session directory."""
        core_identity = self.agent.CORE_IDENTITY

        # Should reference session directory
        self.assertIn("session directory", core_identity.lower())
        self.assertIn("{session_directory}", core_identity)

    def test_core_identity_explains_workflow(self):
        """Test that core identity explains the workflow."""
        core_identity = self.agent.CORE_IDENTITY

        # Should mention key workflow concepts
        self.assertIn("Markdown", core_identity)
        self.assertIn("script.md", core_identity)
        self.assertIn("comic_spec.md", core_identity)

    def test_core_identity_sets_expectations(self):
        """Test that core identity sets proper expectations."""
        core_identity = self.agent.CORE_IDENTITY

        # Should emphasize important behaviors
        self.assertIn("always", core_identity.lower())
        self.assertIn("character consistency", core_identity.lower())
        self.assertIn("pacing", core_identity.lower())

    # ===== Mode Detection Tests =====

    def test_mode_detection_has_clear_instructions(self):
        """Test that mode detection has clear step-by-step instructions."""
        mode_detection = self.agent.MODE_DETECTION

        # Should have structured steps
        self.assertIn("MODE DETECTION", mode_detection)
        self.assertIn("Step 1", mode_detection)
        self.assertIn("Step 2", mode_detection)

    def test_mode_detection_defines_all_modes(self):
        """Test that mode detection defines all four modes."""
        mode_detection = self.agent.MODE_DETECTION

        # Should define all modes
        self.assertIn("SCRIPT MODE", mode_detection)
        self.assertIn("SPEC MODE", mode_detection)
        self.assertIn("GENERATION MODE", mode_detection)
        self.assertIn("EXPORT MODE", mode_detection)

    def test_mode_detection_has_file_checks(self):
        """Test that mode detection includes file existence checks."""
        mode_detection = self.agent.MODE_DETECTION

        # Should check for key files
        self.assertIn("script.md", mode_detection)
        self.assertIn("comic_spec.md", mode_detection)
        self.assertIn("character_refs", mode_detection.lower())
        self.assertIn("panels", mode_detection.lower())

    def test_mode_detection_requires_announcements(self):
        """Test that mode detection requires mode announcements."""
        mode_detection = self.agent.MODE_DETECTION

        # Should require announcing mode (checking for bold markdown too)
        self.assertIn("announce", mode_detection.lower())
        self.assertIn("entering", mode_detection.lower())

    # ===== Script Mode Tests =====

    def test_script_mode_has_clarification_phase(self):
        """Test that script mode includes clarification questions."""
        script_mode = self.agent.SCRIPT_MODE

        # Should ask clarifying questions
        self.assertIn("clarification", script_mode.lower())
        self.assertIn("question", script_mode.lower())

    def test_script_mode_defines_script_format(self):
        """Test that script mode defines the markdown format."""
        script_mode = self.agent.SCRIPT_MODE

        # Should include format instructions
        self.assertIn("Markdown", script_mode)
        self.assertIn("script.md", script_mode)

        # Should show structure
        self.assertIn("Page", script_mode)
        self.assertIn("Panel", script_mode)

    def test_script_mode_enforces_save_then_wait(self):
        """Test that script mode enforces save-then-wait workflow."""
        script_mode = self.agent.SCRIPT_MODE

        # Should enforce save first
        self.assertIn("MANDATORY", script_mode)
        self.assertIn("Save", script_mode)
        self.assertIn("BEFORE", script_mode)

        # Should require waiting
        self.assertIn("STOP AND WAIT", script_mode)
        self.assertIn("Do NOT proceed", script_mode)

    def test_script_mode_includes_panel_types(self):
        """Test that script mode mentions panel types."""
        script_mode = self.agent.SCRIPT_MODE

        # Should mention panel types
        self.assertIn("panel", script_mode.lower())
        self.assertIn("Type:", script_mode) or self.assertIn("type", script_mode.lower())

    # ===== Spec Mode Tests =====

    def test_spec_mode_requires_loading_script(self):
        """Test that spec mode requires loading the script first."""
        spec_mode = self.agent.SPEC_MODE

        # Should load script
        self.assertIn("Load", spec_mode)
        self.assertIn("script.md", spec_mode)
        self.assertIn("read", spec_mode.lower())

    def test_spec_mode_defines_spec_sections(self):
        """Test that spec mode defines all required spec sections."""
        spec_mode = self.agent.SPEC_MODE

        # Should define key sections
        self.assertIn("Art Style", spec_mode)
        self.assertIn("Color", spec_mode)
        self.assertIn("Character", spec_mode)

    def test_spec_mode_includes_character_descriptions(self):
        """Test that spec mode requires detailed character descriptions."""
        spec_mode = self.agent.SPEC_MODE

        # Should require character details
        self.assertIn("Character", spec_mode)
        self.assertIn("visual", spec_mode.lower())

    def test_spec_mode_enforces_save_then_wait(self):
        """Test that spec mode enforces save-then-wait workflow."""
        spec_mode = self.agent.SPEC_MODE

        # Should enforce save first
        self.assertIn("Save", spec_mode)
        self.assertIn("comic_spec.md", spec_mode)

        # Should require waiting
        self.assertIn("STOP AND WAIT", spec_mode) or self.assertIn("wait", spec_mode.lower())

    # ===== Generation Mode Tests =====

    def test_generation_mode_requires_character_refs_first(self):
        """Test that generation mode requires character refs to be generated first."""
        generation_mode = self.agent.GENERATION_MODE

        # Should generate character refs first
        self.assertIn("Character Reference", generation_mode)
        self.assertIn("First", generation_mode)  # "Do This First!" or "FIRST"

    def test_generation_mode_uses_generate_comic_panel_tool(self):
        """Test that generation mode uses the generate_comic_panel tool."""
        generation_mode = self.agent.GENERATION_MODE

        # Should use the tool
        self.assertIn("generate_comic_panel", generation_mode)

    def test_generation_mode_shows_progress(self):
        """Test that generation mode includes progress reporting."""
        generation_mode = self.agent.GENERATION_MODE

        # Should show progress
        self.assertTrue("progress" in generation_mode.lower() or
                        ("Page" in generation_mode and "Panel" in generation_mode))

    def test_generation_mode_has_two_phases(self):
        """Test that generation mode has character refs and panels phases."""
        generation_mode = self.agent.GENERATION_MODE

        # Should have phase structure
        self.assertTrue("Phase 1" in generation_mode or "Character" in generation_mode)
        self.assertTrue("Phase 2" in generation_mode or "Story Pages" in generation_mode or
                        "panel" in generation_mode.lower())

    # ===== Export Mode Tests =====

    def test_export_mode_confirms_completion(self):
        """Test that export mode confirms all panels are ready."""
        export_mode = self.agent.EXPORT_MODE

        # Should confirm completion
        self.assertTrue("ready" in export_mode.lower() or "complete" in export_mode.lower())

    def test_export_mode_provides_file_locations(self):
        """Test that export mode provides file locations."""
        export_mode = self.agent.EXPORT_MODE

        # Should mention file locations
        self.assertIn("character_refs", export_mode.lower())
        self.assertIn("panels", export_mode.lower())

    def test_export_mode_calls_finish_task(self):
        """Test that export mode mentions calling finish_task."""
        export_mode = self.agent.EXPORT_MODE

        # Should call finish_task
        self.assertIn("finish_task", export_mode)

    # ===== Universal Guidelines Tests =====

    def test_universal_guidelines_emphasizes_save_then_wait(self):
        """Test that universal guidelines emphasize save-then-wait rule."""
        universal = self.agent.UNIVERSAL_GUIDELINES

        # Should emphasize the rule
        self.assertIn("Save-Then-Wait", universal)
        self.assertIn("CRITICAL", universal)

    def test_universal_guidelines_lists_all_phases(self):
        """Test that universal guidelines cover all workflow phases."""
        universal = self.agent.UNIVERSAL_GUIDELINES

        # Should mention all phases
        self.assertIn("Script", universal)
        self.assertIn("Spec", universal)
        self.assertIn("Generation", universal) or self.assertIn("Character", universal)

    def test_universal_guidelines_has_visual_principles(self):
        """Test that universal guidelines include visual storytelling principles."""
        universal = self.agent.UNIVERSAL_GUIDELINES

        # Should include visual storytelling
        self.assertIn("Visual Storytelling", universal) or \
        self.assertIn("character consistency", universal.lower())

    def test_universal_guidelines_has_file_management(self):
        """Test that universal guidelines include file management."""
        universal = self.agent.UNIVERSAL_GUIDELINES

        # Should include file management
        self.assertIn("File Management", universal) or self.assertIn("session", universal.lower())

    # ===== Tool Guidelines Tests =====

    def test_tool_guidelines_lists_available_tools(self):
        """Test that tool guidelines list all available tools."""
        tool_guidelines = self.agent.TOOL_GUIDELINES

        # Should list tools
        self.assertIn("read", tool_guidelines.lower())
        self.assertIn("write", tool_guidelines.lower())
        self.assertIn("generate_comic_panel", tool_guidelines)

    def test_tool_guidelines_shows_usage_patterns(self):
        """Test that tool guidelines show tool usage patterns."""
        tool_guidelines = self.agent.TOOL_GUIDELINES

        # Should show how to use tools (new simplified API shows generate_comic_page usage)
        self.assertIn("generate_comic_page(", tool_guidelines) or self.assertIn("generate_comic_panel(", tool_guidelines)

    def test_tool_guidelines_mentions_character_references(self):
        """Test that tool guidelines mention character reference usage."""
        tool_guidelines = self.agent.TOOL_GUIDELINES

        # Should explain character reference workflow
        self.assertIn("character_reference", tool_guidelines.lower())

    # ===== Completion Criteria Tests =====

    def test_completion_criteria_defines_requirements(self):
        """Test that completion criteria clearly define what's needed."""
        completion = self.agent.COMPLETION_CRITERIA

        # Should define requirements
        self.assertIn("finish_task", completion)
        self.assertIn("DONE", completion) or self.assertIn("Must Have", completion)

    def test_completion_criteria_lists_deliverables(self):
        """Test that completion criteria list all deliverables."""
        completion = self.agent.COMPLETION_CRITERIA

        # Should list deliverables
        self.assertIn("script", completion.lower())
        self.assertIn("spec", completion.lower())
        self.assertIn("character reference", completion.lower())
        self.assertIn("panel", completion.lower())

    # ===== Integration Tests =====

    def test_get_system_message_in_script_mode(self):
        """Test get_system_message when in script mode (no files exist)."""
        # No files exist - should be script mode
        system_msg = self.agent.get_system_message()

        # Should include mode detection
        self.assertIn("MODE DETECTION", system_msg)

        # Should include script mode
        self.assertIn("SCRIPT MODE", system_msg)

        # Should include universal guidelines
        self.assertIn("UNIVERSAL GUIDELINES", system_msg)

    def test_get_system_message_in_spec_mode(self):
        """Test get_system_message when in spec mode (script exists)."""
        # Create script.md
        session_path = Path(self.temp_dir)
        (session_path / "script.md").write_text("# Test Script")

        system_msg = self.agent.get_system_message()

        # Should include spec mode
        self.assertIn("SPEC MODE", system_msg)

    def test_get_system_message_in_generation_mode(self):
        """Test get_system_message when in generation mode (spec exists)."""
        # Create script.md and comic_spec.md
        session_path = Path(self.temp_dir)
        (session_path / "script.md").write_text("# Test Script")
        (session_path / "comic_spec.md").write_text("# Test Spec")

        system_msg = self.agent.get_system_message()

        # Should include generation mode
        self.assertIn("GENERATION MODE", system_msg)

    def test_get_system_message_in_export_mode(self):
        """Test get_system_message when in export mode (panels exist)."""
        # Create all necessary files
        session_path = Path(self.temp_dir)
        (session_path / "script.md").write_text("# Test Script")
        (session_path / "comic_spec.md").write_text("# Test Spec")

        # Create a panel file
        panels_dir = session_path / "panels"
        panels_dir.mkdir(exist_ok=True)
        (panels_dir / "page_01_panel_01.png").write_bytes(b"fake image")

        system_msg = self.agent.get_system_message()

        # Should include export mode
        self.assertIn("EXPORT MODE", system_msg)

    def test_system_message_always_includes_core_components(self):
        """Test that system message always includes core components."""
        system_msg = self.agent.get_system_message()

        # Should always include these
        self.assertIn("Comic Book Creator", system_msg)
        self.assertIn("MODE DETECTION", system_msg)
        self.assertIn("UNIVERSAL GUIDELINES", system_msg)
        self.assertIn("TOOL USAGE", system_msg)
        self.assertIn("COMPLETION CRITERIA", system_msg)

    def test_system_message_includes_session_context(self):
        """Test that system message includes session-specific context."""
        system_msg = self.agent.get_system_message()

        # Should include session context
        self.assertIn("Session Context", system_msg)
        self.assertIn(f"Session ID: {self.session_id}", system_msg)
        self.assertIn("Has Script:", system_msg)
        self.assertIn("Has Spec:", system_msg)

    # ===== Prompt Consistency Tests =====

    def test_all_modes_mention_stop_and_wait(self):
        """Test that all mode prompts emphasize stop and wait behavior."""
        # Script mode
        self.assertIn("STOP AND WAIT", self.agent.SCRIPT_MODE)

        # Spec mode
        spec_has_wait = "STOP AND WAIT" in self.agent.SPEC_MODE or "wait" in self.agent.SPEC_MODE.lower()
        self.assertTrue(spec_has_wait)

        # Generation mode
        gen_has_wait = "STOP AND WAIT" in self.agent.GENERATION_MODE or "wait" in self.agent.GENERATION_MODE.lower()
        self.assertTrue(gen_has_wait)

    def test_all_modes_use_consistent_file_names(self):
        """Test that all modes reference consistent file names."""
        all_prompts = (
            self.agent.CORE_IDENTITY +
            self.agent.MODE_DETECTION +
            self.agent.SCRIPT_MODE +
            self.agent.SPEC_MODE +
            self.agent.GENERATION_MODE +
            self.agent.EXPORT_MODE
        )

        # Should use consistent names
        self.assertIn("script.md", all_prompts)
        self.assertIn("comic_spec.md", all_prompts)

    def test_prompts_use_consistent_terminology(self):
        """Test that prompts use consistent terminology."""
        all_prompts = (
            self.agent.CORE_IDENTITY +
            self.agent.SCRIPT_MODE +
            self.agent.SPEC_MODE +
            self.agent.GENERATION_MODE
        )

        # Should use "character reference" consistently
        self.assertIn("character", all_prompts.lower())

        # Should use "panel" consistently
        self.assertIn("panel", all_prompts.lower())

    # ===== Prompt Completeness Tests =====

    def test_prompts_are_not_empty(self):
        """Test that all prompt sections are non-empty."""
        self.assertGreater(len(self.agent.CORE_IDENTITY), 100)
        self.assertGreater(len(self.agent.MODE_DETECTION), 100)
        self.assertGreater(len(self.agent.SCRIPT_MODE), 100)
        self.assertGreater(len(self.agent.SPEC_MODE), 100)
        self.assertGreater(len(self.agent.GENERATION_MODE), 100)
        self.assertGreater(len(self.agent.EXPORT_MODE), 100)
        self.assertGreater(len(self.agent.UNIVERSAL_GUIDELINES), 100)
        self.assertGreater(len(self.agent.TOOL_GUIDELINES), 100)
        self.assertGreater(len(self.agent.COMPLETION_CRITERIA), 100)

    def test_prompts_are_well_formatted(self):
        """Test that prompts use markdown formatting."""
        # Should use markdown headers
        self.assertIn("##", self.agent.MODE_DETECTION)
        self.assertIn("##", self.agent.SCRIPT_MODE)
        self.assertIn("##", self.agent.SPEC_MODE)

    def test_file_constants_match_prompts(self):
        """Test that file name constants match what's in prompts."""
        # Check that constants are used in prompts
        self.assertIn(self.agent.SCRIPT_FILE, self.agent.SCRIPT_MODE)
        self.assertIn(self.agent.SPEC_FILE, self.agent.SPEC_MODE)


if __name__ == '__main__':
    unittest.main()
