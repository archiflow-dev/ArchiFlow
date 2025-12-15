"""
Message formats for runtime execution via MessageBroker.

This module defines the message formats used for pub/sub communication
between agents and the runtime system.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.result import ToolResult


@dataclass
class ToolCallRequest:
    """
    Message for requesting tool execution via MessageBroker.
    
    Published to 'tool.call.request' topic.
    """
    
    call_id: str
    """Unique identifier for this call (for matching request/response)."""
    
    session_id: str
    """Session ID for the agent making the request."""
    
    tool_name: str
    """Name of the tool to execute."""
    
    parameters: Dict[str, Any]
    """Parameters to pass to the tool."""
    
    context: Dict[str, Any]
    """Execution context as dictionary."""
    
    reply_topic: str = "tool.call.result"
    """Topic to publish the result to."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCallRequest":
        """Create from dictionary."""
        return cls(**data)
    
    @classmethod
    def create(
        cls,
        call_id: str,
        session_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext,
        reply_topic: str = "tool.call.result"
    ) -> "ToolCallRequest":
        """
        Create a tool call request from an ExecutionContext.
        
        Args:
            call_id: Unique call identifier
            session_id: Session identifier
            tool_name: Name of the tool
            parameters: Tool parameters
            context: Execution context
            reply_topic: Topic for the response
            
        Returns:
            ToolCallRequest instance
        """
        return cls(
            call_id=call_id,
            session_id=session_id,
            tool_name=tool_name,
            parameters=parameters,
            context={
                'session_id': context.session_id,
                'timeout': context.timeout,
                'max_memory_mb': context.max_memory_mb,
                'max_cpu_percent': context.max_cpu_percent,
                'allowed_network': context.allowed_network,
                'working_directory': context.working_directory,
                'environment': context.environment,
                'metadata': context.metadata,
            },
            reply_topic=reply_topic
        )


@dataclass
class BatchToolCallRequest:
    """
    Message for requesting batch tool execution via MessageBroker.
    
    Published to 'tool.call.batch.request' topic or runtime topic.
    """
    
    batch_id: str
    """Unique identifier for this batch."""
    
    session_id: str
    """Session ID for the agent making the request."""
    
    tool_calls: List[ToolCallRequest]
    """List of tool call requests."""
    
    context: Dict[str, Any]
    """Shared execution context as dictionary."""
    
    reply_topic: str = "tool.call.batch.result"
    """Topic to publish the result to."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['tool_calls'] = [tc.to_dict() for tc in self.tool_calls]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchToolCallRequest":
        """Create from dictionary."""
        tool_calls_data = data.pop('tool_calls', [])
        tool_calls = [ToolCallRequest.from_dict(tc) for tc in tool_calls_data]
        return cls(tool_calls=tool_calls, **data)
    
    @classmethod
    def create(
        cls,
        batch_id: str,
        session_id: str,
        tool_calls: List[ToolCallRequest],
        context: ExecutionContext,
        reply_topic: str = "tool.call.batch.result"
    ) -> "BatchToolCallRequest":
        """Create a batch tool call request."""
        return cls(
            batch_id=batch_id,
            session_id=session_id,
            tool_calls=tool_calls,
            context={
                'session_id': context.session_id,
                'timeout': context.timeout,
                'max_memory_mb': context.max_memory_mb,
                'max_cpu_percent': context.max_cpu_percent,
                'allowed_network': context.allowed_network,
                'working_directory': context.working_directory,
                'environment': context.environment,
                'metadata': context.metadata,
            },
            reply_topic=reply_topic
        )


@dataclass
class ToolCallResult:
    """
    Message for tool execution result via MessageBroker.
    
    Published to 'tool.call.result' topic (or custom reply_topic).
    """
    
    call_id: str
    """Matches the request call_id."""
    
    session_id: str
    """Session ID from the request."""
    
    tool_name: str
    """Name of the tool that was executed."""
    
    result: Dict[str, Any]
    """Tool result as dictionary."""
    
    execution_time_ms: int
    """Execution time in milliseconds."""
    
    runtime_used: str
    """Which runtime executed the tool."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCallResult":
        """Create from dictionary."""
        return cls(**data)
    
    @classmethod
    def create(
        cls,
        call_id: str,
        session_id: str,
        tool_name: str,
        result: ToolResult,
        runtime_used: str
    ) -> "ToolCallResult":
        """
        Create a tool call result from a ToolResult.
        
        Args:
            call_id: Unique call identifier (from request)
            session_id: Session identifier
            tool_name: Name of the tool
            result: Tool execution result
            runtime_used: Name of the runtime that executed the tool
            
        Returns:
            ToolCallResult instance
        """
        return cls(
            call_id=call_id,
            session_id=session_id,
            tool_name=tool_name,
            result={
                'success': result.success,
                'output': result.output,
                'error': result.error,
                'execution_time': result.execution_time,
                'metadata': result.metadata,
            },
            execution_time_ms=int(result.execution_time * 1000),
            runtime_used=runtime_used
        )
    
    def get_tool_result(self) -> ToolResult:
        """
        Convert back to ToolResult.
        
        Returns:
            ToolResult instance
        """
        return ToolResult(
            success=self.result['success'],
            output=self.result.get('output'),
            error=self.result.get('error'),
            execution_time=self.result.get('execution_time', 0.0),
            metadata=self.result.get('metadata', {}),
        )
