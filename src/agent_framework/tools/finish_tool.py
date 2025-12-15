"""Tool for signaling task completion."""
from typing import Dict
from .tool_base import BaseTool, ToolResult

class FinishAction(BaseTool):
    """Tool for the agent to signal that it has finished the task.
    
    This tool should be called when the agent has completed all the objectives
    in its plan and verified the results.
    """
    
    name: str = "finish_task"
    description: str = (
        "Signals that the agent has finished the task. "
        "Call this ONLY when all todo items are completed and verified."
    )
    
    parameters: Dict = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "The reason for finishing (e.g., 'All tasks completed successfully')."
            },
            "result": {
                "type": "string",
                "description": "Optional detailed result or summary to display to the user (e.g., statistics, key findings, output location)."
            }
        },
        "required": ["reason"]
    }

    async def execute(self, reason: str, result: str = "") -> ToolResult:
        """Execute the finish action.

        Args:
            reason: The reason for finishing.
            result: Optional detailed result or summary.

        Returns:
            ToolResult: A confirmation message.
        """
        # The actual handling of this tool call (creating AgentFinishedMessage)
        # happens in the agent integration layer or controller.
        # This execution just returns a polite confirmation for the history.
        if result:
            return ToolResult(
                output=f"Task marked as finished. Reason: {reason}\nResult: {result}"
            )
        return ToolResult(
            output=f"Task marked as finished. Reason: {reason}"
        )
