"""
Tech Lead Agent Implementation.

A specialized agent for system architecture design, technical decision-making,
and breaking down projects into implementation phases. This agent bridges the gap
between product requirements and actual implementation.
"""
import logging
from typing import Optional, Callable
from pathlib import Path

from ..messages.types import BaseMessage
from ..tools.tool_base import ToolRegistry
from ..llm.provider import LLMProvider
from .project_agent import ProjectAgent, get_environment_context

logger = logging.getLogger(__name__)


class TechLeadAgent(ProjectAgent):
    """
    A specialized agent for technical leadership and system architecture.

    This agent helps users:
    - Design scalable system architectures
    - Make informed technical decisions with clear rationale
    - Create RFCs and Architecture Decision Records (ADRs)
    - Break down projects into implementation phases and tasks
    - Provide clear handoff documentation for coding agents

    Key Features:
    - Inherits project directory management from ProjectAgent
    - Adaptive workflow based on available documentation
    - Creates comprehensive technical documentation
    - Read-only access to code (+ write for documentation)
    - Integrates with product manager and coding agents
    """

    # Core identity (always active)
    CORE_IDENTITY = """You are an expert Technical Lead and Software Architect. Your role is to:
- Design robust, scalable system architectures
- Make well-reasoned technical decisions
- Create clear implementation plans
- Bridge the gap between business requirements and code

Your project directory is: {project_directory}

You always:
- Think about scalability, maintainability, and team capabilities
- Document your decisions with clear rationale
- Consider trade-offs and alternatives
- Provide practical, implementable solutions"""

    # Mode detection (first priority)
    MODE_DETECTION = """## MODE DETECTION (Always check this first)

Before any other action, assess what documentation/information is available:

### Step 1: Check for Existing Documentation
Use `glob` and `read` to look for:
- docs/PRODUCT_REQUIREMENTS.md
- docs/TECHNICAL_SPEC.md
- docs/USER_STORIES.md
- README.md
- Any *.md files in docs/
- Any existing codebase

### Step 2: Determine Your Mode

**IF** you find complete product requirements documentation:
→ ENTER ANALYSIS MODE
- Read all documents first
- Focus on technical clarifications
- Design architecture based on requirements

**IF** you find partial documentation or rough notes:
→ ENTER HYBRID MODE
- Read what exists
- Ask targeted questions to fill gaps
- Build upon existing information

**IF** you find NO documentation but existing code:
→ ENTER INTEGRATION MODE
- Explore the codebase
- Understand current architecture
- Plan enhancements/additions

**IF** you find NOTHING:
→ ENTER DISCOVERY MODE
- Start with requirements gathering
- Document as you go
- Create architecture from scratch

**ALWAYS** announce your mode when you start:
- "I'm entering ANALYSIS MODE - I found your requirements..."
- "I'm entering DISCOVERY MODE - let's gather requirements..." """

    # Analysis mode for complete documentation
    ANALYSIS_MODE = """## ANALYSIS MODE

You found existing documentation. Here's your workflow:

1. **Read and Understand**
   - Read all documentation files
   - Look for: requirements, constraints, tech preferences
   - Use `todo_write` to track key points

2. **Clarify Technical Details**
   Focus questions on:
   - Scale: "What are the specific scalability targets?"
   - Performance: "What are the latency/throughput requirements?"
   - Constraints: "Are there budget, timeline, or technology constraints?"
   - Team: "What's the team size and expertise?"

3. **Architecture Design**
   Based on requirements, design:
   - System architecture patterns
   - Technology stack recommendations
   - Data models and flows
   - Security considerations

4. **Create Implementation Plan**
   Break down into phases with:
   - Clear dependencies
   - Effort estimates
   - Risk mitigation

Exit condition: When you have a complete technical plan"""

    # Discovery mode for no documentation
    DISCOVERY_MODE = """## DISCOVERY MODE

No documentation found. Here's your workflow:

1. **Business Understanding** (Create docs/BUSINESS_REQUIREMENTS.md)
   Ask about:
   - Problem: "What problem are you solving?"
   - Users: "Who are your target users?"
   - Value: "What makes your solution unique?"
   - Success: "What does success look like?"

2. **Feature Discovery** (Update docs/BUSINESS_REQUIREMENTS.md)
   Ask about:
   - Core features: "What features are essential for launch?"
   - User workflows: "Walk me through how a user would use this"
   - Differentiators: "What makes this better than existing solutions?"

3. **Technical Requirements** (Create docs/TECHNICAL_REQUIREMENTS.md)
   Ask about:
   - Scale: "Expected users, data volume, transactions?"
   - Performance: "Response time, uptime requirements?"
   - Security: "Data sensitivity, compliance needs?"
   - Integration: "Existing systems to connect?"
   - Team: "Team size, preferred technologies?"

4. **Document Confirmation**
   After each section, say:
   "I've documented this in [file]. Does this capture what you described?"

5. **Architecture Design**
   Only AFTER requirements are documented:
   - Propose architecture
   - Explain design decisions
   - Create diagrams

Exit condition: When requirements are documented AND architecture is designed"""

    # Hybrid mode for partial information
    HYBRID_MODE = """## HYBRID MODE

Partial information found. Here's your workflow:

1. **Review Existing**
   - Read what exists
   - Note gaps in information
   - `todo_write` what's missing

2. **Fill Gaps**
   Ask specific questions for missing information:
   - "I see you mentioned X, but can you clarify Y?"
   - "Your notes cover features, but what about scale?"

3. **Complete Documentation**
   - Update existing docs
   - Create missing sections
   - Confirm understanding

4. **Proceed with Architecture**
   - Design based on complete picture
   - Consider constraints from existing info

Exit condition: When documentation is complete AND architecture is designed"""

    # Integration mode for existing code
    INTEGRATION_MODE = """## INTEGRATION MODE

Existing codebase found. Here's your workflow:

1. **Code Analysis**
   Use `glob` and `grep` to understand:
   - Programming languages and frameworks
   - Architecture patterns used
   - Database systems
   - APIs and services
   - Configuration and deployment

2. **Current State Assessment**
   - Document current architecture
   - Identify technical debt
   - Note scalability limits
   - Find integration points

3. **Enhancement Planning**
   For new features:
   - Maintain existing patterns vs. introduce new ones
   - Minimize disruption
   - Plan migration strategy
   - Consider backward compatibility

4. **Implementation Strategy**
   - How to add features safely
   - Testing strategy
   - Rollback plan

Exit condition: When integration plan is complete"""

    # Universal guidelines for all modes
    UNIVERSAL_GUIDELINES = """## UNIVERSAL GUIDELINES

### Communication Style
- Be conversational but professional
- Ask 2-3 questions at a time, not overwhelming
- Explain your reasoning before making decisions
- Use diagrams and examples to clarify complex ideas

### Documentation Standards
- Always create documentation as you work
- Use clear, structured markdown
- Include rationale for decisions
- Track tasks with `todo_write`

### Decision Making
- Always consider alternatives
- Explain trade-offs clearly
- Recommend, don't dictate
- Consider team capabilities

### Quality Assurance
- Define acceptance criteria
- Plan for testing
- Consider monitoring and observability
- Think about maintenance and operations

### Diagram Generation
Create diagrams using one of these approaches:

1. **ASCII/Unicode Diagrams** (simple, no dependencies):
```
┌─────────────┐     ┌─────────────┐
│   Service   │────▶│  Database   │
└─────────────┘     └─────────────┘
```

2. **Mermaid Diagrams** (text-based, renderable in markdown):
```mermaid
graph TB
    A[Service] --> B[Database]
```

Always place diagrams in docs/architecture/diagrams/"""

    # Completion criteria
    COMPLETION_CRITERIA = """## COMPLETION CRITERIA

Call `finish_task` when you have delivered:

**Must Have:**
1. ✓ Architecture documentation
2. ✓ Implementation phases
3. ✓ Task breakdown with priorities
4. ✓ Technology recommendations with rationale

**Nice to Have:**
- Risk assessment
- Performance projections
- Scaling strategy
- Monitoring plan

**Before finishing:**
1. Mark all todos as completed
2. Create summary of deliverables
3. Provide clear next steps
4. Recommend which agent to use next (usually coding agent)"""

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        project_directory: Optional[str] = None,
        tools: Optional[ToolRegistry] = None,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        debug_log_path: Optional[str] = None
    ):
        """
        Initialize the Tech Lead Agent.

        Args:
            session_id: The session identifier.
            llm: The LLM provider for intelligent conversation.
            project_directory: Root directory for the project.
                              Defaults to current working directory if not specified.
            tools: Optional custom tools. If None, uses global registry.
            publish_callback: Callback for publishing messages to broker.
            debug_log_path: Optional path to debug log file for saving LLM interactions.
                           If None, no debug logging is performed.
        """
        # Define allowed tools (read-only + write for documentation)
        self.allowed_tools = [
            "todo_write", "todo_read",  # Task/tracking
            "write", "read",            # Documentation generation
            "list", "glob",             # Project navigation
            "grep",                     # Search for patterns
            "finish_task"               # Completion signal
        ]

        # Call parent constructor - handles all common initialization
        super().__init__(
            session_id=session_id,
            llm=llm,
            project_directory=project_directory,
            tools=tools,
            publish_callback=publish_callback,
            debug_log_path=debug_log_path,
            agent_name="TechLeadAgent",
            agent_version="1.0.0"
        )

        logger.info(
            f"TechLeadAgent initialized for session {session_id}, "
            f"project: {self.project_directory}"
        )

    def get_system_message(self) -> str:
        """
        Dynamically build system prompt based on available documentation.

        Returns:
            The complete system message with appropriate mode-specific instructions
        """
        # Build the prompt parts
        prompt_parts = [
            self.CORE_IDENTITY.format(project_directory=self.project_directory),
            self.MODE_DETECTION,
        ]

        # Check documentation availability
        if self._has_complete_docs():
            prompt_parts.append(self.ANALYSIS_MODE)
        elif self._has_partial_docs():
            prompt_parts.append(self.HYBRID_MODE)
        elif self._has_existing_code():
            prompt_parts.append(self.INTEGRATION_MODE)
        else:
            prompt_parts.append(self.DISCOVERY_MODE)

        # Add universal guidelines and completion criteria
        prompt_parts.extend([
            self.UNIVERSAL_GUIDELINES,
            self.COMPLETION_CRITERIA
        ])

        # Add environment context
        prompt_parts.append(get_environment_context(working_directory=str(self.project_directory)))

        return "\n\n".join(prompt_parts)

    def _has_complete_docs(self) -> bool:
        """Check if complete product documentation exists."""
        docs_dir = Path(self.project_directory) / "docs"

        # Look for key documents
        required_files = [
            "PRODUCT_REQUIREMENTS.md",
            "TECHNICAL_SPEC.md",
            "USER_STORIES.md"
        ]

        found_files = 0
        for file in required_files:
            if (docs_dir / file).exists():
                found_files += 1

        # Consider "complete" if at least 2 of 3 key files exist
        return found_files >= 2

    def _has_partial_docs(self) -> bool:
        """Check if any partial documentation exists."""
        docs_dir = Path(self.project_directory) / "docs"

        # Check for any markdown files
        if docs_dir.exists():
            md_files = list(docs_dir.glob("*.md"))
            if md_files:
                return True

        # Check for README in root
        if Path(self.project_directory, "README.md").exists():
            return True

        return False

    def _has_existing_code(self) -> bool:
        """Check if there's existing code in the project."""
        project_path = Path(self.project_directory)

        # Look for common code indicators
        code_indicators = [
            "src", "lib", "app", "main.py", "index.js", "package.json",
            "pom.xml", "requirements.txt", "Cargo.toml", "go.mod"
        ]

        for indicator in code_indicators:
            if (project_path / indicator).exists():
                return True

        # Look for any code files
        code_extensions = [".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp"]
        for ext in code_extensions:
            if list(project_path.rglob(f"*{ext}")):
                return True

        return False

    def _setup_tools(self):
        """
        Validate required tools are available.

        TechLeadAgent uses tools for architecture and documentation:
        - todo_write/todo_read: Track decisions and tasks
        - write: Generate RFCs, ADRs, architecture docs
        - read: Reference existing documentation and code
        - list/glob/grep: Explore project structure
        - finish_task: Signal completion with deliverable summary
        """
        # Verify required tools are available
        missing_tools = []
        for tool_name in self.allowed_tools:
            if not self.tools.get(tool_name):
                missing_tools.append(tool_name)
                logger.warning(f"Required tool not found in registry: {tool_name}")

        if missing_tools:
            raise ValueError(
                f"Missing required tools: {', '.join(missing_tools)}. "
                "Make sure all_tools.register_all_tools() has been called."
            )

        logger.info(
            f"TechLeadAgent verified {len(self.allowed_tools)} "
            f"tools are available"
        )

    def _get_tools_schema(self) -> list[dict]:
        """
        Get filtered tool schema (documentation and analysis tools only).

        This ensures the LLM can only see and use tools appropriate for
        tech lead work, even though the global registry contains all tools.

        Returns:
            List of tool schemas for allowed documentation tools
        """
        return self.tools.to_llm_schema(tool_names=self.allowed_tools)

    def _format_finish_message(self, reason: str, result: str) -> str:
        """
        Format finish message to include deliverables summary.

        Overrides parent to include the complete summary of architecture
        documentation created, decisions made, and implementation plan.

        Args:
            reason: Reason for finishing (e.g., "Architecture design complete")
            result: Comprehensive summary of deliverables and decisions

        Returns:
            Formatted message with both reason and detailed summary
        """
        return f"{reason}\n\n{result}"