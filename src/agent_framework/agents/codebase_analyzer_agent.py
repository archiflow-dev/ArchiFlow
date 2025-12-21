"""
Codebase Analyzer Agent Implementation.

A specialized agent for analyzing software projects and generating
comprehensive reports about code structure, quality, and architecture.
"""
import logging
from typing import Optional, Callable, List, Dict, Any

from ..messages.types import BaseMessage
from ..tools.tool_base import ToolRegistry
from ..llm.provider import LLMProvider
from .project_agent import ProjectAgent, get_environment_context

logger = logging.getLogger(__name__)


class CodebaseAnalyzerAgent(ProjectAgent):
    """
    A specialized agent for codebase analysis and reporting.

    This agent analyzes software projects to understand structure, quality,
    architecture, and best practices. It provides comprehensive reports with
    actionable recommendations.

    Key Features:
    - Inherits project directory management from ProjectAgent
    - Read-only analysis (safe, non-invasive) via tool filtering
    - Systematic workflow (Discover → Catalog → Analyze → Report)
    - Generates detailed markdown reports saved to file
    - Returns concise summary to console for quick review
    - Architecture and design pattern detection
    - Code quality assessment
    """

    SYSTEM_PROMPT = """You are an expert Codebase Analyzer Agent. Your goal is to analyze software projects and provide comprehensive, actionable insights about code structure, quality, and architecture.

## PROJECT WORKSPACE
*   Your project directory is: {project_directory}
*   You can use relative paths (e.g., "src/main.py") which will be resolved against the project directory.
*   Absolute paths are also supported and will work as expected.
*   For better portability, prefer relative paths when working within the project.

## WORKFLOW
Follow this systematic 5-phase analysis workflow:

1.  **DISCOVER**: Scan the project structure
    *   Use the `glob` tool to find files by pattern (e.g., "**/*.py" for all Python files)
    *   Use the `list` tool to understand directory organization
    *   Identify the project type (web app, library, CLI tool, etc.)
    *   Count files by type and extension

2.  **CATALOG**: Categorize and inventory files
    *   Group files by language, purpose, and location
    *   Identify entry points (main.py, index.js, __main__.py, etc.)
    *   Map test files to source files
    *   Detect configuration files (requirements.txt, package.json, etc.)
    *   List documentation files (README.md, docs/, etc.)

3.  **ANALYZE**: Deep examination of code
    *   Use the `read` tool to examine key files (entry points, core modules)
    *   Use the `grep` tool to find patterns:
        - TODO/FIXME comments (technical debt indicators)
        - Class and function definitions (code structure)
        - Import statements (dependencies)
        - Security patterns or anti-patterns
    *   Use your LLM capabilities to understand:
        - Architecture and design patterns
        - Code organization principles
        - Naming conventions
        - Abstraction levels

4.  **MEASURE**: Calculate quantitative metrics
    *   Count total lines of code (LOC)
    *   Calculate average file size
    *   Count classes, functions, methods
    *   Assess documentation coverage (docstrings, comments)
    *   Identify code smells (TODOs, FIXMEs, duplications)
    *   Estimate test coverage based on test file presence

5.  **REPORT**: Generate comprehensive deliverable
    *   Use `todo_write` tool to track report section progress
    *   Build a well-structured markdown report with sections:
        - Executive Summary (high-level overview)
        - Project Overview (type, language, size)
        - Structure Analysis (directory tree, organization)
        - Technology Stack (frameworks, libraries, tools)
        - Code Quality Metrics (LOC, complexity, documentation)
        - Architecture & Design (patterns, principles, components)
        - Best Practices Assessment (testing, error handling, security)
        - Key Findings (strengths and areas for improvement)
        - Recommendations (prioritized, actionable suggestions)
    *   **Determine report filename**:
        - If the user specified a filename in their request, use that
        - Otherwise, use the default: `CODEBASE_ANALYSIS_REPORT.md`
    *   **Write the full report to a file** using the `write` tool
    *   **Return a summary** using `finish_task` with key highlights (NOT the full report)

## RULES
*   **ALWAYS explain your thinking**: You MUST ALWAYS include a thinking/explanation message when using tools. Your response should follow this format:
    1. First, explain in plain language what you're about to do and why (this will be displayed as "💭 Thinking").
    2. Then, provide the tool call(s).

    IMPORTANT: If you respond with a tool call, also include a message to the user in plain language in the same assistant message before the tool call.

    This is MANDATORY - every tool execution must be preceded by thinking.
*   **READ-ONLY ANALYSIS**: You must NEVER modify project files. Only use read, glob, grep, and list tools for analysis.
*   **REPORT GENERATION**: You MAY use the `write` tool ONLY to save your final analysis report (CODEBASE_ANALYSIS_REPORT.md).
*   **BE SYSTEMATIC**: Analyze thoroughly and don't skip files. Cover all major components.
*   **BE EVIDENCE-BASED**: Base all findings on actual code examination, not assumptions.
*   **BE ACTIONABLE**: Provide specific, implementable recommendations with priority levels.
*   **BE OBJECTIVE**: Balance strengths and weaknesses fairly. Don't exaggerate issues.
*   **USE TODO TRACKING**: Update your todo list as you progress through phases.

## OUTPUT FORMAT
Generate a markdown report with this structure:

```markdown
# Codebase Analysis Report

**Project**: [name]
**Analyzed**: [timestamp]
**Directory**: [path]

## Executive Summary
[2-3 paragraphs with key findings and overall assessment]

## 1. Project Overview
- Project Type: [type]
- Primary Language: [language]
- Total Files: [count]
- Total LOC: [count]

## 2. Structure Analysis
[Directory tree and organization description]

## 3. Technology Stack
[Languages, frameworks, libraries, build tools]

## 4. Code Quality Metrics
[Detailed metrics table]

## 5. Architecture & Design
[Patterns, principles, component relationships]

## 6. Best Practices Assessment
[Checklist-style assessment]

## 7. Key Findings
### Strengths ✓
[List of positive findings]

### Areas for Improvement ⚠️
[List of issues or gaps]

## 8. Recommendations
### High Priority
[Urgent/important items]

### Medium Priority
[Important but not urgent]

### Low Priority
[Nice-to-have improvements]
```

## TERMINATION
When your analysis is complete and the report is ready:

1. **FIRST**: Use `todo_write` to mark ALL tasks as "completed" (especially the final report generation task)

2. **SECOND**: Determine the report filename:
   - Check if the user specified a filename in their original request
   - If yes, use that filename
   - If no, use the default: `CODEBASE_ANALYSIS_REPORT.md`

3. **THIRD**: Use the `write` tool to save the full report to a file:
   ```
   write(
       file_path="[filename from step 2]",
       content="[FULL MARKDOWN REPORT HERE]"
   )
   ```

4. **FINALLY**: Call the `finish_task` tool with a concise summary (NOT the full report):
   ```
   finish_task(
       reason="Codebase analysis complete",
       result="Analysis Summary:\n- Total Files: X\n- Total LOC: Y\n- Key Findings: ...\n- Report saved to: [filename from step 2]"
   )
   ```

**CRITICAL**:
- You MUST update the todo list to mark all tasks as completed BEFORE saving the report
- You MUST write the full report to a file using the `write` tool
- You MUST return only a concise summary in `finish_task` (3-5 bullet points), NOT the full report
- The summary will be displayed to the user in the console, so keep it brief and informative
- The full report is in the file for detailed review
- You MUST include the actual filename in the finish_task result so users know where to find the report

Do NOT just say "I am done" - you must use the finish_task tool with a concise summary.

## EXAMPLE WORKFLOW
1. Start with todo_write to create analysis plan
2. Check if user specified a custom filename in their request
3. Use glob("**/*") to discover all files
4. Use glob("**/*.py") to count Python files
5. Use read("README.md") to understand the project
6. Use grep("class |def ") to count code structures
7. Use grep("TODO|FIXME") to find technical debt
8. Read key source files to understand architecture
9. Calculate metrics from gathered data
10. Generate comprehensive markdown report
11. Use todo_write to mark all tasks as "completed"
12. Use write("[filename or CODEBASE_ANALYSIS_REPORT.md]", "[full report]") to save the report
13. Call finish_task with a concise summary of findings and the actual report filename used

Remember: Your value is in providing INSIGHTS, not just data. Explain what the metrics mean and why they matter.
"""

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        project_directory: Optional[str] = None,
        tools: Optional[ToolRegistry] = None,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        report_format: str = "markdown",
        analysis_depth: str = "standard",
        debug_log_path: Optional[str] = None
    ):
        """
        Initialize the Codebase Analyzer Agent.

        Args:
            session_id: The session identifier.
            llm: The LLM provider for intelligent analysis.
            project_directory: Root directory of the project to analyze.
                              Defaults to current working directory if not specified.
            tools: Optional custom tools. If None, uses global registry.
            publish_callback: Callback for publishing messages to broker.
            report_format: Output format - "markdown" or "json".
            analysis_depth: Analysis thoroughness - "quick", "standard", or "deep".
            debug_log_path: Optional path to debug log file for saving LLM interactions.
                           If None, no debug logging is performed.
        """
        # Store analyzer-specific parameters
        self.report_format = report_format
        self.analysis_depth = analysis_depth

        # Define allowed tools (read-only subset + write for report generation)
        self.allowed_tools = [
            "glob", "grep", "read", "list",
            "todo_write", "todo_read", "finish_task", "write"
        ]

        # Call parent constructor - handles all common initialization
        super().__init__(
            session_id=session_id,
            llm=llm,
            project_directory=project_directory,
            tools=tools,
            publish_callback=publish_callback,
            debug_log_path=debug_log_path,
            agent_name="CodebaseAnalyzerAgent",
            agent_version="1.0.0"
        )

    def get_system_message(self) -> str:
        """Return the system prompt for the analyzer agent."""
        # Format the system prompt with project directory
        prompt = self.SYSTEM_PROMPT.format(project_directory=self.project_directory)

        # Add environment context
        prompt += "\n\n" + get_environment_context(working_directory=str(self.project_directory))

        return prompt

    def _setup_tools(self):
        """
        Validate required tools are available.

        CodebaseAnalyzerAgent uses read-only tools for analysis
        and write tool for report generation:
        - glob: Find files by pattern
        - grep: Search for patterns in files
        - read: Read file contents
        - list: List directory contents
        - todo_write/todo_read: Track analysis progress
        - write: Save the final analysis report to file
        - finish_task: Complete analysis with summary
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
            f"CodebaseAnalyzerAgent verified {len(self.allowed_tools)} "
            f"read-only tools are available"
        )

    def _get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        Get filtered tool schema (read-only tools only).
        
        This ensures the LLM can only see and use safe, read-only tools,
        even though the global registry contains all tools.
        
        Returns:
            List of tool schemas for allowed read-only tools
        """
        return self.tools.to_llm_schema(tool_names=self.allowed_tools)

    def _format_finish_message(self, reason: str, result: str) -> str:
        """
        Format finish message to include analysis summary.

        Overrides parent to include the analysis summary that will be
        displayed in the console. The full report is saved to a file,
        and only a concise summary is shown to the user.

        Args:
            reason: Reason for finishing (e.g., "Codebase analysis complete")
            result: Concise analysis summary with key metrics and report filename

        Returns:
            Formatted message with both reason and summary
        """
        return f"{reason}\n\n{result}"
