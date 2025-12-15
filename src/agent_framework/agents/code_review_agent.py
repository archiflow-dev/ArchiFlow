"""
CodeReviewAgent: Automated code review agent.

Reviews code changes (diffs, PRs) and provides constructive feedback on:
- Code quality and maintainability
- Security vulnerabilities
- Performance issues
- Best practices
- Architecture and design
"""

from typing import Optional, Callable, List, Dict, Any
from pathlib import Path
from datetime import datetime
import logging
import json
import subprocess
import re

from ..messages.types import BaseMessage, AgentFinishedMessage
from ..llm.provider import LLMProvider
from ..tools.tool_base import ToolRegistry
from .project_agent import ProjectAgent

logger = logging.getLogger(__name__)


class CodeReviewAgent(ProjectAgent):
    """
    Specialized agent for code review tasks.
    
    Reviews code changes (PRs, diffs) and provides constructive feedback
    on code quality, security, performance, and best practices.
    
    Inherits from ProjectAgent to leverage common project functionality.
    """
    
    # Phase 2.2: Enhanced System Prompt
    SYSTEM_PROMPT = """You are an expert Code Review Agent. Your goal is to provide thorough,
constructive code reviews that improve code quality while respecting the
developer's intent.

## YOUR ENVIRONMENT

You have access to:
- Diff file showing code changes
- PR description explaining what the changes should accomplish
- Read-only tools to examine the codebase (read, list, glob, grep)
- TODO tracking tools to organize your review process

## 5-PHASE REVIEW WORKFLOW

### Phase 1: UNDERSTAND THE CONTEXT
- Read the PR description to understand the goal and requirements
- Identify the purpose: bug fix, new feature, refactoring, etc.
- Note any special considerations mentioned by the developer

### Phase 2: EXAMINE THE CHANGES
- Review the diff file to see all code changes
- Identify modified files and their roles in the codebase
- Map changes to requirements from PR description
- Use read/grep tools to understand surrounding context

### Phase 3: ANALYZE ACROSS DIMENSIONS

Review code quality across ALL these dimensions:

**Security** 🔐
- Input validation and sanitization
- SQL injection, XSS, CSRF vulnerabilities
- Authentication and authorization
- Sensitive data exposure
- Cryptography usage
- Dependency vulnerabilities

**Performance** ⚡
- Algorithmic complexity (O(n) issues)
- Database query optimization (N+1 queries)
- Caching opportunities
- Memory leaks
- Resource management (connections, files)
- Unnecessary computations

**Code Quality** ✨
- Readability and clarity
- Naming conventions
- Code duplication (DRY principle)
- Function/method complexity
- Magic numbers and constants
- Documentation and comments

**Correctness** ✅
- Logic errors and bugs
- Edge case handling
- Error handling and recovery
- Null/undefined checks
- Type safety
- Off-by-one errors

**Testing** 🧪
- Test coverage for new code
- Test quality and assertions
- Edge cases tested
- Mock usage appropriateness
- Integration test gaps

**Architecture** 🏗️
- Design patterns usage
- Separation of concerns
- Coupling and cohesion
- SOLID principles
- Backwards compatibility
- API design

### Phase 4: PROVIDE SPECIFIC FEEDBACK
- Create inline comments for each issue found
- Reference exact file names and line numbers
- Explain WHY something is an issue
- Suggest HOW to fix it
- Provide code examples when helpful

### Phase 5: SYNTHESIZE AND RECOMMEND
- Summarize overall assessment
- Highlight strengths of the changes
- Provide actionable recommendations
- Make clear verdict: APPROVE, REQUEST_CHANGES, or COMMENT

## OUTPUT FORMAT

**IMPORTANT**: Write review results directly to files using the `write_review_file` tool.

You MUST create TWO files:

### 1. JSON File: `results/latest.json`

Use `write_review_file` to write the structured JSON review:

{{
  "verdict": "APPROVE | REQUEST_CHANGES | COMMENT",
  "summary": "Brief overall assessment (2-3 sentences)",
  "comments": [
    {{
      "file": "path/to/file.py",
      "line": 42,
      "severity": "CRITICAL | MAJOR | MINOR | NIT",
      "category": "security | performance | code_quality | correctness | testing | architecture",
      "issue": "Clear description of the problem",
      "suggestion": "Specific suggestion on how to fix it",
      "code_example": "Optional code snippet showing the fix"
    }}
  ],
  "strengths": [
    "List positive aspects of the changes",
    "Good practices observed",
    "Well-implemented features"
  ],
  "recommendations": [
    {{"priority": "HIGH", "item": "Critical action item"}},
    {{"priority": "MEDIUM", "item": "Important improvement"}},
    {{"priority": "LOW", "item": "Nice to have enhancement"}}
  ]
}}

### 2. Markdown File: `results/latest.md`

Use `write_review_file` to write a human-readable Markdown report with these sections:
- Header with date and verdict
- Summary
- Review Comments (grouped by severity: CRITICAL, MAJOR, MINOR, NIT)
- Strengths (if any)
- Recommendations (grouped by priority: HIGH, MEDIUM, LOW)

Example structure:
```markdown
# Code Review Report

**Date**: 2024-01-15
**Verdict**: REQUEST_CHANGES

## Summary

[Your meaningful summary here]

## Review Comments

### 🔴 CRITICAL (2)

#### `auth/login.py`

**Line 45** - *security*
**Issue**: SQL injection vulnerability
**Suggestion**: Use parameterized queries
...
```

### 3. Call `finish_task`

After writing both files, call `finish_task` with reason describing what you reviewed:

```
finish_task(reason="Completed code review of authentication module changes")
```

## ⚠️ CRITICAL: Summary Field Requirements

The "summary" field in JSON and Markdown MUST contain a REAL, MEANINGFUL summary of your review. This will be shown to users.

✅ **Good Summary Examples:**
- "The authentication module is well-structured with proper error handling. Found 2 minor issues in input validation that should be addressed."
- "The new API endpoint is well-designed with comprehensive tests. One critical security issue found in user input sanitization."
- "Refactoring improves code clarity significantly. No functional issues found. Minor suggestion for better naming conventions."
- "The changes introduce a memory leak in the file upload handler. Requires fixing before merge."

❌ **DO NOT Use Generic Summaries Like:**
- "Review complete"
- "All phases done"
- "Delivering structured JSON review result"
- "All 5 review phases completed and todos marked completed"
- "Task finished"

**Your summary should answer:**
1. What was changed? (e.g., "authentication module", "API endpoint", "refactoring")
2. What's the overall quality? (e.g., "well-structured", "needs improvement")
3. What's the key finding? (e.g., "2 security issues", "no issues found", "minor improvements needed")

## SEVERITY LEVELS

**CRITICAL** 🔴 - Must fix before merging
- Security vulnerabilities (SQL injection, XSS, authentication bypass)
- Data corruption or loss risks
- Breaking changes to public APIs
- Production-breaking bugs

**MAJOR** 🟠 - Should fix before merging
- Functional bugs affecting core features
- Significant performance degradation
- Poor error handling leading to crashes
- Architectural issues causing tight coupling
- Missing critical tests

**MINOR** 🟡 - Consider fixing
- Code quality issues (duplication, complexity)
- Missing edge case handling
- Incomplete test coverage
- Maintainability concerns
- Minor performance inefficiencies

**NIT** ⚪ - Optional improvements
- Code style inconsistencies
- Naming improvements
- Better comments or documentation
- Refactoring opportunities
- Cosmetic improvements

## VERDICT GUIDELINES

**APPROVE** ✅
- Use when: Changes are high quality with no blocking issues
- Minor/NIT comments are acceptable
- Trust developer to address optional suggestions

**REQUEST_CHANGES** ❌
- Use when: CRITICAL or MAJOR issues exist
- Changes must be made before merging
- Be specific about what needs to change

**COMMENT** 💬
- Use when: Providing feedback without blocking merge
- Questions or discussions needed
- Suggestions for future improvements

## REVIEW GUIDELINES

✅ **Be Specific**: Reference exact files and line numbers
✅ **Be Constructive**: Suggest solutions, not just problems
✅ **Be Thorough**: Check all dimensions, don't rush
✅ **Be Balanced**: Acknowledge good code too
✅ **Be Respectful**: Assume good intent, be kind
✅ **Be Consistent**: Apply same standards across all code
✅ **Be Educational**: Explain the "why" behind suggestions

❌ **Don't**: Make vague complaints without solutions
❌ **Don't**: Focus only on negatives
❌ **Don't**: Nitpick excessively on style
❌ **Don't**: Make subjective preference complaints
❌ **Don't**: Review code you don't understand

## WORKFLOW TRACKING

Use TODO tools to track progress through phases:
1. Create TODOs for each review phase
2. Mark phases as completed as you progress
3. Mark ALL todos as completed BEFORE calling finish_task

## RULES
*   **Explain your thinking**: Before using tools, briefly explain what you're about to do and why. This helps users understand your approach. If you respond with a tool call, also include a message to the user in plain language in the same assistant message before the tool call.
*   **Use `todo_write` proactively**: The system relies on the todo list state. Update it frequently.

## TERMINATION

When review is complete:
1. ✅ Ensure all 5 phases completed
2. ✅ Mark all TODOs as completed
3. ✅ Write `results/latest.json` using `write_review_file` tool
4. ✅ Write `results/latest.md` using `write_review_file` tool
5. ✅ Call `finish_task(reason="Completed review of <what you reviewed>")`

**CRITICAL**:
- You MUST update the todo list to mark all tasks as completed BEFORE writing review files
- You MUST write BOTH JSON and Markdown files BEFORE calling finish_task
- DO NOT pass review data to finish_task's result parameter - write files directly instead

## EXAMPLES

Good comment example:
{{
  "file": "auth/login.py",
  "line": 45,
  "severity": "CRITICAL",
  "category": "security",
  "issue": "SQL query uses string concatenation with user input, vulnerable to SQL injection",
  "suggestion": "Use parameterized queries instead",
  "code_example": "cursor.execute('SELECT * FROM users WHERE username = ?', (username,))"
}}

Bad comment example:
{{
  "file": "utils.py",
  "line": 12,
  "severity": "NIT",
  "category": "code_quality",
  "issue": "This code is bad",
  "suggestion": "Make it better"
}}
"""

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        project_directory: Optional[str] = None,
        tools: Optional[ToolRegistry] = None,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        diff_file: Optional[str] = None,
        pr_description_file: Optional[str] = None,
        review_depth: str = "standard",
        focus_areas: Optional[List[str]] = None,
        debug_log_path: Optional[str] = None
    ):
        """
        Initialize the Code Review Agent.
        
        Args:
            session_id: The session identifier.
            llm: The LLM provider.
            project_directory: Root directory for the project.
            tools: Optional pre-configured tool registry.
            publish_callback: Optional callback for publishing messages.
            diff_file: Path to diff/patch file to review.
            pr_description_file: Path to PR description/requirements file.
            review_depth: Depth of review ('quick', 'standard', 'thorough').
            focus_areas: Optional list of areas to focus on 
                        (e.g., ['security', 'performance']).
            debug_log_path: Optional path for debug logging.
        """
        # Store review-specific configuration
        self.diff_file = diff_file
        self.pr_description_file = pr_description_file
        self.review_depth = review_depth
        self.focus_areas = focus_areas or ['all']
        
        # Define allowed tools (read-only + tracking + write + finish)
        self.allowed_tools = [
            "read",              # Read source files
            "list",              # List directories
            "glob",              # Find files by pattern
            "grep",              # Search code patterns
            "todo_write",        # Track review progress
            "todo_read",         # Read review progress
            "write_review_file", # Write review results (sandboxed to .agent/review/)
            "finish_task"        # Complete review
        ]
        
        # Call parent constructor
        super().__init__(
            session_id=session_id,
            llm=llm,
            project_directory=project_directory,
            tools=tools,
            publish_callback=publish_callback,
            debug_log_path=debug_log_path,
            agent_name="CodeReviewAgent",
            agent_version="1.0.0"
        )
        
        logger.info(
            f"CodeReviewAgent initialized - "
            f"diff_file: {diff_file}, "
            f"pr_description: {pr_description_file}, "
            f"depth: {review_depth}"
        )
        
        # Initialize review folder structure
        self.review_dir = Path(self.project_directory) / ".agent" / "review"
        self._initialize_review_folder()
    
    def _initialize_review_folder(self):
        """
        Initialize the review folder structure.
        
        Creates:
        - .agent/review/ (main review directory)
        - .agent/review/results/ (review results)
        - .agent/review/results/history/ (past reviews)
        - .agent/review/context/ (additional context)
        - .agent/review/metadata.json (tracking file)
        """
        # Create directory structure
        self.review_dir.mkdir(parents=True, exist_ok=True)
        (self.review_dir / "results").mkdir(exist_ok=True)
        (self.review_dir / "results" / "history").mkdir(exist_ok=True)
        (self.review_dir / "context").mkdir(exist_ok=True)
        
        # Initialize metadata if it doesn't exist
        metadata_file = self.review_dir / "metadata.json"
        if not metadata_file.exists():
            initial_metadata = {
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "current_session": self.session_id,
                "reviews": []
            }
            self._save_metadata(initial_metadata)
            logger.info(f"Initialized review folder at {self.review_dir}")
        else:
            # Update session info
            metadata = self._load_metadata()
            metadata["current_session"] = self.session_id
            metadata["last_updated"] = datetime.now().isoformat()
            self._save_metadata(metadata)
            logger.info(f"Using existing review folder at {self.review_dir}")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """
        Load review metadata from metadata.json.
        
        Returns:
            Dictionary containing review metadata.
        """
        metadata_file = self.review_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_metadata(self, metadata: Dict[str, Any]):
        """
        Save review metadata to metadata.json.
        
        Args:
            metadata: Dictionary containing review metadata to save.
        """
        metadata_file = self.review_dir / "metadata.json"
        metadata["last_updated"] = datetime.now().isoformat()
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        logger.debug(f"Saved metadata to {metadata_file}")
    
    def _auto_generate_diff(self) -> Optional[str]:
        """
        Auto-generate diff from git if not provided by user.
        
        Attempts to generate diff with fallback priority:
        1. Staged changes (git diff --cached)
        2. Working directory changes (git diff)
        3. Branch comparison (git diff main...HEAD)
        
        Returns:
            Path to generated diff file, or None if no changes found.
            
        Raises:
            ValueError: If no changes can be detected.
        """
        diff_file = self.review_dir / "auto_generated.diff"
        diff_content = None
        source = None
        
        # Priority 1: Staged changes
        try:
            result = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=self.project_directory,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0 and result.stdout.strip():
                diff_content = result.stdout
                source = "staged"
                logger.info("Generated diff from staged changes")
        except Exception as e:
            logger.warning(f"Could not check staged changes: {e}")
        
        # Priority 2: Working directory
        if not diff_content:
            try:
                result = subprocess.run(
                    ["git", "diff"],
                    cwd=self.project_directory,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    diff_content = result.stdout
                    source = "working_directory"
                    logger.info("Generated diff from working directory")
            except Exception as e:
                logger.warning(f"Could not check working directory: {e}")
        
        # Priority 3: Branch comparison
        if not diff_content:
            try:
                result = subprocess.run(
                    ["git", "diff", "main...HEAD"],
                    cwd=self.project_directory,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    diff_content = result.stdout
                    source = "branch_comparison"
                    logger.info("Generated diff from branch comparison (main...HEAD)")
            except Exception as e:
                logger.warning(f"Could not compare branches: {e}")
        
        # Check if we found any changes
        if not diff_content:
            logger.error("No changes detected - cannot generate diff")
            raise ValueError(
                "No changes detected. Cannot generate diff. "
                "Make some changes or provide a diff file explicitly."
            )
        
        # Parse diff stats
        stats = self._parse_diff_stats(diff_content)
        
        # Save diff file
        diff_file.write_text(diff_content, encoding='utf-8')
        logger.info(
            f"Saved auto-generated diff: {stats['files_changed']} files, "
            f"+{stats['insertions']}/-{stats['deletions']} lines"
        )
        
        # Update metadata
        metadata = self._load_metadata()
        metadata["diff"] = {
            "file": "auto_generated.diff",
            "created_at": datetime.now().isoformat(),
            "source": source,
            "stats": stats
        }
        self._save_metadata(metadata)
        
        return str(diff_file)
    
    def _parse_diff_stats(self, diff_content: str) -> Dict[str, int]:
        """
        Parse statistics from diff content.
        
        Args:
            diff_content: Raw diff text.
            
        Returns:
            Dictionary with files_changed, insertions, deletions counts.
        """
        files_changed = set()
        insertions = 0
        deletions = 0
        
        for line in diff_content.split('\n'):
            # Track files
            if line.startswith('diff --git'):
                # Extract filename from "diff --git a/file b/file"
                match = re.search(r'b/(.+)$', line)
                if match:
                    files_changed.add(match.group(1))
            
            # Count insertions and deletions
            elif line.startswith('+') and not line.startswith('+++'):
                insertions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
        
        return {
            "files_changed": len(files_changed),
            "insertions": insertions,
            "deletions": deletions
        }

    def handle_user_provided_files(
        self, diff_file: Optional[str] = None, pr_description_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle user-provided diff and PR description files.

        Phase 3.3: Validates and copies user-provided files to the review directory.

        Args:
            diff_file: Path to user-provided diff/patch file.
            pr_description_file: Path to user-provided PR description file.

        Returns:
            Dictionary with status and paths to copied files.

        Raises:
            FileNotFoundError: If a provided file doesn't exist.
            ValueError: If a provided file is invalid.
        """
        result = {
            "diff_file": None,
            "pr_description_file": None,
            "copied_files": [],
            "errors": []
        }

        # Handle diff file
        if diff_file:
            diff_path = Path(diff_file)

            # Validate existence
            if not diff_path.exists():
                error_msg = f"Diff file not found: {diff_file}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            # Validate it's a file (not directory)
            if not diff_path.is_file():
                error_msg = f"Diff path is not a file: {diff_file}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Validate file is not empty
            if diff_path.stat().st_size == 0:
                error_msg = f"Diff file is empty: {diff_file}"
                result["errors"].append(error_msg)
                logger.warning(error_msg)

            # Copy to review directory
            target_path = self.review_dir / "user_provided.diff"
            try:
                # Read and parse diff for stats
                diff_content = diff_path.read_text(encoding='utf-8')
                stats = self._parse_diff_stats(diff_content)

                # Write to target
                target_path.write_text(diff_content, encoding='utf-8')
                result["diff_file"] = str(target_path)
                result["copied_files"].append(str(target_path))

                logger.info(
                    f"Copied user-provided diff: {stats['files_changed']} files, "
                    f"+{stats['insertions']}/-{stats['deletions']} lines"
                )

                # Update metadata
                metadata = self._load_metadata()
                metadata["diff"] = {
                    "file": "user_provided.diff",
                    "created_at": datetime.now().isoformat(),
                    "source": "user_provided",
                    "original_path": str(diff_path),
                    "stats": stats
                }
                self._save_metadata(metadata)

            except Exception as e:
                error_msg = f"Error copying diff file: {e}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                raise

        # Handle PR description file
        if pr_description_file:
            pr_desc_path = Path(pr_description_file)

            # Validate existence
            if not pr_desc_path.exists():
                error_msg = f"PR description file not found: {pr_description_file}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            # Validate it's a file
            if not pr_desc_path.is_file():
                error_msg = f"PR description path is not a file: {pr_description_file}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Validate file is not empty
            if pr_desc_path.stat().st_size == 0:
                error_msg = f"PR description file is empty: {pr_description_file}"
                result["errors"].append(error_msg)
                logger.warning(error_msg)

            # Copy to review directory
            target_path = self.review_dir / "user_provided_pr_description.md"
            try:
                pr_content = pr_desc_path.read_text(encoding='utf-8')
                target_path.write_text(pr_content, encoding='utf-8')
                result["pr_description_file"] = str(target_path)
                result["copied_files"].append(str(target_path))

                logger.info(f"Copied user-provided PR description ({len(pr_content)} chars)")

                # Update metadata
                metadata = self._load_metadata()
                metadata["pr_description"] = {
                    "file": "user_provided_pr_description.md",
                    "created_at": datetime.now().isoformat(),
                    "source": "user_provided",
                    "original_path": str(pr_desc_path)
                }
                self._save_metadata(metadata)

            except Exception as e:
                error_msg = f"Error copying PR description file: {e}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                raise

        return result



    def _setup_tools(self):
        """
        Set up tools for code review.

        Registers all standard tools plus the sandboxed ReviewWriteTool.
        """
        # Import tool collection
        from ..tools.all_tools import get_tool_collection

        # Register all standard tools
        for tool in get_tool_collection().tools:
            self.tools.register(tool)

        # Register the sandboxed review write tool
        from ..tools.review_write_tool import ReviewWriteTool
        review_write_tool = ReviewWriteTool(project_directory=str(self.project_directory))
        self.tools.register(review_write_tool)

        logger.info(f"CodeReviewAgent tools configured: {self.allowed_tools}")
    
    def _get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        Get tool schema filtered to allowed tools only.
        
        This enforces read-only access by only exposing safe tools
        to the LLM.
        
        Returns:
            List of tool schemas for allowed tools.
        """
        # Filter tools to only allowed ones
        return self.tools.to_llm_schema(tool_names=self.allowed_tools)
    
    def get_system_message(self) -> str:
        """
        Get the system message for the agent.
        
        Returns:
            Formatted system prompt with environment details.
        """
        review_dir = Path(self.project_directory) / ".agent" / "review"
        
        # Append context info (don't use .format() due to JSON curly braces in prompt)
        context = f"""

## CURRENT CONTEXT

- Project Directory: {self.project_directory}
- Review Directory: {str(review_dir)}
- Diff File: {self.diff_file or "Not provided - will auto-generate"}
- PR Description: {self.pr_description_file or "Not provided - will auto-locate"}
"""
        return self.SYSTEM_PROMPT + context
    
    def _format_finish_message(self, reason: str, result: str) -> str:
        """
        Format the finish message to include full review.
        
        Args:
            reason: Reason for finishing.
            result: Review result (should be JSON).
            
        Returns:
            Formatted finish message.
        """
        # Include both reason and full review result
        return f"{reason}\n\n{result}"
    
    def _locate_pr_description(self) -> Optional[str]:
        """
        Locate PR description file in .agent/review/ folder.
        
        Returns:
            Path to PR description file, or None if not found.
        """
        # Priority 1: Final generated PR description
        pr_file = self.review_dir / "pr_description.md"
        if pr_file.exists():
            logger.info(f"Found final PR description: {pr_file}")
            return str(pr_file)
        
        # Priority 2: Draft PR description
        draft_file = self.review_dir / "pr_description.draft.md"
        if draft_file.exists():
            logger.info(f"Found draft PR description: {draft_file}")
            return str(draft_file)
        
        # Priority 3: User-provided file
        if self.pr_description_file and Path(self.pr_description_file).exists():
            return str(self.pr_description_file)
        
        logger.warning("No PR description found")
        return None
    
    def _prepare_review_context(self) -> dict:
        """
        Prepare review context by auto-loading diff and PR description.
        
        Called on init to set up the review context.
        
        Returns:
            Dictionary with diff_file and pr_description paths.
        """
        context = {
            "diff_file": None,
            "pr_description": None,
            "auto_generated": False
        }
        
        # Get or generate diff
        if self.diff_file and Path(self.diff_file).exists():
            context["diff_file"] = self.diff_file
        else:
            try:
                context["diff_file"] = self._auto_generate_diff()
                context["auto_generated"] = True
            except ValueError as e:
                logger.warning(f"Could not auto-generate diff: {e}")
        
        # Locate PR description
        context["pr_description"] = self._locate_pr_description()
        
        # Update metadata
        metadata = self._load_metadata()
        metadata["review_context"] = {
            "diff_file": context["diff_file"],
            "pr_description": context["pr_description"],
            "auto_generated_diff": context["auto_generated"]
        }
        self._save_metadata(metadata)
        
        logger.info(f"Review context prepared: diff={bool(context['diff_file'])}, pr_desc={bool(context['pr_description'])}")
        return context

    # ========================================================================
    # PHASE 2.1: JSON Review Output Format
    # ========================================================================

    def _validate_review_result(self, review_data: Dict[str, Any]) -> bool:
        """
        Validate review result JSON structure.

        Args:
            review_data: Review result dictionary.

        Returns:
            True if valid, False otherwise.
        """
        required_fields = ["verdict", "summary", "comments"]

        # Check required top-level fields
        for field in required_fields:
            if field not in review_data:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate verdict
        valid_verdicts = ["APPROVE", "REQUEST_CHANGES", "COMMENT"]
        if review_data["verdict"] not in valid_verdicts:
            logger.error(f"Invalid verdict: {review_data['verdict']}")
            return False

        # Validate comments structure
        for idx, comment in enumerate(review_data.get("comments", [])):
            required_comment_fields = ["file", "line", "severity", "category", "issue"]
            for field in required_comment_fields:
                if field not in comment:
                    logger.error(f"Comment {idx} missing field: {field}")
                    return False

            # Validate severity
            valid_severities = ["CRITICAL", "MAJOR", "MINOR", "NIT"]
            if comment["severity"] not in valid_severities:
                logger.error(f"Invalid severity in comment {idx}: {comment['severity']}")
                return False

        return True

    def _save_review_result(self, review_data: Dict[str, Any]) -> Path:
        """
        Save review result to JSON file.

        Saves to:
        - .agent/review/results/latest.json (current review)
        - .agent/review/results/history/<timestamp>.json (archived copy)

        Args:
            review_data: Review result dictionary.

        Returns:
            Path to the saved latest.json file.
        """
        # Validate structure
        if not self._validate_review_result(review_data):
            logger.warning("Review result validation failed, saving anyway")

        # Add metadata
        review_data["metadata"] = {
            "session_id": self.session_id,
            "agent": "CodeReviewAgent",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "review_depth": self.review_depth,
            "focus_areas": self.focus_areas
        }

        # Save to latest.json
        results_dir = self.review_dir / "results"
        latest_file = results_dir / "latest.json"

        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(review_data, f, indent=2)

        logger.info(f"Saved review result to {latest_file}")

        # Archive to history
        history_dir = results_dir / "history"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        history_file = history_dir / f"review_{timestamp}.json"

        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(review_data, f, indent=2)

        logger.info(f"Archived review to {history_file}")

        # Update metadata
        metadata = self._load_metadata()
        if "reviews" not in metadata:
            metadata["reviews"] = []

        metadata["reviews"].append({
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "verdict": review_data["verdict"],
            "comments_count": len(review_data.get("comments", [])),
            "file": f"history/review_{timestamp}.json"
        })

        self._save_metadata(metadata)

        return latest_file

    # ========================================================================
    # PHASE 2.3: Markdown Review Output
    # ========================================================================

    def _convert_review_to_markdown(self, review_data: Dict[str, Any]) -> str:
        """
        Convert JSON review result to Markdown format.

        Args:
            review_data: Review result dictionary.

        Returns:
            Markdown-formatted review.
        """
        md_lines = []

        # Header
        md_lines.append("# Code Review Report")
        md_lines.append("")
        md_lines.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md_lines.append(f"**Verdict**: {review_data.get('verdict', 'UNKNOWN')}")
        md_lines.append("")

        # Summary
        md_lines.append("## Summary")
        md_lines.append("")
        md_lines.append(review_data.get("summary", "No summary provided."))
        md_lines.append("")

        # Comments grouped by severity
        comments = review_data.get("comments", [])
        if comments:
            md_lines.append("## Review Comments")
            md_lines.append("")

            # Group by severity
            severity_order = ["CRITICAL", "MAJOR", "MINOR", "NIT"]
            for severity in severity_order:
                severity_comments = [c for c in comments if c.get("severity") == severity]

                if severity_comments:
                    # Severity section header
                    severity_icon = {
                        "CRITICAL": "🔴",
                        "MAJOR": "🟠",
                        "MINOR": "🟡",
                        "NIT": "⚪"
                    }.get(severity, "")

                    md_lines.append(f"### {severity_icon} {severity} ({len(severity_comments)})")
                    md_lines.append("")

                    # Group by file within severity
                    files = {}
                    for comment in severity_comments:
                        file_path = comment.get("file", "unknown")
                        if file_path not in files:
                            files[file_path] = []
                        files[file_path].append(comment)

                    # Render comments by file
                    for file_path, file_comments in sorted(files.items()):
                        md_lines.append(f"#### `{file_path}`")
                        md_lines.append("")

                        for comment in file_comments:
                            line = comment.get("line", "?")
                            category = comment.get("category", "general")
                            issue = comment.get("issue", "")
                            suggestion = comment.get("suggestion", "")
                            code_example = comment.get("code_example", "")

                            md_lines.append(f"**Line {line}** - *{category}*")
                            md_lines.append("")
                            md_lines.append(f"**Issue**: {issue}")
                            md_lines.append("")

                            if suggestion:
                                md_lines.append(f"**Suggestion**: {suggestion}")
                                md_lines.append("")

                            if code_example:
                                md_lines.append("**Example**:")
                                md_lines.append("```")
                                md_lines.append(code_example)
                                md_lines.append("```")
                                md_lines.append("")

                            md_lines.append("---")
                            md_lines.append("")
        else:
            md_lines.append("## Review Comments")
            md_lines.append("")
            md_lines.append("No issues found.")
            md_lines.append("")

        # Strengths
        strengths = review_data.get("strengths", [])
        if strengths:
            md_lines.append("## Strengths")
            md_lines.append("")
            for strength in strengths:
                md_lines.append(f"- ✅ {strength}")
            md_lines.append("")

        # Recommendations
        recommendations = review_data.get("recommendations", [])
        if recommendations:
            md_lines.append("## Recommendations")
            md_lines.append("")

            # Group by priority
            for priority in ["HIGH", "MEDIUM", "LOW"]:
                priority_recs = [r for r in recommendations if r.get("priority") == priority]

                if priority_recs:
                    priority_icon = {
                        "HIGH": "🔴",
                        "MEDIUM": "🟡",
                        "LOW": "🟢"
                    }.get(priority, "")

                    md_lines.append(f"### {priority_icon} {priority} Priority")
                    md_lines.append("")

                    for rec in priority_recs:
                        md_lines.append(f"- {rec.get('item', '')}")

                    md_lines.append("")

        # Footer
        md_lines.append("---")
        md_lines.append("")
        md_lines.append("*Generated by CodeReviewAgent*")

        return "\n".join(md_lines)

    def _save_markdown_review(self, review_data: Dict[str, Any]) -> Path:
        """
        Save review result to Markdown file.

        Args:
            review_data: Review result dictionary.

        Returns:
            Path to the saved latest.md file.
        """
        # Convert to markdown
        markdown_content = self._convert_review_to_markdown(review_data)

        # Save to latest.md
        results_dir = self.review_dir / "results"
        latest_md = results_dir / "latest.md"

        latest_md.write_text(markdown_content, encoding='utf-8')

        logger.info(f"Saved markdown review to {latest_md}")

        # Also save to history
        history_dir = results_dir / "history"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        history_md = history_dir / f"review_{timestamp}.md"

        history_md.write_text(markdown_content, encoding='utf-8')

        logger.info(f"Archived markdown review to {history_md}")

        return latest_md

    # ========================================================================
    # Phase 3.4: Export Formats (Reviewdog, SARIF)
    # ========================================================================

    def export_review(
        self,
        review_data: Optional[Dict[str, Any]] = None,
        formats: Optional[List[str]] = None
    ) -> Dict[str, Path]:
        """
        Export review results to various formats.

        Phase 3.4: Supports exporting to Reviewdog and SARIF formats
        for integration with CI/CD systems and code quality tools.

        Args:
            review_data: Review data to export (uses latest.json if not provided).
            formats: List of formats to export ('reviewdog', 'sarif').
                    Exports all formats if not specified.

        Returns:
            Dictionary mapping format names to export file paths.
        """
        # Load review data if not provided
        if review_data is None:
            latest_file = self.review_dir / "results" / "latest.json"
            if not latest_file.exists():
                logger.error("No review data found to export")
                return {}

            with open(latest_file, 'r', encoding='utf-8') as f:
                review_data = json.load(f)

        # Determine which formats to export
        if formats is None:
            formats = ["reviewdog", "sarif"]

        # Create exports directory
        exports_dir = self.review_dir / "exports"
        exports_dir.mkdir(exist_ok=True)

        exported_files = {}

        # Export to each requested format
        for format_name in formats:
            if format_name == "reviewdog":
                export_path = self._export_reviewdog(review_data, exports_dir)
                if export_path:
                    exported_files["reviewdog"] = export_path

            elif format_name == "sarif":
                export_path = self._export_sarif(review_data, exports_dir)
                if export_path:
                    exported_files["sarif"] = export_path

            else:
                logger.warning(f"Unknown export format: {format_name}")

        return exported_files

    def _export_reviewdog(
        self, review_data: Dict[str, Any], exports_dir: Path
    ) -> Optional[Path]:
        """
        Export review to Reviewdog JSON format.

        Reviewdog format spec:
        https://github.com/reviewdog/reviewdog

        Format:
        {
          "source": {"name": "CodeReviewAgent", "url": "..."},
          "diagnostics": [
            {
              "message": "Issue description",
              "location": {
                "path": "file.py",
                "range": {"start": {"line": 42, "column": 1}}
              },
              "severity": "ERROR|WARNING|INFO",
              "code": {"value": "category/severity"}
            }
          ]
        }

        Args:
            review_data: Review data to export.
            exports_dir: Directory to save export file.

        Returns:
            Path to exported file or None on error.
        """
        try:
            # Map our severity levels to Reviewdog severity
            severity_map = {
                "CRITICAL": "ERROR",
                "MAJOR": "ERROR",
                "MINOR": "WARNING",
                "NIT": "INFO"
            }

            diagnostics = []

            for comment in review_data.get("comments", []):
                diagnostic = {
                    "message": comment.get("issue", ""),
                    "location": {
                        "path": comment.get("file", ""),
                        "range": {
                            "start": {
                                "line": comment.get("line", 1),
                                "column": 1
                            }
                        }
                    },
                    "severity": severity_map.get(
                        comment.get("severity", "MINOR"), "WARNING"
                    ),
                    "code": {
                        "value": f"{comment.get('category', 'code_quality')}/{comment.get('severity', 'MINOR')}"
                    }
                }

                # Add suggestion if available
                suggestion = comment.get("suggestion", "")
                code_example = comment.get("code_example", "")
                if suggestion or code_example:
                    diagnostic["suggestions"] = []
                    suggestion_text = suggestion
                    if code_example:
                        suggestion_text += f"\n\nExample:\n{code_example}"
                    diagnostic["suggestions"].append({
                        "text": suggestion_text
                    })

                diagnostics.append(diagnostic)

            # Build Reviewdog output
            reviewdog_output = {
                "source": {
                    "name": "CodeReviewAgent",
                    "url": "https://github.com/your-org/your-repo"  # TODO: Make configurable
                },
                "diagnostics": diagnostics
            }

            # Ensure exports directory exists
            exports_dir.mkdir(parents=True, exist_ok=True)

            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = exports_dir / f"reviewdog_{timestamp}.json"

            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(reviewdog_output, f, indent=2)

            logger.info(f"Exported review to Reviewdog format: {export_file}")
            return export_file

        except Exception as e:
            logger.error(f"Error exporting to Reviewdog format: {e}")
            return None

    def _export_sarif(
        self, review_data: Dict[str, Any], exports_dir: Path
    ) -> Optional[Path]:
        """
        Export review to SARIF (Static Analysis Results Interchange Format).

        SARIF spec: https://sarifweb.azurewebsites.net/
        Used by GitHub Code Scanning, Azure DevOps, and other tools.

        Args:
            review_data: Review data to export.
            exports_dir: Directory to save export file.

        Returns:
            Path to exported file or None on error.
        """
        try:
            # Map our severity levels to SARIF levels
            severity_map = {
                "CRITICAL": "error",
                "MAJOR": "error",
                "MINOR": "warning",
                "NIT": "note"
            }

            # Build SARIF results
            results = []

            for comment in review_data.get("comments", []):
                result = {
                    "ruleId": f"{comment.get('category', 'code_quality')}/{comment.get('severity', 'MINOR')}",
                    "level": severity_map.get(comment.get("severity", "MINOR"), "warning"),
                    "message": {
                        "text": comment.get("issue", "")
                    },
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {
                                    "uri": comment.get("file", "")
                                },
                                "region": {
                                    "startLine": comment.get("line", 1),
                                    "startColumn": 1
                                }
                            }
                        }
                    ]
                }

                # Add fix suggestion if available
                suggestion = comment.get("suggestion", "")
                code_example = comment.get("code_example", "")
                if suggestion:
                    result["message"]["markdown"] = f"{comment.get('issue', '')}\n\n**Suggestion**: {suggestion}"
                    if code_example:
                        result["message"]["markdown"] += f"\n\n```\n{code_example}\n```"

                # Add fixes section if code example provided
                if code_example:
                    result["fixes"] = [
                        {
                            "description": {
                                "text": suggestion or "Suggested fix"
                            }
                        }
                    ]

                results.append(result)

            # Build SARIF document
            sarif_output = {
                "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {
                            "driver": {
                                "name": "CodeReviewAgent",
                                "version": "1.0.0",
                                "informationUri": "https://github.com/your-org/your-repo",
                                "rules": self._build_sarif_rules(review_data)
                            }
                        },
                        "results": results
                    }
                ]
            }

            # Ensure exports directory exists
            exports_dir.mkdir(parents=True, exist_ok=True)

            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = exports_dir / f"sarif_{timestamp}.json"

            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(sarif_output, f, indent=2)

            logger.info(f"Exported review to SARIF format: {export_file}")
            return export_file

        except Exception as e:
            logger.error(f"Error exporting to SARIF format: {e}")
            return None

    def _build_sarif_rules(self, review_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build SARIF rules from review comments.

        Each unique category/severity combination becomes a rule.

        Args:
            review_data: Review data.

        Returns:
            List of SARIF rule objects.
        """
        # Collect unique category/severity combinations
        rule_ids = set()
        for comment in review_data.get("comments", []):
            rule_id = f"{comment.get('category', 'code_quality')}/{comment.get('severity', 'MINOR')}"
            rule_ids.add(rule_id)

        # Build rules
        rules = []
        for rule_id in sorted(rule_ids):
            category, severity = rule_id.split("/")

            rule = {
                "id": rule_id,
                "name": f"{category.replace('_', ' ').title()} - {severity}",
                "shortDescription": {
                    "text": f"{severity} severity {category.replace('_', ' ')} issue"
                },
                "fullDescription": {
                    "text": f"Code review identified a {severity.lower()} severity issue in the {category.replace('_', ' ')} category."
                },
                "helpUri": f"https://github.com/your-org/your-repo/docs/rules/{rule_id}",
                "properties": {
                    "category": category,
                    "severity": severity
                }
            }

            rules.append(rule)

        return rules

    # ========================================================================
    # Override finish_task handling to process review results
    # ========================================================================

    def _is_generic_summary(self, summary: str) -> bool:
        """
        Check if summary is generic/placeholder text.

        Args:
            summary: The summary text to check.

        Returns:
            True if summary appears to be generic, False otherwise.
        """
        if not summary or not summary.strip():
            return True

        summary_lower = summary.lower()

        # Generic phrases that indicate placeholder text
        generic_phrases = [
            "delivering",
            "structured json",
            "review complete",
            "all phases",
            "todos marked",
            "task finished",
            "task completed",
            "phases completed",
            "review finished",
            "review done",
            "all done",
            "finished review"
        ]

        # Check if any generic phrase is in the summary
        return any(phrase in summary_lower for phrase in generic_phrases)

    def _generate_summary_from_review(self, review_data: Dict[str, Any]) -> str:
        """
        Generate a meaningful summary from review data when LLM provides a generic one.

        Args:
            review_data: The review data dictionary.

        Returns:
            Generated summary string.
        """
        verdict = review_data.get("verdict", "COMMENT")
        comments = review_data.get("comments", [])
        strengths = review_data.get("strengths", [])

        # Count issues by severity
        critical = sum(1 for c in comments if c.get("severity") == "CRITICAL")
        major = sum(1 for c in comments if c.get("severity") == "MAJOR")
        minor = sum(1 for c in comments if c.get("severity") == "MINOR")
        nit = sum(1 for c in comments if c.get("severity") == "NIT")

        # Build summary based on verdict and findings
        if verdict == "APPROVE":
            if strengths:
                return f"Code review complete. {len(strengths)} strength(s) identified. No blocking issues found."
            else:
                return "Code review complete. No issues found. Code looks good."

        elif verdict == "REQUEST_CHANGES":
            issues = []
            if critical:
                issues.append(f"{critical} critical")
            if major:
                issues.append(f"{major} major")
            if minor:
                issues.append(f"{minor} minor")

            if issues:
                return f"Code review found {', '.join(issues)} issue(s) that require attention before approval."
            else:
                return "Code review requests changes. See comments for details."

        else:  # COMMENT
            if comments:
                total = len(comments)
                if critical or major:
                    return f"Code review complete with {total} observation(s). Some issues need attention, see comments for details."
                else:
                    return f"Code review complete with {total} observation(s). Minor suggestions provided, no blocking issues."
            else:
                if strengths:
                    return f"Code review complete. {len(strengths)} strength(s) noted. No issues found."
                else:
                    return "Code review complete. No issues or observations to report."

    def _archive_review_to_history(self, review_data: Dict[str, Any]) -> None:
        """
        Archive review files to history directory.

        Args:
            review_data: Review data to archive.
        """
        try:
            results_dir = self.review_dir / "results"
            history_dir = results_dir / "history"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Archive JSON
            history_json = history_dir / f"review_{timestamp}.json"
            with open(history_json, 'w', encoding='utf-8') as f:
                json.dump(review_data, f, indent=2)
            logger.info(f"Archived review JSON to {history_json}")

            # Archive Markdown if it exists
            latest_md = results_dir / "latest.md"
            if latest_md.exists():
                history_md = history_dir / f"review_{timestamp}.md"
                markdown_content = latest_md.read_text(encoding='utf-8')
                history_md.write_text(markdown_content, encoding='utf-8')
                logger.info(f"Archived review Markdown to {history_md}")

            # Update metadata
            metadata = self._load_metadata()
            if "reviews" not in metadata:
                metadata["reviews"] = []

            metadata["reviews"].append({
                "timestamp": datetime.now().isoformat(),
                "session_id": self.session_id,
                "verdict": review_data.get("verdict", "UNKNOWN"),
                "comments_count": len(review_data.get("comments", [])),
                "file": f"history/review_{timestamp}.json"
            })

            self._save_metadata(metadata)

        except Exception as e:
            logger.error(f"Error archiving review to history: {e}")

    def _handle_finish_task(self, tool_calls: List[Any]) -> Optional['AgentFinishedMessage']:
        """
        Override to process review results before finishing.

        The agent is expected to write review files using write_review_file tool.
        This method:
        1. Reads the files written by the agent
        2. Validates content and fixes generic summaries if needed
        3. Archives to history
        4. Calls parent to complete finish workflow

        Args:
            tool_calls: List of tool calls from LLM response.

        Returns:
            AgentFinishedMessage if finish_task found, None otherwise.
        """
        # Check for finish_task
        has_finish_task = any(tc.name == "finish_task" for tc in tool_calls)

        if has_finish_task:
            try:
                # Read the review files that should have been written by the agent
                results_dir = self.review_dir / "results"
                latest_json = results_dir / "latest.json"
                latest_md = results_dir / "latest.md"

                # Check if JSON file exists (required)
                if latest_json.exists():
                    # Load and validate the review data
                    with open(latest_json, 'r', encoding='utf-8') as f:
                        review_data = json.load(f)

                    # Validate and fix generic summaries
                    summary = review_data.get("summary", "")
                    if self._is_generic_summary(summary):
                        original_summary = summary
                        review_data["summary"] = self._generate_summary_from_review(review_data)
                        logger.warning(f"Generic summary detected and replaced")
                        logger.warning(f"  Original: {original_summary}")
                        logger.warning(f"  Generated: {review_data['summary']}")

                        # Update the JSON file with fixed summary
                        with open(latest_json, 'w', encoding='utf-8') as f:
                            json.dump(review_data, f, indent=2)

                        # Also update the markdown file if it exists
                        if latest_md.exists():
                            markdown_content = self._convert_review_to_markdown(review_data)
                            latest_md.write_text(markdown_content, encoding='utf-8')

                    # Archive to history
                    self._archive_review_to_history(review_data)

                    logger.info(
                        f"Processed review: {review_data.get('verdict')} "
                        f"with {len(review_data.get('comments', []))} comments"
                    )

                else:
                    logger.warning(
                        "Review JSON file not found. Agent should have written it using write_review_file tool. "
                        f"Expected: {latest_json}"
                    )

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse review JSON file: {e}")
            except Exception as e:
                logger.error(f"Error processing review files: {e}")

        # Call parent to handle finish_task normally
        return super()._handle_finish_task(tool_calls)

