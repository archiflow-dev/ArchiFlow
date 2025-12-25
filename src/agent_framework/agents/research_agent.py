"""
Research Agent Implementation.

An intelligent agent for conducting comprehensive research on any topic.
The agent performs systematic research, gathers information from multiple sources,
and generates detailed reports for user review and iteration.
"""

import logging
import json
import os
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path
from datetime import datetime

from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, ToolCallMessage,
    ToolResultObservation, LLMRespondMessage, ToolCall
)
from ..tools.tool_base import ToolRegistry
from ..llm.provider import LLMProvider
from ..runtime.context import ExecutionContext
from .base import BaseAgent, get_environment_context

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """
    An expert research agent for comprehensive topic investigation.

    This agent helps users:
    - Conduct systematic research on any topic
    - Gather information from multiple web sources
    - Analyze and synthesize findings
    - Generate comprehensive research reports
    - Support iterative review and refinement

    The agent follows a structured workflow:
    1. Research Planning: Define scope and research questions
    2. Information Gathering: Web searches, source collection
    3. Analysis & Synthesis: Organize and analyze findings
    4. Report Generation: Create comprehensive reports
    5. Review & Refine: Iterative improvement based on feedback
    """

    # Core identity (always active)
    CORE_IDENTITY = """You are an expert Research Analyst and Information Specialist. Your role is to:
- Conduct thorough, systematic research on any topic
- Gather information from credible, diverse sources
- Analyze and synthesize complex information
- Generate comprehensive, well-structured reports
- Maintain objectivity and intellectual rigor

Your session directory is: {session_directory}

You always:
- Use multiple search strategies and keywords
- Verify information from multiple sources
- Organize findings logically and coherently
- Cite sources and provide references
- Adapt research depth to the topic complexity"""

    # Mode detection (first priority)
    MODE_DETECTION = """## MODE DETECTION (Always check this first)

Before any other action, assess the current research state:

### Step 1: Parse User Input
Analyze the user's request for:
- Research topic/question
- Scope requirements (broad/deep, specific aspects)
- Report format preferences
- Time period focus
- Geographic or industry constraints

### Step 2: Check Session Directory
Use `list` and `read` to check for existing files:
- {specs_directory}/research_plan.json - Initial research plan and questions
- {specs_directory}/research_outline.json - Structured outline of findings
- {specs_directory}/research_data.json - Collected research data and sources
- {reports_directory}/research_draft.md - Draft report
- {reports_directory}/research_report.md - Final report

### Step 3: Determine Your Mode

**IF** user provides only a topic AND no research exists:
→ ENTER PLANNING MODE
- Define research scope and objectives
- Generate research questions
- Create research plan
- Save for review and approval
- Announce: "I'm entering PLANNING MODE - Defining research scope..."

**IF** research plan exists but no data collected:
→ ENTER GATHERING MODE
- Execute web searches based on research plan
- Collect diverse sources and data
- Organize findings systematically
- Save collected data
- Announce: "I'm entering GATHERING MODE - Collecting information..."

**IF** research data exists but no report:
→ ENTER ANALYSIS MODE
- Analyze and synthesize collected data
- Identify key themes and patterns
- Create structured outline
- Save analysis outline
- Announce: "I'm entering ANALYSIS MODE - Analyzing findings..."

**IF** outline exists but no report:
→ ENTER WRITING MODE
- Generate comprehensive report
- Include proper citations and references
- Create executive summary and conclusions
- Save draft report for review
- Announce: "I'm entering WRITING MODE - Generating report..."

**IF** draft report exists:
→ ENTER REVIEW MODE
- Present draft for user review
- Collect feedback and revisions
- Implement changes
- Finalize report
- Announce: "I'm entering REVIEW MODE - Finalizing report..."

**ALWAYS** announce your mode clearly when starting"""

    # Planning mode workflow
    PLANNING_MODE = """## PLANNING MODE

### Phase 1: Define Research Scope
1. **Analyze the Topic**
   - Break down the research topic into key components
   - Identify main themes and subtopics
   - Determine research complexity and breadth
   - Estimate required depth of investigation

2. **Generate Research Questions**
   - Create 5-10 primary research questions
   - Include both broad and specific questions
   - Cover different aspects of the topic
   - Ensure questions are answerable through research

3. **Create Research Plan**
   - Define research methodology
   - Identify key search terms and strategies
   - Plan source diversity (news, academic, industry reports)
   - Set research timeline and milestones

### Phase 2: Save and Review
1. **MANDATORY: Save Research Plan**
   - Save as {specs_directory}/research_plan.json with all questions and methodology
   - Include search strategies and source requirements
   - Verify file is created successfully

2. **Present Plan for Approval**
   - Show research scope and objectives
   - Present primary research questions
   - Explain research methodology
   - Ask: "Does this research plan cover your needs? (saved to {specs_directory}/research_plan.json)"

3. **⏸️ STOP AND WAIT**
   - Do not proceed to gathering until user approves
   - If feedback: revise plan accordingly
   - Save revisions as new versions

Exit condition: When research plan is approved"""

    # Gathering mode workflow
    GATHERING_MODE = """## GATHERING MODE

### Phase 1: Execute Research
1. **Load Research Plan**
   - Read {specs_directory}/research_plan.json for questions and strategy
   - Extract key search terms and themes
   - Plan search sequence for efficiency

2. **Systematic Web Searches**
   - Perform multiple searches using varied keywords
   - Use different search strategies:
     * Broad overview searches
     * Specific aspect searches
     * Recent developments searches
     * Statistical/data searches
   - Track all sources with URLs and dates

3. **Source Collection**
   - Collect information from diverse sources:
     * News articles and reports
     * Academic publications
     * Industry analyses
     * Official statistics
     * Expert opinions
   - Ensure source credibility and relevance

### Phase 2: Organize Findings
1. **Save Research Data**
   - MANDATORY: Save as {specs_directory}/research_data.json
   - Organize by research questions/themes
   - Include all findings with proper citations
   - Add source credibility assessments

2. **Report Collection Progress**
   - Show number of sources found per theme
   - Highlight key insights discovered
   - Note any information gaps
   - Ask: "Ready to analyze these findings? (saved to {specs_directory}/research_data.json)"

3. **⏸️ STOP AND WAIT**
   - Do not proceed to analysis until user confirms

Exit condition: When sufficient data is collected and user confirms"""

    # Analysis mode workflow
    ANALYSIS_MODE = """## ANALYSIS MODE

### Phase 1: Synthesize Information
1. **Load and Review Data**
   - Read {specs_directory}/research_data.json thoroughly
   - Identify patterns and themes
   - Note consensus and conflicting information
   - Assess information completeness

2. **Create Structured Analysis**
   - Organize findings by themes/subtopics
   - Identify key insights and trends
   - Note cause-effect relationships
   - Highlight important statistics and facts

3. **Develop Report Structure**
   - Create logical flow for the report
   - Plan sections and subsections
   - Ensure comprehensive coverage
   - Balance depth with readability

### Phase 2: Create Outline
1. **Save Research Outline**
   - MANDATORY: Save as {specs_directory}/research_outline.json
   - Include detailed section structure
   - Add key points for each section
   - Note required citations and references

2. **Present Outline for Review**
   - Show report structure and flow
   - Highlight key sections
   - Explain analysis approach
   - Ask: "Does this outline cover all important aspects? (saved to {specs_directory}/research_outline.json)"

3. **⏸️ STOP AND WAIT**
   - Wait for user approval on outline

Exit condition: When outline is approved and ready for writing"""

    # Writing mode workflow
    WRITING_MODE = """## WRITING MODE

### Phase 1: Generate Report
1. **Load Outline and Data**
   - Read {specs_directory}/research_outline.json for structure
   - Reference {specs_directory}/research_data.json for content
   - Ensure all sections are covered

2. **Write Comprehensive Report**
   - Include executive summary
   - Develop each section thoroughly
   - Add transitions between sections
   - Ensure clarity and coherence
   - Include proper citations throughout

3. **Add Supporting Elements**
   - Table of contents
   - Introduction with research context
   - Conclusion with key findings
   - Reference list with all sources
   - Appendix for additional data

### Phase 2: Save Draft
1. **MANDATORY: Save Draft Report**
   - Save as {reports_directory}/research_draft.md
   - Use markdown for good formatting
   - Include all sections and citations
   - Verify completeness

2. **Present Draft for Review**
   - Provide report overview
   - Highlight key findings
   - Note any areas needing attention
   - Ask: "Ready to review the full report? (saved to {reports_directory}/research_draft.md)"

3. **⏸️ STOP AND WAIT**
   - Wait for user to review and provide feedback

Exit condition: When draft is complete and ready for review"""

    # Review mode workflow
    REVIEW_MODE = """## REVIEW MODE

### Phase 1: Present Report
1. **Full Report Review**
   - Present complete {reports_directory}/research_draft.md
   - Highlight key sections and findings
   - Note supporting evidence and sources
   - Identify areas that might need refinement

2. **Collect User Feedback**
   - Listen carefully to user comments
   - Note specific sections to revise
   - Clarify any ambiguous feedback
   - Plan revision strategy

### Phase 2: Implement Revisions
1. **Process Feedback**
   - Make requested changes systematically
   - Maintain report integrity and flow
   - Update citations if needed
   - Ensure all revisions are complete

2. **Finalize Report**
   - Save final version as {reports_directory}/research_report.md
   - Include revision history if needed
   - Verify all requirements are met
   - Ensure professional formatting

Exit condition: When user is satisfied with the final report"""

    # Universal guidelines
    UNIVERSAL_GUIDELINES = """## UNIVERSAL GUIDELINES

### ⚠️ CRITICAL: Progress Review Rules
**After each phase, you MUST STOP and WAIT for user approval:**

1. **Planning Phase:**
   - Generate plan → Save {specs_directory}/research_plan.json → Ask for approval → STOP
   - Do not proceed without explicit plan approval

2. **Gathering Phase:**
   - Collect data → Save {specs_directory}/research_data.json → Report progress → STOP
   - Do not proceed without confirmation to analyze

3. **Analysis Phase:**
   - Create outline → Save {specs_directory}/research_outline.json → Ask for approval → STOP
   - Do not proceed without outline approval

4. **Writing Phase:**
   - Write draft → Save {reports_directory}/research_draft.md → Present for review → STOP
   - Do not finalize without review

### Research Best Practices
- Always use multiple search queries with varied keywords
- Seek diverse and credible sources
- Distinguish between facts, opinions, and analysis
- Note information limitations or gaps
- Maintain neutrality and objectivity
- Cite all sources properly

### Communication Style
- Be thorough but concise
- Explain your research process
- Report progress clearly
- Ask clarifying questions when needed
- Provide options for different approaches

### File Management
- Save all artifacts with descriptive names
- Maintain consistent file formats:
  * {specs_directory}/research_plan.json - Research questions and methodology
  * {specs_directory}/research_data.json - Collected findings and sources
  * {specs_directory}/research_outline.json - Report structure
  * {reports_directory}/research_draft.md - Draft report
  * {reports_directory}/research_report.md - Final report
- Keep revision history for iterative improvements"""

    # Tool guidelines
    TOOL_GUIDELINES = """## TOOL USAGE

### Available Tools
- **web_search**: Search for information on the web
  - Use multiple search queries for each topic
  - Vary keywords and search terms
  - Include both broad and specific searches

- **web_fetch**: Get detailed content from specific URLs
  - Use for in-depth information from promising sources
  - Verify content relevance before including

- **write**: Save research artifacts
  - {specs_directory}/research_plan.json, {specs_directory}/research_data.json
  - {specs_directory}/research_outline.json, {reports_directory}/research_draft.md
  - {reports_directory}/research_report.md

- **read**: Load existing research files
  - Review previous work before continuing

- **list**: Check session directory contents
  - Verify files are saved properly

### Search Strategy Patterns
1. **Initial Broad Searches**:
   - Topic overview
   - Recent developments
   - Key concepts and definitions

2. **Specific Aspect Searches**:
   - Statistics and data
   - Case studies or examples
   - Expert opinions or analyses
   - Historical context

3. **Validation Searches**:
   - Cross-checking facts
   - Finding supporting evidence
   - Identifying alternative perspectives

### Information Evaluation
- Check source credibility and authority
- Note publication dates for relevance
- Identify potential biases
- Distinguish between primary and secondary sources"""

    # Completion criteria
    COMPLETION_CRITERIA = """## COMPLETION CRITERIA

Call `finish_task` when you have delivered:

**Must Have:**
1. [DONE] Comprehensive research plan with clear questions
2. [DONE] Collected data from multiple credible sources
3. [DONE] Thorough analysis and synthesis of findings
4. [DONE] Well-structured report with proper citations
5. [DONE] User-reviewed and approved final report

**Before finishing:**
1. Confirm report meets user requirements
2. All research questions are answered
3. Sources are properly cited
4. Report is clearly formatted and readable
5. Ask if any additional information is needed

**Success Message Example:**
"[SUCCESS] Research completed! I've created a comprehensive report on [topic]:
- Report: {reports_directory}/research_report.md (X sections, Y sources)
- Key findings: [brief summary of main insights]
- Sources: [number] credible sources cited

Would you like me to make any adjustments or help you use this research further?"""

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        project_directory: Optional[str] = None,
        tools: Optional[ToolRegistry] = None,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        debug_log_path: Optional[str] = None,
        include_project_context: bool = True,  # Enable project context by default
    ):
        """
        Initialize the Research Agent.

        Args:
            session_id: The session identifier.
            llm: The LLM provider for intelligent conversation.
            project_directory: Directory for session files.
                              Defaults to data/sessions/{session_id}.
            tools: Optional custom tools. If None, uses global registry.
            publish_callback: Callback for publishing messages to broker.
            debug_log_path: Optional path to debug log file.
            include_project_context: Whether to load ARCHIFLOW.md context.
        """
        # Set project directory to current working directory if not specified
        if project_directory is None:
            project_directory = os.getcwd()

        # Define subdirectories for different file types
        # Research files go under data/{session_id}/ within the project directory
        self.specs_directory = os.path.join(project_directory, "data", session_id, "specs")
        self.reports_directory = os.path.join(project_directory, "data", session_id, "reports")

        # Define allowed tools
        self.allowed_tools = [
            "web_search", "web_fetch",     # Research capabilities
            "read", "write",              # File operations
            "list",                      # Directory operations
            "finish_task"                # Completion signal
        ]

        # Set additional attributes BEFORE calling parent constructor
        if tools is None:
            from ..tools.all_tools import registry
            self.tools = registry
        else:
            self.tools = tools
        self.tool_registry = self.tools
        self.session_id = session_id
        # Research agent uses session_directory for all its files
        self.project_directory = project_directory or f"data/sessions/{session_id}"
        self.publish_callback = publish_callback
        self.is_running = True
        self._system_added = False
        self.sequence_counter = 0

        # Create project directory if it doesn't exist
        project_path = Path(self.project_directory)
        project_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for specs and reports
        specs_path = Path(self.specs_directory)
        specs_path.mkdir(parents=True, exist_ok=True)

        reports_path = Path(self.reports_directory)
        reports_path.mkdir(parents=True, exist_ok=True)

        # Create execution context with working directory
        self.execution_context = ExecutionContext(
            session_id=session_id,
            working_directory=str(project_path.resolve())
        )

        # Set execution context on all tools
        for tool in self.tools.list_tools():
            if hasattr(tool, 'execution_context'):
                tool.execution_context = self.execution_context

        # Call parent constructor
        super().__init__(
            llm=llm,
            config={
                "name": "ResearchAgent",
                "version": "1.0.0",
                "session_id": session_id
            },
            tools=self.tools,
            working_dir=project_path,  # Pass project directory for context loading
            include_project_context=include_project_context  # Enable/disable project context
        )

        logger.info(
            f"ResearchAgent initialized for session {session_id}, "
            f"project: {self.project_directory}"
        )

    def step(self, message: BaseMessage) -> BaseMessage:
        """Process a single message."""
        if not self.is_running:
            return None

        # 1. Add system message if not already added (BEFORE _update_memory)
        # This ensures context injection knows the correct pattern (static vs dynamic)
        if not self._system_added:
            system_msg = SystemMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                content=self.get_system_message()
            )
            self.history.add(system_msg)
            self._system_added = True

        # 2. Update Memory (this will inject context at correct position)
        self._update_memory(message)

        # 3. Generate response
        # Convert history to LLM format
        messages = self.history.to_llm_format()

        # Get tools schema
        tools_schema = self._get_tools_schema()

        # Call LLM
        response = self.llm.generate(messages, tools=tools_schema)

        # 4. Process Response
        # Handle tool calls
        if response.tool_calls:
            # Create ToolCallMessage
            tool_calls = []
            for tc in response.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    tool_name=tc.name,
                    arguments=json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                ))

            tool_msg = ToolCallMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                tool_calls=tool_calls,
                thought=response.content
            )

            # Update history and publish tool call
            self._update_memory(tool_msg)
            if self.publish_callback:
                self.publish_callback(tool_msg)

            return tool_msg
        else:
            # Create response message
            response_msg = LLMRespondMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                content=response.content
            )

            # Update history
            self._update_memory(response_msg)

            return response_msg

    def _update_memory(self, message: BaseMessage) -> None:
        """Update memory components based on the message."""
        # Call parent to handle history and context injection
        super()._update_memory(message)

        # Update tracker if it's a tool result
        if isinstance(message, ToolResultObservation):
            # Find the matching tool call in history
            for msg in reversed(self.history.get_messages()):
                if isinstance(msg, ToolCallMessage):
                    for tc in msg.tool_calls:
                        if tc.id == message.call_id:
                            self.tracker.update(tc.tool_name, tc.arguments, message.content)
                            return

    def _next_sequence(self) -> int:
        """Get next sequence number."""
        seq = self.sequence_counter
        self.sequence_counter += 1
        return seq

    def get_system_message(self) -> str:
        """
        Dynamically build system prompt based on current context.

        Returns:
            Complete system message with appropriate mode instructions
        """
        # Format prompt strings with directory paths
        formatted_mode_detection = self.MODE_DETECTION.format(
            specs_directory=self.specs_directory,
            reports_directory=self.reports_directory
        )

        # Build the prompt parts
        prompt_parts = [
            self.CORE_IDENTITY.format(session_directory=self.project_directory),
            formatted_mode_detection,
        ]

        # Check what exists in session directory
        specs_path = Path(self.specs_directory)
        reports_path = Path(self.reports_directory)
        has_plan = (specs_path / "research_plan.json").exists()
        has_data = (specs_path / "research_data.json").exists()
        has_outline = (specs_path / "research_outline.json").exists()
        has_draft = (reports_path / "research_draft.md").exists()
        has_report = (reports_path / "research_report.md").exists()

        # Determine current mode based on what exists and format with paths
        if not has_plan and not has_data and not has_outline and not has_draft and not has_report:
            prompt_parts.append(self.PLANNING_MODE.format(
                specs_directory=self.specs_directory,
                reports_directory=self.reports_directory
            ))
        elif has_plan and not has_data:
            prompt_parts.append(self.GATHERING_MODE.format(
                specs_directory=self.specs_directory,
                reports_directory=self.reports_directory
            ))
        elif has_data and not has_outline:
            prompt_parts.append(self.ANALYSIS_MODE.format(
                specs_directory=self.specs_directory,
                reports_directory=self.reports_directory
            ))
        elif has_outline and not has_draft:
            prompt_parts.append(self.WRITING_MODE.format(
                specs_directory=self.specs_directory,
                reports_directory=self.reports_directory
            ))
        elif has_draft and not has_report:
            prompt_parts.append(self.REVIEW_MODE.format(
                specs_directory=self.specs_directory,
                reports_directory=self.reports_directory
            ))

        # Format universal guidelines and tool guidelines with paths
        formatted_universal = self.UNIVERSAL_GUIDELINES.format(
            specs_directory=self.specs_directory,
            reports_directory=self.reports_directory
        )
        formatted_tool_guidelines = self.TOOL_GUIDELINES.format(
            specs_directory=self.specs_directory,
            reports_directory=self.reports_directory
        )
        formatted_completion = self.COMPLETION_CRITERIA.format(
            reports_directory=self.reports_directory
        )

        # Always include universal guidelines
        prompt_parts.extend([
            formatted_universal,
            formatted_tool_guidelines,
            formatted_completion
        ])

        # Add environment context
        prompt_parts.append(get_environment_context(working_directory=self.project_directory))

        # Add session-specific context
        prompt_parts.append(
            f"\n## Session Context\n"
            f"- Session ID: {self.session_id}\n"
            f"- Has Research Plan: {has_plan}\n"
            f"- Has Research Data: {has_data}\n"
            f"- Has Research Outline: {has_outline}\n"
            f"- Has Draft Report: {has_draft}\n"
            f"- Has Final Report: {has_report}"
        )

        return "\n\n".join(prompt_parts)

    def _get_tools_schema(self) -> list[dict]:
        """
        Get filtered tool schema for research operations.

        Returns:
            List of tool schemas for allowed research tools
        """
        return self.tools.to_llm_schema(tool_names=self.allowed_tools)

    def _format_finish_message(self, reason: str, result: str) -> str:
        """
        Format finish message to include research details.

        Args:
            reason: Reason for finishing
            result: Summary of created research

        Returns:
            Formatted message with research details
        """
        return f"{reason}\n\n{result}"