"""
Test that history compaction properly handles tool calls and tool results.
"""
import pytest
from src.agent_framework.memory.history import HistoryManager
from src.agent_framework.memory.summarizer import SimpleSummarizer
from src.agent_framework.messages.types import (
    SystemMessage, UserMessage, ToolCallMessage, ToolResultObservation, ToolCall
)


def test_compaction_preserves_tool_call_for_tool_result():
    """
    Test that when compacting, if a tool result is in the tail,
    its corresponding tool call is also preserved (not compacted away).

    This prevents the OpenAI API error:
    "messages with role 'tool' must be a response to a preceeding message with 'tool_calls'"
    """
    history = HistoryManager(
        max_tokens=50,  # Low to force compaction
        retention_window=3,  # Keep last 3 messages
        summarizer=SimpleSummarizer()
    )

    # 1. System Message (Head)
    history.add(SystemMessage(content="System Prompt", session_id="test", sequence=0))

    # 2. User Goal (Head)
    history.add(UserMessage(content="Do task", session_id="test", sequence=1))

    # 3-7. Middle messages that will be compacted
    for i in range(5):
        history.add(UserMessage(content=f"Middle {i}", session_id="test", sequence=2+i))

    # 8. Tool call message (should be preserved because result is in tail)
    tool_call_msg = ToolCallMessage(
        session_id="test",
        sequence=7,
        tool_calls=[
            ToolCall(id="call_123", tool_name="write", arguments={"file": "test.py"})
        ]
    )
    history.add(tool_call_msg)

    # 9. Tool result (in tail)
    tool_result_msg = ToolResultObservation(
        session_id="test",
        sequence=8,
        call_id="call_123",
        content="File written successfully"
    )
    history.add(tool_result_msg)

    # 10. Another message (in tail)
    history.add(UserMessage(content="Tail message", session_id="test", sequence=9))

    # Force compaction
    history.compact()

    msgs = history.get_messages()

    # Verify structure
    # Expected: [System, Goal, Summary, ToolCall, ToolResult, UserMessage]

    # Find the tool call and tool result
    tool_call_indices = [i for i, m in enumerate(msgs) if isinstance(m, ToolCallMessage)]
    tool_result_indices = [i for i, m in enumerate(msgs) if isinstance(m, ToolResultObservation)]

    assert len(tool_call_indices) == 1, "Should have exactly one tool call message"
    assert len(tool_result_indices) == 1, "Should have exactly one tool result message"

    tool_call_idx = tool_call_indices[0]
    tool_result_idx = tool_result_indices[0]

    # The tool call must come BEFORE the tool result
    assert tool_call_idx < tool_result_idx, "Tool call must precede tool result"

    # The tool call and result should reference the same call_id
    preserved_tool_call = msgs[tool_call_idx]
    preserved_tool_result = msgs[tool_result_idx]

    call_ids = [tc.id for tc in preserved_tool_call.tool_calls]
    assert preserved_tool_result.call_id in call_ids, "Tool result must reference a call_id from the tool call"

    print(f"✓ Compaction preserved tool call-result pair correctly")
    print(f"  Messages: {len(msgs)}")
    print(f"  Tool call at index {tool_call_idx}, result at index {tool_result_idx}")


def test_compaction_with_multiple_tool_pairs():
    """
    Test compaction with multiple tool call/result pairs in the tail.
    """
    history = HistoryManager(
        max_tokens=50,
        retention_window=6,
        summarizer=SimpleSummarizer()
    )

    # Head
    history.add(SystemMessage(content="System", session_id="test", sequence=0))
    history.add(UserMessage(content="Goal", session_id="test", sequence=1))

    # Middle (will be compacted)
    for i in range(5):
        history.add(UserMessage(content=f"Middle {i}", session_id="test", sequence=2+i))

    # Tool pair 1 (should be preserved)
    history.add(ToolCallMessage(
        session_id="test",
        sequence=7,
        tool_calls=[ToolCall(id="call_A", tool_name="read", arguments={})]
    ))
    history.add(ToolResultObservation(
        session_id="test",
        sequence=8,
        call_id="call_A",
        content="File contents"
    ))

    # Tool pair 2 (should be preserved)
    history.add(ToolCallMessage(
        session_id="test",
        sequence=9,
        tool_calls=[ToolCall(id="call_B", tool_name="write", arguments={})]
    ))
    history.add(ToolResultObservation(
        session_id="test",
        sequence=10,
        call_id="call_B",
        content="File written"
    ))

    history.compact()

    msgs = history.get_messages()

    # Verify both tool call messages are present
    tool_calls = [m for m in msgs if isinstance(m, ToolCallMessage)]
    tool_results = [m for m in msgs if isinstance(m, ToolResultObservation)]

    assert len(tool_calls) == 2, "Should preserve both tool call messages"
    assert len(tool_results) == 2, "Should preserve both tool result messages"

    # Verify they're in correct order
    call_ids_in_order = []
    result_ids_in_order = []

    for msg in msgs:
        if isinstance(msg, ToolCallMessage):
            call_ids_in_order.extend([tc.id for tc in msg.tool_calls])
        elif isinstance(msg, ToolResultObservation):
            result_ids_in_order.append(msg.call_id)

    # Each result should have had its call appear before it
    for result_id in result_ids_in_order:
        assert result_id in call_ids_in_order, f"Result {result_id} missing its tool call"

    print(f"✓ Multiple tool pairs preserved correctly")


def test_llm_format_valid_after_compaction():
    """
    Test that the LLM format is valid after compaction (no orphaned tool results).
    """
    history = HistoryManager(
        max_tokens=50,
        retention_window=3,
        summarizer=SimpleSummarizer()
    )

    # Create a scenario similar to the error log
    history.add(SystemMessage(content="System", session_id="test", sequence=0))
    history.add(UserMessage(content="Task", session_id="test", sequence=1))

    # Middle
    for i in range(10):
        history.add(UserMessage(content=f"M{i}", session_id="test", sequence=2+i))

    # Tool call + result (in tail)
    history.add(ToolCallMessage(
        session_id="test",
        sequence=12,
        tool_calls=[ToolCall(id="call_XYZ", tool_name="bash", arguments={})]
    ))
    history.add(ToolResultObservation(
        session_id="test",
        sequence=13,
        call_id="call_XYZ",
        content="Command output"
    ))

    history.compact()

    # Convert to LLM format
    llm_messages = history.to_llm_format()

    # Validate: every 'tool' role message must be preceded by an 'assistant' message with 'tool_calls'
    for i, msg in enumerate(llm_messages):
        if msg.get("role") == "tool":
            # Find the preceding assistant message with tool_calls
            found_tool_call = False
            tool_call_id = msg.get("tool_call_id")

            for j in range(i - 1, -1, -1):
                prev_msg = llm_messages[j]
                if prev_msg.get("role") == "assistant" and prev_msg.get("tool_calls"):
                    # Check if any tool call has the matching ID
                    for tc in prev_msg["tool_calls"]:
                        if tc.get("id") == tool_call_id:
                            found_tool_call = True
                            break
                    if found_tool_call:
                        break

            assert found_tool_call, f"Tool result with call_id={tool_call_id} has no preceding tool call"

    print(f"✓ LLM format valid after compaction (no orphaned tool results)")


if __name__ == "__main__":
    test_compaction_preserves_tool_call_for_tool_result()
    test_compaction_with_multiple_tool_pairs()
    test_llm_format_valid_after_compaction()
    print("\n✅ All tool call/result compaction tests passed!")
