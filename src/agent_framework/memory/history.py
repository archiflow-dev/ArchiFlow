"""
History Manager with Selective Retention compaction strategy.
"""
import logging
from typing import List, Optional, Callable, Dict, Any
import json

from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, ToolCallMessage,
    ToolResultObservation, BatchToolResultObservation,
    AgentFinishedMessage, EnvironmentMessage, LLMRespondMessage
)
from .summarizer import HistorySummarizer, SimpleSummarizer
from ..llm.model_config import ModelConfig

logger = logging.getLogger(__name__)

class HistoryManager:
    """
    Manages conversation history with token-aware compaction.
    
    Strategy: Selective Retention (Anchor Method)
    1. Always keep System Prompt (usually first message)
    2. Always keep Initial User Request (Goal)
    3. Keep Last N messages (Working Context)
    4. Summarize or drop the middle
    """
    
    def __init__(
        self,
        summarizer: HistorySummarizer,
        model_config: Optional[ModelConfig] = None,
        system_prompt_tokens: int = 0,
        tools_tokens: int = 0,
        retention_window: int = 10,
        buffer_tokens: int = 500,
        max_tokens: Optional[int] = None,
        auto_remove_old_todos: bool = True
    ):
        """
        Initialize HistoryManager with model-aware token limits.

        Args:
            summarizer: HistorySummarizer instance (REQUIRED).
            model_config: ModelConfig for the LLM being used. If provided,
                         max_tokens is calculated automatically.
            system_prompt_tokens: Estimated tokens in system prompt.
            tools_tokens: Estimated tokens in tool definitions.
            retention_window: Number of recent messages to keep.
            buffer_tokens: Safety buffer for token counting errors.
            max_tokens: Override calculated max_tokens if provided.
                       If both model_config and max_tokens are None,
                       defaults to 4000 (conservative).
            auto_remove_old_todos: If True, automatically remove old TODO messages
                                  when new TODO messages are added. Reduces token
                                  usage by keeping only the current TODO state.
                                  Default: True.
        """
        if summarizer is None:
            raise ValueError(
                "summarizer is required. Use LLMSummarizer(llm) for intelligent summaries "
                "or SimpleSummarizer() for basic summaries."
            )

        self.summarizer = summarizer
        self.retention_window = retention_window
        self.auto_remove_old_todos = auto_remove_old_todos

        # Calculate max tokens based on model config or use override
        if max_tokens is not None:
            self.max_tokens = max_tokens
            logger.info(f"HistoryManager using explicit max_tokens={max_tokens}")
        elif model_config is not None:
            self.max_tokens = model_config.get_available_context(
                system_prompt_tokens=system_prompt_tokens,
                tools_tokens=tools_tokens,
                buffer_tokens=buffer_tokens
            )
            logger.info(
                f"HistoryManager calculated max_tokens={self.max_tokens} "
                f"(model={model_config.model_name}, context={model_config.context_window}, "
                f"system={system_prompt_tokens}, tools={tools_tokens}, buffer={buffer_tokens})"
            )
        else:
            self.max_tokens = 4000
            logger.warning(
                "No model_config or max_tokens provided, using default max_tokens=4000. "
                "Consider providing model_config for optimal token management."
            )

        self._messages: List[BaseMessage] = []
        self.summary_message: Optional[SystemMessage] = None
        
    def add(self, message: BaseMessage) -> None:
        """Add a message to history and trigger compaction if needed."""
        # If this is a new TODO message and auto-removal is enabled, remove old TODOs
        if self.auto_remove_old_todos and self._is_new_todo_message(message):
            self._remove_previous_todos()

        self._messages.append(message)

        # Check compaction
        current_tokens = self.get_token_estimate()
        utilization = (current_tokens / self.max_tokens) * 100 if self.max_tokens > 0 else 0

        logger.debug(
            f"History: {len(self._messages)} messages, "
            f"{current_tokens}/{self.max_tokens} tokens ({utilization:.1f}%)"
        )

        if current_tokens > self.max_tokens:
            logger.info(
                f"Triggering compaction: {current_tokens} tokens > {self.max_tokens} limit"
            )
            self.compact()
            
    def get_messages(self) -> List[BaseMessage]:
        """Get the current effective list of messages."""
        return self.messages
        
    @property
    def messages(self) -> List[BaseMessage]:
        """Backward-compatible property to access internal messages list."""
        return self._messages
        
    def get_token_estimate(self) -> int:
        """
        Rough estimate of token count.
        Approximation: 1 token ~= 4 chars.
        """
        total_chars = 0
        for msg in self._messages:
            # Estimate based on content and other fields
            content = ""
            if hasattr(msg, 'content') and msg.content:
                content += str(msg.content)
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                content += str(msg.tool_calls)
            
            total_chars += len(content)
            
        return total_chars // 4
        
    def compact(self) -> None:
        """
        Execute compaction strategy.
        
        Preserves:
        - System Message (if at index 0)
        - First User Message (Goal)
        - Last N messages
        
        Summarizes/Drops:
        - The middle chunk
        """
        if len(self._messages) <= self.retention_window + 2:
            return

        logger.info("Compacting history (current size: %d, tokens: %d)", 
                    len(self._messages), self.get_token_estimate())
        
        preserved_head = []
        preserved_tail = []
        middle_chunk = []
        
        # 1. Identify Head (System + Goal)
        idx = 0
        # Keep first SystemMessage if present
        if idx < len(self._messages) and isinstance(self._messages[idx], SystemMessage):
            preserved_head.append(self._messages[idx])
            idx += 1
            
        # Keep first UserMessage (Goal) if present
        # We scan a bit forward to find the first user message
        found_goal = False
        temp_idx = idx
        while temp_idx < len(self._messages) and temp_idx < 5: # Look in first 5 messages
            if isinstance(self._messages[temp_idx], UserMessage):
                if temp_idx > idx:
                     # If we skipped some messages to find user message, decide if we keep them.
                     # For strict "Anchor", maybe we just grab the UserMessage.
                     # Let's just grab the UserMessage and whatever was before it.
                     pass
                preserved_head.extend(self._messages[idx:temp_idx+1])
                idx = temp_idx + 1
                found_goal = True
                break
            temp_idx += 1
            
        if not found_goal:
            # If no user message found early, just keep the first few as head
            end_head = min(idx + 1, len(self._messages))
            preserved_head.extend(self._messages[idx:end_head])
            idx = end_head
            
        # 2. Identify Tail (Last N)
        tail_start = max(idx, len(self._messages) - self.retention_window)
        preserved_tail = self._messages[tail_start:]

        # 2.5. Extend tail backwards to include tool_calls for any tool results in tail
        # This prevents orphaned tool results (tool results without their tool_calls)
        call_ids_needed = set()

        # Collect all tool_call_ids referenced by tool results in the tail
        for msg in preserved_tail:
            if isinstance(msg, ToolResultObservation):
                call_ids_needed.add(msg.call_id)
            elif isinstance(msg, BatchToolResultObservation):
                for result in msg.results:
                    call_ids_needed.add(result.call_id)

        # Walk backwards from tail_start to find messages with needed tool_calls
        if call_ids_needed:
            extended_start = tail_start
            for i in range(tail_start - 1, idx - 1, -1):
                msg = self._messages[i]
                if isinstance(msg, ToolCallMessage):
                    # Check if this message has any of the needed tool calls
                    has_needed_call = any(tc.id in call_ids_needed for tc in msg.tool_calls)
                    if has_needed_call:
                        extended_start = i
                        # Remove the call_ids we found
                        for tc in msg.tool_calls:
                            call_ids_needed.discard(tc.id)

                        # If we found all needed calls, we can stop
                        if not call_ids_needed:
                            break

            # Update tail to include the extended range
            if extended_start < tail_start:
                preserved_tail = self._messages[extended_start:]
                tail_start = extended_start

        # 3. Identify Middle
        if tail_start > idx:
            middle_chunk = self._messages[idx:tail_start]
            
        if not middle_chunk:
            return

        # 4. Summarize Middle using the summarizer
        summary_text = self.summarizer.summarize(middle_chunk)
        logger.info(f"Generated summary: {summary_text[:100]}...")

        # Create summary message
        summary_msg = SystemMessage(
            content=summary_text,
            session_id=self._messages[0].session_id if self._messages else "unknown",
            sequence=0
        )
        
        # Reconstruct messages
        self._messages = preserved_head + [summary_msg] + preserved_tail
        
        logger.info("Compaction complete. New size: %d", len(self._messages))

    def _is_new_todo_message(self, message: BaseMessage) -> bool:
        """
        Check if the message is a new TODO tool result.

        Args:
            message: Message to check

        Returns:
            True if this is a ToolResultObservation for a todo_write call
        """
        if not isinstance(message, ToolResultObservation):
            return False

        # Search backwards to find the corresponding tool_call
        for i in range(len(self._messages) - 1, -1, -1):
            msg = self._messages[i]
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.id == message.call_id and tc.tool_name == "todo_write":
                        return True

        return False

    def _is_todo_related_message(self, msg: BaseMessage, idx: int) -> bool:
        """
        Check if a message is related to TODO (either a tool_call or tool_result).

        Args:
            msg: Message to check
            idx: Index of the message in self._messages

        Returns:
            True if the message is a todo_write call or its result
        """
        # Check if it's a ToolCallMessage with todo_write
        if isinstance(msg, ToolCallMessage):
            return any(tc.tool_name == "todo_write" for tc in msg.tool_calls)

        # Check if it's a ToolResultObservation for a todo_write call
        if isinstance(msg, ToolResultObservation):
            # Search backwards for the corresponding tool_call
            for i in range(idx - 1, -1, -1):
                if isinstance(self._messages[i], ToolCallMessage):
                    for tc in self._messages[i].tool_calls:
                        if tc.id == msg.call_id and tc.tool_name == "todo_write":
                            return True

        return False

    def _remove_previous_todos(self) -> None:
        """
        Remove all previous TODO-related messages (both tool_calls and results).
        Respects the retention window - only removes TODOs outside of it.

        This is called when a new TODO message is being added to prevent
        accumulation of obsolete TODO states in the conversation history.
        """
        if len(self._messages) == 0:
            return

        # Find all TODO-related message indices
        todo_indices = []
        for i, msg in enumerate(self._messages):
            if self._is_todo_related_message(msg, i):
                todo_indices.append(i)

        if len(todo_indices) == 0:
            return

        # Calculate retention boundary
        # Only remove messages outside the retention window
        retention_start = max(0, len(self._messages) - self.retention_window)

        # Remove TODO messages that are outside the retention window
        # We keep messages in the retention window to maintain recent context
        removed_count = 0
        for idx in reversed(todo_indices):
            if idx < retention_start:
                del self._messages[idx]
                removed_count += 1

        if removed_count > 0:
            logger.info(
                f"Removed {removed_count} old TODO message(s) from history "
                f"(kept {len(todo_indices) - removed_count} in retention window)"
            )

    def to_llm_format(self) -> List[Dict[str, Any]]:
        """Convert to LLM format (delegates to existing logic or implements here)."""
        # Re-using the logic from the original ConversationHistory for consistency
        # Or we can import it. Let's implement a simple version here for independence
        # or better yet, adapt the one from agents/history.py
        
        llm_messages = []
        for msg in self._messages:
            role = None
            content = ""
            tool_calls = None
            tool_call_id = None
            
            if isinstance(msg, UserMessage):
                role = "user"
                content = msg.content
            elif isinstance(msg, SystemMessage):
                role = "system"
                content = msg.content
            elif isinstance(msg, EnvironmentMessage):
                role = "user"
                content = f"[Environment: {msg.event_type}] {msg.content}"
            elif isinstance(msg, ToolCallMessage):
                role = "assistant"
                tool_calls = []
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments)
                        }
                    })
            elif isinstance(msg, ToolResultObservation):
                role = "tool"
                tool_call_id = msg.call_id
                content = msg.content
            elif isinstance(msg, LLMRespondMessage):
                role = "assistant"
                content = msg.content
            elif isinstance(msg, BatchToolResultObservation):
                 # Batch results might need to be split or handled as multiple tool messages
                 # For OpenAI, each tool result is a separate message
                 for result in msg.results:
                     llm_messages.append({
                         "role": "tool",
                         "tool_call_id": result.call_id,
                         "content": result.content
                     })
                 continue # Skip the main append
            else:
                role = "assistant"
                content = msg.content
            
            if role is not None:
                msg_dict = {"role": role}
                if content is not None:
                    msg_dict["content"] = content
                if tool_calls is not None:
                    msg_dict["tool_calls"] = tool_calls
                if tool_call_id is not None:
                    msg_dict["tool_call_id"] = tool_call_id
                llm_messages.append(msg_dict)
            else:
                logger.error(f"Message not in any of the User, System , Toolcall, Environment, ToolResult type. msg: {msg}")
            
        return llm_messages
