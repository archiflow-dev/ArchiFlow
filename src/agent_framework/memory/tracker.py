"""
Environment Tracker for Agent Memory.
"""
import os
from typing import List, Set, Dict, Any, Optional

class EnvironmentTracker:
    """
    Tracks the agent's environment state (CWD, files).
    """
    
    def __init__(self):
        self.cwd: str = os.getcwd()
        self.recent_files: Set[str] = set()
        self.max_recent_files: int = 5
        
    def update(self, tool_name: str, tool_args: Dict[str, Any], tool_result: Any) -> None:
        """
        Update state based on tool execution.
        
        Args:
            tool_name: Name of the tool executed.
            tool_args: Arguments passed to the tool.
            tool_result: Result of the tool execution.
        """
        # Track CWD changes
        if tool_name in ["change_directory", "cd"]:
            path = tool_args.get("path")
            if path:
                # In a real scenario, we'd verify success from tool_result
                # For now, assume success if no error in result string (simplification)
                if isinstance(tool_result, str) and "Error" not in tool_result:
                    self.cwd = path
                elif hasattr(tool_result, "success") and tool_result.success:
                     self.cwd = path

        # Track file interactions
        if tool_name in ["read_file", "write_file", "edit_file"]:
            path = tool_args.get("path") or tool_args.get("target_file")
            if path:
                self._add_recent_file(path)
                
    def _add_recent_file(self, path: str) -> None:
        """Add a file to the recent list, maintaining size limit."""
        if path in self.recent_files:
            return
            
        self.recent_files.add(path)
        if len(self.recent_files) > self.max_recent_files:
            # Remove an arbitrary element (set is unordered)
            # Ideally we'd use an OrderedDict or list for LRU
            self.recent_files.pop()
            
    def get_summary(self) -> str:
        """Get a formatted summary of the environment state."""
        summary = [
            "## Environment State",
            f"- Current Working Directory: `{self.cwd}`"
        ]
        
        if self.recent_files:
            files_str = ", ".join([f"`{f}`" for f in self.recent_files])
            summary.append(f"- Recently Accessed Files: {files_str}")
            
        return "\n".join(summary)
