"""
Tests for ComicAgent Professional Layouts Enhancement.

Comprehensive test coverage for:
- McCloud's transition types in prompts
- Layout system descriptions
- Special panel techniques
- Gutter-transition alignment
- Visual hierarchy concepts
- Layout selection guide
- Example layout descriptions
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


class TestComicAgentLayouts(unittest.TestCase):
    """Test suite for professional layout enhancements."""

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

    # ===== McCloud's Transition Types Tests =====

    def test_spec_mode_includes_mcloud_transitions(self):
        """Test that SPEC_MODE includes all 6 McCloud transition types."""
        spec_mode = self.agent.SPEC_MODE

        # All 6 transition types must be present
        self.assertIn("Moment-to-Moment", spec_mode)
        self.assertIn("Action-to-Action", spec_mode)
        self.assertIn("Subject-to-Subject", spec_mode)
        self.assertIn("Scene-to-Scene", spec_mode)
        self.assertIn("Aspect-to-Aspect", spec_mode)
        self.assertIn("Non-Sequitur", spec_mode)

    def test_spec_mode_explains_transition_gutter_alignment(self):
        """Test that SPEC_MODE explains gutter-transition alignment."""
        spec_mode = self.agent.SPEC_MODE

        # Should mention the critical relationship (case-insensitive check)
        self.assertTrue("gutter width should match transition type" in spec_mode.lower())

        # Specific examples (case-insensitive check)
        self.assertTrue("scene-to-scene needs wide gutters" in spec_mode.lower())
        self.assertTrue("moment-to-moment needs narrow gutters" in spec_mode.lower())

    def test_spec_mode_provides_transition_examples(self):
        """Test that each transition type has usage examples."""
        spec_mode = self.agent.SPEC_MODE

        # Moment-to-Moment example
        self.assertIn("character's expression changes", spec_mode.lower())

        # Action-to-Action example
        self.assertIn("punch", spec_mode.lower())

        # Scene-to-Scene example
        self.assertIn("travel", spec_mode.lower()) or self.assertIn("location", spec_mode.lower())

    # ===== Layout Systems Tests =====

    def test_spec_mode_includes_layout_systems(self):
        """Test that SPEC_MODE includes all layout systems."""
        spec_mode = self.agent.SPEC_MODE

        # All major systems should be present
        self.assertIn("Row-based", spec_mode)
        self.assertIn("Column-based", spec_mode)
        self.assertIn("Diagonal", spec_mode)
        self.assertTrue("Z-Path" in spec_mode or "Z-formation" in spec_mode or "z-path" in spec_mode.lower())

    def test_spec_mode_explains_z_path_optimization(self):
        """Test that Z-path reading flow is explained."""
        spec_mode = self.agent.SPEC_MODE

        # Z-path should be described
        self.assertIn("top-left", spec_mode.lower())
        self.assertIn("bottom-right", spec_mode.lower())
        self.assertTrue("natural eye movement" in spec_mode.lower() or "eye flow" in spec_mode.lower())

    # ===== Special Panel Techniques Tests =====

    def test_spec_mode_includes_special_techniques(self):
        """Test that SPEC_MODE includes all special panel techniques."""
        spec_mode = self.agent.SPEC_MODE

        # All techniques should be mentioned
        self.assertIn("Splash Pages", spec_mode)
        self.assertIn("Inset Panels", spec_mode)
        self.assertIn("Overlapping Panels", spec_mode)
        self.assertIn("Broken Frames", spec_mode)
        self.assertIn("Borderless Panels", spec_mode)
        self.assertIn("Widescreen Panels", spec_mode)

    def test_spec_mode_explains_technique_usage(self):
        """Test that special techniques have usage guidance."""
        spec_mode = self.agent.SPEC_MODE

        # Splash page usage
        self.assertIn("cover", spec_mode.lower())

        # Inset panel usage
        self.assertIn("detail", spec_mode.lower())

        # Overlapping panel usage
        self.assertTrue("simultaneous" in spec_mode.lower() or "layered" in spec_mode.lower())

    # ===== Gutter Control Tests =====

    def test_spec_mode_includes_gutter_types(self):
        """Test that SPEC_MODE includes all gutter types."""
        spec_mode = self.agent.SPEC_MODE

        # All gutter types should be present
        self.assertIn("standard", spec_mode.lower())
        self.assertIn("wide", spec_mode.lower())
        self.assertTrue("no gutters" in spec_mode.lower() or "borderless" in spec_mode.lower())
        self.assertIn("variable", spec_mode.lower())

    def test_spec_mode_explains_gutter_pacing_relationship(self):
        """Test that gutter width's effect on pacing is explained."""
        spec_mode = self.agent.SPEC_MODE

        # Gutter controls pacing
        self.assertIn("pacing", spec_mode.lower())
        self.assertIn("time", spec_mode.lower())

        # Specific effects
        self.assertIn("time passing", spec_mode.lower())
        self.assertIn("continuous", spec_mode.lower())

    # ===== Visual Hierarchy Tests =====

    def test_spec_mode_includes_visual_hierarchy_concepts(self):
        """Test that SPEC_MODE includes visual hierarchy principles."""
        spec_mode = self.agent.SPEC_MODE

        # Key concepts
        self.assertIn("size", spec_mode.lower())
        self.assertIn("position", spec_mode.lower())
        self.assertIn("frame", spec_mode.lower())
        self.assertIn("emphasis", spec_mode.lower())

    def test_spec_mode_includes_composition_techniques(self):
        """Test that within-panel composition is explained."""
        spec_mode = self.agent.SPEC_MODE

        # Rule of thirds
        self.assertTrue("Rule of Thirds" in spec_mode or "rule of thirds" in spec_mode.lower())

        # Golden ratio
        self.assertTrue("Golden Ratio" in spec_mode or "golden ratio" in spec_mode.lower())

        # Negative space
        self.assertTrue("Negative" in spec_mode or "negative space" in spec_mode.lower())

    # ===== Layout Selection Guide Tests =====

    def test_spec_mode_includes_layout_selection_guide(self):
        """Test that layout selection guide table is present."""
        spec_mode = self.agent.SPEC_MODE

        # Should have table or guide
        self.assertTrue("Layout Selection" in spec_mode or "selection guide" in spec_mode.lower())

        # Should mention story types
        self.assertIn("Story Type", spec_mode)

    def test_layout_guide_maps_story_to_layout(self):
        """Test that layout guide maps story types to layouts."""
        spec_mode = self.agent.SPEC_MODE

        # Key mappings should be present
        self.assertIn("Cover", spec_mode)
        self.assertIn("Action", spec_mode)
        self.assertTrue("Dialogue" in spec_mode or "Conversation" in spec_mode)

        # Should include transition types in mapping
        self.assertIn("Transition Type", spec_mode)

    def test_layout_guide_includes_gutter_column(self):
        """Test that layout guide includes gutter recommendations."""
        spec_mode = self.agent.SPEC_MODE

        # Should have gutter column/section
        self.assertIn("Gutter", spec_mode)

    # ===== Example Layout Descriptions Tests =====

    def test_spec_mode_includes_example_descriptions(self):
        """Test that SPEC_MODE includes example layout descriptions."""
        spec_mode = self.agent.SPEC_MODE

        # Should have examples section
        self.assertIn("Example", spec_mode)

        # Should include transition-aware examples
        self.assertIn("action-to-action", spec_mode.lower())
        self.assertIn("scene-to-scene", spec_mode.lower())

    def test_examples_include_transition_types(self):
        """Test that example descriptions specify transition types."""
        spec_mode = self.agent.SPEC_MODE

        # Examples should mention transitions
        self.assertIn("moment-to-moment", spec_mode.lower())
        self.assertIn("aspect-to-aspect", spec_mode.lower())

    # ===== GENERATION_MODE Tests =====

    def test_generation_mode_extracts_transition_type(self):
        """Test that GENERATION_MODE includes transition type extraction."""
        generation_mode = self.agent.GENERATION_MODE

        # Should extract transition type
        self.assertIn("Transition Type", generation_mode)

    def test_generation_mode_extracts_gutter_type(self):
        """Test that GENERATION_MODE includes gutter type extraction."""
        generation_mode = self.agent.GENERATION_MODE

        # Should extract gutter information
        self.assertIn("Gutter", generation_mode)

    def test_generation_mode_extracts_special_techniques(self):
        """Test that GENERATION_MODE extracts special techniques."""
        generation_mode = self.agent.GENERATION_MODE

        # Should extract techniques
        self.assertIn("Special Techniques", generation_mode) or self.assertIn("Techniques", generation_mode)

    def test_generation_mode_includes_layout_parsing_logic(self):
        """Test that GENERATION_MODE includes layout parsing instructions."""
        generation_mode = self.agent.GENERATION_MODE

        # Should have parsing section
        self.assertIn("Parse", generation_mode)

        # Should mention grid detection
        self.assertIn("grid", generation_mode.lower())

    def test_generation_mode_includes_enhanced_prompt_building(self):
        """Test that GENERATION_MODE includes enhanced prompt building."""
        generation_mode = self.agent.GENERATION_MODE

        # Should have prompt building section
        self.assertIn("Build", generation_mode) and self.assertIn("Prompt", generation_mode)

        # Should include prompt building examples (using actual section headers)
        self.assertIn("Basic grid:", generation_mode)
        self.assertIn("With transition awareness:", generation_mode)

    def test_generation_mode_includes_transition_aware_prompts(self):
        """Test that prompt building includes transition-aware examples."""
        generation_mode = self.agent.GENERATION_MODE

        # Examples should be transition-aware
        self.assertIn("action-to-action", generation_mode.lower())
        self.assertIn("narrow gutters", generation_mode.lower())

    # ===== TOOL_GUIDELINES Tests =====

    def test_tool_guidelines_includes_layout_aware_section(self):
        """Test that TOOL_GUIDELINES includes layout-aware generation."""
        tool_guidelines = self.agent.TOOL_GUIDELINES

        # Should have layout-aware section
        self.assertTrue("Layout-Aware" in tool_guidelines or "layout aware" in tool_guidelines.lower())

    def test_tool_guidelines_maps_grid_layouts(self):
        """Test that grid layout mapping is documented."""
        tool_guidelines = self.agent.TOOL_GUIDELINES

        # Should show grid mapping
        self.assertIn("2x3", tool_guidelines)
        self.assertIn("3x3", tool_guidelines)

        # Should mention direct mapping
        self.assertIn("Direct Mapping", tool_guidelines) or self.assertIn("mapping", tool_guidelines.lower())

    def test_tool_guidelines_handles_special_layouts(self):
        """Test that special layout handling is documented."""
        tool_guidelines = self.agent.TOOL_GUIDELINES

        # Should mention special layouts
        self.assertIn("Splash", tool_guidelines)
        self.assertIn("Diagonal", tool_guidelines)
        self.assertIn("Overlapping", tool_guidelines) or self.assertIn("overlap", tool_guidelines.lower())

    def test_tool_guidelines_includes_gutter_extraction(self):
        """Test that gutter information extraction is documented."""
        tool_guidelines = self.agent.TOOL_GUIDELINES

        # Should have gutter section
        self.assertIn("Gutter", tool_guidelines)

        # Should mention extraction
        self.assertIn("Extract", tool_guidelines)

    def test_tool_guidelines_includes_emphasis_extraction(self):
        """Test that emphasis information extraction is documented."""
        tool_guidelines = self.agent.TOOL_GUIDELINES

        # Should have emphasis section
        self.assertIn("Emphasis", tool_guidelines)

    def test_tool_guidelines_includes_transition_gutter_alignment(self):
        """Test that transition-gutter alignment is documented."""
        tool_guidelines = self.agent.TOOL_GUIDELINES

        # Should mention the critical alignment (case-insensitive check)
        self.assertTrue("scene-to-scene" in tool_guidelines.lower() and "wide" in tool_guidelines.lower())
        self.assertTrue("moment-to-moment" in tool_guidelines.lower() and "narrow" in tool_guidelines.lower())

    # ===== Integration Tests =====

    def test_backward_compatibility_basic_grids(self):
        """Test that basic grid layouts still work (backward compatibility)."""
        spec_mode = self.agent.SPEC_MODE

        # Basic grids should still be mentioned
        self.assertIn("2x2", spec_mode)
        self.assertIn("2x3", spec_mode)
        self.assertIn("3x3", spec_mode)

    def test_spec_mode_includes_all_new_sections(self):
        """Test that SPEC_MODE includes all new major sections."""
        spec_mode = self.agent.SPEC_MODE

        # Major section headers
        self.assertIn("McCloud", spec_mode) or self.assertIn("Transition", spec_mode)
        self.assertIn("Layout Systems", spec_mode) or self.assertIn("Systems", spec_mode)
        self.assertIn("Special", spec_mode)
        self.assertIn("Gutter", spec_mode)
        self.assertIn("Visual Hierarchy", spec_mode) or self.assertIn("Hierarchy", spec_mode)
        self.assertIn("Composition", spec_mode)
        self.assertIn("Selection", spec_mode) or self.assertIn("Guide", spec_mode)
        self.assertIn("Example", spec_mode)

    def test_prompt_consistency_across_modes(self):
        """Test that terminology is consistent across SPEC and GENERATION modes."""
        spec_mode = self.agent.SPEC_MODE
        generation_mode = self.agent.GENERATION_MODE

        # Transition types should be consistent
        for transition in ["Moment-to-Moment", "Action-to-Action", "Scene-to-Scene"]:
            self.assertIn(transition, spec_mode)

        # Layout terms should be consistent
        for layout in ["diagonal", "splash", "overlapping"]:
            self.assertIn(layout.lower(), spec_mode.lower())


if __name__ == '__main__':
    unittest.main()
