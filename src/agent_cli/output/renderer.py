"""
Output renderer for the CLI.

Provides consistent formatting for different types of output.
"""

from typing import Any
import logging

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# Global console instance
console = Console()
logger = logging.getLogger(__name__)
# Special logger for tool results
tool_result_logger = logging.getLogger("tool_results")


class OutputRenderer:
    """
    Renders output with consistent formatting using Rich.

    Provides methods for different types of output (errors, success, info, etc.)
    """

    def __init__(self, console_instance: Console | None = None, tool_result_line_limit: int = 20) -> None:
        """
        Initialize the renderer.

        Args:
            console_instance: Optional Rich Console instance to use
            tool_result_line_limit: Maximum number of lines to display for tool results
        """
        self.console = console_instance or console
        self.tool_result_line_limit = tool_result_line_limit

    def error(self, message: str, title: str | None = None) -> None:
        """
        Render an error message in red.

        Args:
            message: The error message
            title: Optional title for the error
        """
        if title:
            self.console.print(f"[bold red]{title}:[/bold red] {message}")
        else:
            self.console.print(f"[bold red]Error:[/bold red] {message}")

    def success(self, message: str, title: str | None = None) -> None:
        """
        Render a success message in green.

        Args:
            message: The success message
            title: Optional title
        """
        if title:
            self.console.print(f"[bold green]{title}:[/bold green] {message}")
        else:
            self.console.print(f"[green]✓[/green] {message}")

    def info(self, message: str, title: str | None = None) -> None:
        """
        Render an info message in cyan.

        Args:
            message: The info message
            title: Optional title
        """
        if title:
            self.console.print(f"[bold cyan]{title}:[/bold cyan] {message}")
        else:
            self.console.print(f"[cyan]ℹ[/cyan] {message}")

    def warning(self, message: str, title: str | None = None) -> None:
        """
        Render a warning message in yellow.

        Args:
            message: The warning message
            title: Optional title
        """
        if title:
            self.console.print(f"[bold yellow]{title}:[/bold yellow] {message}")
        else:
            self.console.print(f"[yellow]⚠[/yellow] {message}")

    def text(self, message: str, style: str | None = None) -> None:
        """
        Render plain text with optional style.

        Args:
            message: The text to render
            style: Optional Rich style string
        """
        if style:
            self.console.print(f"[{style}]{message}[/{style}]")
        else:
            self.console.print(message)

    def markdown(self, content: str, title: str | None = None) -> None:
        """
        Render markdown content.

        Args:
            content: Markdown content to render
            title: Optional title for the panel
        """
        md = Markdown(content)
        if title:
            self.console.print(Panel(md, title=title, border_style="blue"))
        else:
            self.console.print(md)

    def code(
        self, code: str, language: str = "python", title: str | None = None
    ) -> None:
        """
        Render syntax-highlighted code.

        Args:
            code: The code to render
            language: Programming language for syntax highlighting
            title: Optional title
        """
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        if title:
            self.console.print(Panel(syntax, title=title, border_style="blue"))
        else:
            self.console.print(syntax)

    def panel(
        self,
        content: str,
        title: str | None = None,
        border_style: str = "blue",
        style: str | None = None,
    ) -> None:
        """
        Render content in a panel.

        Args:
            content: Content to display
            title: Panel title
            border_style: Border color style
            style: Content style
        """
        self.console.print(Panel(content, title=title, border_style=border_style))

    def table(self, title: str, columns: list[str], rows: list[list[Any]]) -> None:
        """
        Render a table.

        Args:
            title: Table title
            columns: Column headers
            rows: Table rows
        """
        table = Table(title=title)

        for column in columns:
            table.add_column(column)

        for row in rows:
            table.add_row(*[str(cell) for cell in row])

        self.console.print(table)

    def clear(self) -> None:
        """Clear the console."""
        self.console.clear()

    def _truncate_tool_result(self, result: str) -> str:
        """
        Truncate tool result to the configured line limit.

        Args:
            result: The full tool result string

        Returns:
            Truncated result with message if truncated, otherwise original result
        """
        if not result:
            return result

        lines = result.splitlines()

        # If result is within limit, return as-is
        if len(lines) <= self.tool_result_line_limit:
            return result

        # Truncate to limit and add message
        truncated_lines = lines[:self.tool_result_line_limit]
        truncated_result = '\n'.join(truncated_lines)

        omitted_count = len(lines) - self.tool_result_line_limit
        truncation_message = f"\n\n[dim]... ({omitted_count} more lines omitted) [/dim]"

        return truncated_result + truncation_message

    def print(self, *args: Any, **kwargs: Any) -> None:
        """
        Direct access to console.print.

        Args:
            *args: Arguments to pass to console.print
            **kwargs: Keyword arguments to pass to console.print
        """
        self.console.print(*args, **kwargs)

    def _format_tool_details(self, tool_name: str, args: dict[str, Any]) -> str:
        """
        Format tool-specific details for display.
        
        Args:
            tool_name: Name of the tool
            args: Tool arguments
            
        Returns:
            Formatted details string
        """
        # Format details based on tool type
        if tool_name == "glob":
            pattern = args.get("pattern", "")
            path = args.get("path", ".")
            return f"[dim]→[/dim] Finding files matching [yellow]'{pattern}'[/yellow] in [blue]{path}[/blue]"
            
        elif tool_name == "grep":
            pattern = args.get("pattern", "")
            path = args.get("path", ".")
            return f"[dim]→[/dim] Searching for [yellow]'{pattern}'[/yellow] in [blue]{path}[/blue]"
            
        elif tool_name == "bash":
            command = args.get("command", "")
            # Truncate long commands
            display_cmd = command if len(command) < 60 else command[:57] + "..."
            return f"[dim]→[/dim] Running: [yellow]{display_cmd}[/yellow]"
            
        elif tool_name == "read":
            path = args.get("file_path", args.get("path", ""))
            return f"[dim]→[/dim] Reading [blue]{path}[/blue]"

        elif tool_name == "edit":
            path = args.get("file_path", args.get("path", ""))
            return f"[dim]→[/dim] Editing [blue]{path}[/blue]"

        elif tool_name == "write":
            path = args.get("file_path", args.get("path", ""))
            return f"[dim]→[/dim] Writing to [blue]{path}[/blue]"
            
        elif tool_name == "list":
            path = args.get("path", ".")
            return f"[dim]→[/dim] Listing directory [blue]{path}[/blue]"
            
        elif tool_name == "web_search":
            query = args.get("query", "")
            return f"[dim]→[/dim] Searching web for [yellow]'{query}'[/yellow]"
            
        elif tool_name == "web_fetch":
            url = args.get("url", "")
            # Truncate long URLs
            display_url = url if len(url) < 50 else url[:47] + "..."
            return f"[dim]→[/dim] Fetching [blue]{display_url}[/blue]"
            
        elif tool_name == "finish_task":
            reason = args.get("reason", "Task completed")
            return f"[dim]→[/dim] [green]{reason}[/green]"
            
        elif tool_name == "todo_read":
            return f"[dim]→[/dim] Reading current task list"
            
        else:
            # For unknown tools, try to show first couple args if available
            if args:
                first_key = list(args.keys())[0]
                first_val = str(args[first_key])
                if len(first_val) > 50:
                    first_val = first_val[:47] + "..."
                return f"[dim]→[/dim] {first_key}: [yellow]{first_val}[/yellow]"
            return ""



    def render_todo_list(self, todos: list[dict[str, Any]]) -> None:
        """
        Render a list of TODO items.

        Args:
            todos: List of todo items (dict with 'task' and 'status')
        """
        table = Table(title="Current Task List", box=None)
        table.add_column("Status", justify="center", style="bold")
        table.add_column("Task")

        for todo in todos:
            # key is 'content' in todo_write tool, not 'task'
            task = todo.get("content", todo.get("task", ""))
            status = todo.get("status", "pending")
            
            icon = "○"
            style = "dim"
            
            if status == "completed":
                icon = "✅"
                style = "green strike"
            elif status == "in_progress":
                icon = "⏳"
                style = "yellow"
            elif status == "pending":
                icon = "○"
                style = "white"

            table.add_row(icon, f"[{style}]{task}[/{style}]")

        self.console.print(table)
        self.console.print()

    def render_event(self, message: dict[str, Any]) -> None:
        """
        Render a message event based on its type.

        Args:
            message: The message dictionary containing 'type' and 'content' etc.
        """
        message_type = message.get("type", "Unknown")
        content = message.get("content", "")

        if message_type == "AssistantMessage":
            self.markdown(content, title="Agent")
        elif message_type == "AgentThought":
            # Display agent's thinking/reasoning
            self.console.print(f"[dim cyan]💭 Thinking:[/dim cyan] [italic]{content}[/italic]")
            self.console.print()  # Add spacing after thought
        elif message_type == "ToolCall":
            tool_name = message.get("tool_name", "unknown")
            args = message.get("arguments", {})
            
            # Special rendering for todo_write
            if tool_name == "todo_write" and "todos" in args:
                self.render_todo_list(args["todos"])
            else:
                # Show detailed tool information based on tool type
                details = self._format_tool_details(tool_name, args)
                if details:
                    self.console.print(f"[cyan]🔧 {tool_name}[/cyan] {details}")
                else:
                    self.info(content)

               
        elif message_type == "ToolResult":
            tool_name = message.get("tool_name", "unknown")
            result = message.get("result", "")
            status = message.get("status", "")

            # Log before rendering
            logger.debug(
                "Renderer displaying ToolResult: tool=%s, status=%s, result_len=%d",
                tool_name,
                status,
                len(result)
            )

            # Detailed log to dedicated tool result logger
            tool_result_logger.debug(
                "=== RENDERER DISPLAYING TOOL RESULT ===\n"
                f"Tool: {tool_name}\n"
                f"Status: {status}\n"
                f"Result Length: {len(result)}\n"
                f"Full Result:\n{result}\n"
                "======================================="
            )

            # Truncate tool results if they exceed the line limit
            truncated_result = self._truncate_tool_result(result)
            self.text(f"[dim]Tool '{tool_name}' result:[/dim] {truncated_result}")

            # Log after rendering
            logger.debug("Successfully displayed ToolResult in console")
            tool_result_logger.debug(
                f"=== TOOL RESULT DISPLAYED IN CONSOLE ===\n"
                f"Tool: {tool_name}\n"
                "========================================="
            )
        elif message_type == "Error":
            self.error(content)
        elif message_type == "UserMessage":
            # Usually user sees what they typed, but this can confirm receipt
            pass
        elif message_type == "AGENT_FINISHED":
            # Display the agent's finish message (summary)
            # AGENT_FINISHED uses "reason" field, not "content"
            finish_message = message.get("reason", content)
            if finish_message:
                self.console.print("\n[bold green]✅ All tasks completed[/bold green]\n")
                self.console.print(finish_message)
                self.console.print()
            else:
                self.success("Agent has completed the task.", title="Finished")
        elif message_type == "WAIT_FOR_USER_INPUT":
             self.warning(content or "The agent is waiting for your input.", title="Waiting for Input")
        else:
             self.text(f"[{message_type}] {content}")

class CodeReviewRenderer(OutputRenderer):
    """
    Specialized renderer for code review results.

    Extends OutputRenderer with methods for rendering structured code review
    output including verdict, statistics, comments, and recommendations.
    """

    def render_review_results(self, review_data: dict[str, Any]) -> None:
        """
        Render complete code review results with rich formatting.

        Args:
            review_data: Review result dictionary from CodeReviewAgent
        """
        # Render verdict and summary
        self._render_verdict(review_data)
        self.console.print()

        # Render statistics
        self._render_statistics(review_data)
        self.console.print()

        # Render comments by severity
        comments = review_data.get("comments", [])
        if comments:
            self._render_comments_by_severity(comments)
            self.console.print()
        else:
            self.success("No issues found! Code looks clean.", title="Review")
            self.console.print()

        # Render strengths
        strengths = review_data.get("strengths", [])
        if strengths:
            self._render_strengths(strengths)
            self.console.print()

        # Render recommendations
        recommendations = review_data.get("recommendations", [])
        if recommendations:
            self._render_recommendations(recommendations)
            self.console.print()

    def _render_verdict(self, review_data: dict[str, Any]) -> None:
        """Render the review verdict with appropriate color."""
        verdict = review_data.get("verdict", "UNKNOWN")
        summary = review_data.get("summary", "")

        # Color based on verdict
        if verdict == "APPROVE":
            color = "green"
            icon = "✅"
        elif verdict == "REQUEST_CHANGES":
            color = "red"
            icon = "❌"
        elif verdict == "COMMENT":
            color = "yellow"
            icon = "💬"
        else:
            color = "white"
            icon = "❓"

        # Create verdict panel
        verdict_text = f"[bold {color}]{icon} {verdict}[/bold {color}]\n\n{summary}"
        self.console.print(
            Panel(
                verdict_text,
                title="[bold]Code Review Verdict[/bold]",
                border_style=color,
                expand=False
            )
        )

    def _render_statistics(self, review_data: dict[str, Any]) -> None:
        """Render review statistics."""
        comments = review_data.get("comments", [])
        metadata = review_data.get("metadata", {})

        # Count by severity
        severity_counts = {
            "CRITICAL": 0,
            "MAJOR": 0,
            "MINOR": 0,
            "NIT": 0
        }

        files_affected = set()
        for comment in comments:
            severity = comment.get("severity", "UNKNOWN")
            if severity in severity_counts:
                severity_counts[severity] += 1
            file_path = comment.get("file", "")
            if file_path:
                files_affected.add(file_path)

        # Create statistics table
        table = Table(title="Review Statistics", box=None, show_header=False)
        table.add_column("Label", style="cyan")
        table.add_column("Value", style="bold")

        table.add_row("Files Reviewed", str(len(files_affected)))
        table.add_row("Total Comments", str(len(comments)))
        table.add_row("", "")  # Spacer

        if severity_counts["CRITICAL"] > 0:
            table.add_row("🔴 Critical", str(severity_counts["CRITICAL"]))
        if severity_counts["MAJOR"] > 0:
            table.add_row("🟠 Major", str(severity_counts["MAJOR"]))
        if severity_counts["MINOR"] > 0:
            table.add_row("🟡 Minor", str(severity_counts["MINOR"]))
        if severity_counts["NIT"] > 0:
            table.add_row("⚪ Nit", str(severity_counts["NIT"]))

        self.console.print(table)

    def _render_comments_by_severity(self, comments: list[dict[str, Any]]) -> None:
        """Render comments grouped by severity."""
        # Group by severity
        severity_order = ["CRITICAL", "MAJOR", "MINOR", "NIT"]
        severity_groups = {sev: [] for sev in severity_order}

        for comment in comments:
            severity = comment.get("severity", "UNKNOWN")
            if severity in severity_groups:
                severity_groups[severity].append(comment)

        # Render each severity group
        for severity in severity_order:
            group_comments = severity_groups[severity]
            if not group_comments:
                continue

            # Severity header
            severity_config = {
                "CRITICAL": ("🔴", "red", "Must Fix"),
                "MAJOR": ("🟠", "yellow", "Should Fix"),
                "MINOR": ("🟡", "blue", "Consider Fixing"),
                "NIT": ("⚪", "white", "Optional")
            }

            icon, color, label = severity_config.get(severity, ("", "white", ""))
            count = len(group_comments)

            self.console.print(
                f"\n[bold {color}]{icon} {severity}[/bold {color}] "
                f"[dim]({count} issue{'s' if count != 1 else ''} - {label})[/dim]"
            )
            self.console.print()

            # Group by file within severity
            files = {}
            for comment in group_comments:
                file_path = comment.get("file", "unknown")
                if file_path not in files:
                    files[file_path] = []
                files[file_path].append(comment)

            # Render comments by file
            for file_path in sorted(files.keys()):
                self.console.print(f"  [bold cyan]📄 {file_path}[/bold cyan]")

                for comment in files[file_path]:
                    self._render_inline_comment(comment, indent="    ")

    def _render_inline_comment(self, comment: dict[str, Any], indent: str = "") -> None:
        """
        Render a single inline comment.

        Args:
            comment: Comment dictionary
            indent: Indentation string
        """
        line = comment.get("line", "?")
        category = comment.get("category", "general")
        issue = comment.get("issue", "")
        suggestion = comment.get("suggestion", "")
        code_example = comment.get("code_example", "")

        # Line and category
        self.console.print(
            f"{indent}[bold]Line {line}[/bold] [dim]({category})[/dim]"
        )

        # Issue
        self.console.print(f"{indent}[red]Issue:[/red] {issue}")

        # Suggestion
        if suggestion:
            self.console.print(f"{indent}[green]Fix:[/green] {suggestion}")

        # Code example
        if code_example:
            # Try to determine language from file extension in comment
            language = "python"  # Default
            file_path = comment.get("file", "")
            if file_path.endswith(".js") or file_path.endswith(".ts"):
                language = "javascript"
            elif file_path.endswith(".java"):
                language = "java"
            elif file_path.endswith(".go"):
                language = "go"
            elif file_path.endswith(".rs"):
                language = "rust"

            syntax = Syntax(
                code_example,
                language,
                theme="monokai",
                line_numbers=False,
                background_color="default"
            )
            self.console.print(f"{indent}[green]Example:[/green]")
            self.console.print(syntax)

        self.console.print()  # Blank line between comments

    def _render_strengths(self, strengths: list[str]) -> None:
        """Render code strengths."""
        self.console.print("[bold green]✨ Strengths[/bold green]")
        self.console.print()

        for strength in strengths:
            self.console.print(f"  [green]✓[/green] {strength}")

    def _render_recommendations(self, recommendations: list[dict[str, Any]]) -> None:
        """Render recommendations grouped by priority."""
        self.console.print("[bold blue]📋 Recommendations[/bold blue]")
        self.console.print()

        # Group by priority
        priority_groups = {"HIGH": [], "MEDIUM": [], "LOW": []}

        for rec in recommendations:
            priority = rec.get("priority", "LOW")
            if priority in priority_groups:
                priority_groups[priority].append(rec)

        # Render each priority group
        for priority in ["HIGH", "MEDIUM", "LOW"]:
            group_recs = priority_groups[priority]
            if not group_recs:
                continue

            # Priority config
            priority_config = {
                "HIGH": ("🔴", "red"),
                "MEDIUM": ("🟡", "yellow"),
                "LOW": ("🟢", "green")
            }

            icon, color = priority_config.get(priority, ("", "white"))

            self.console.print(f"  [{color}]{icon} {priority} Priority[/{color}]")

            for rec in group_recs:
                item = rec.get("item", "")
                self.console.print(f"    • {item}")

            self.console.print()


# Global renderer instance
renderer = OutputRenderer()
