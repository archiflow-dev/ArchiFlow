"""
Runtime executor for handling tool execution via MessageBroker.

This module provides the RuntimeExecutor class that subscribes to
tool execution requests and publishes results via the message broker.
"""

import asyncio
import logging
import time
import uuid
from typing import Optional

from message_queue.broker import MessageBroker
from message_queue.message import Message

# Special logger for tool results
tool_result_logger = logging.getLogger("tool_results")

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.exceptions import ToolNotFoundError
from agent_framework.runtime.manager import RuntimeManager
from agent_framework.runtime.messages import ToolCallRequest, ToolCallResult
from agent_framework.runtime.result import ToolResult

logger = logging.getLogger(__name__)


class RuntimeExecutor:
    """
    Executes tools via MessageBroker pub/sub.
    
    Subscribes to 'tool.call.request' topic and publishes results
    to 'tool.call.result' topic.
    """
    
    def __init__(
        self,
        broker: MessageBroker,
        runtime_manager: RuntimeManager,
        tool_registry: Optional["ToolRegistry"] = None,
        context: Optional["TopicContext"] = None,
    ):
        """
        Initialize the runtime executor.
        
        Args:
            broker: Message broker for pub/sub
            runtime_manager: Runtime manager for tool execution
            tool_registry: Optional tool registry for tool lookup
            context: Optional topic context for agent communication
        """
        self.broker = broker
        self.runtime_manager = runtime_manager
        self.tool_registry = tool_registry
        self.context = context
        self._running = False
        
        logger.info("RuntimeExecutor initialized")
    
    def _get_tool(self, tool_name: str) -> Optional[Any]:
        """Get tool from registry."""
        if not self.tool_registry:
            return None
        return self.tool_registry.get(tool_name)
    
    def start(self) -> None:
        """Start listening for tool call requests."""
        if self._running:
            logger.warning("RuntimeExecutor already running")
            return
        
        if not self.context:
            raise ValueError("TopicContext is required to start RuntimeExecutor")
            
        # Subscribe ONLY to the runtime topic defined in context
        self.broker.subscribe(self.context.runtime_topic, self._on_tool_call_request)
        self._running = True
        
        logger.info("RuntimeExecutor started, listening on '%s'", self.context.runtime_topic)
    
    def stop(self) -> None:
        """Stop listening for requests."""
        if not self._running:
            return
        
        if self.context:
            self.broker.unsubscribe(self.context.runtime_topic, self._on_tool_call_request)
            
        self._running = False
        logger.info("RuntimeExecutor stopped")
    
    async def _on_tool_call_request(self, message: Message) -> None:
        """
        Handle incoming tool call request (Single or Batch).
        
        Args:
            message: Message containing ToolCallRequest or BatchToolCallRequest
        """
        try:
            payload = message.payload
            # Check if it's a batch request
            if 'tool_calls' in payload:
                await self._handle_batch_request(message)
                return

            # ... existing single request handling ...
            # Parse request
            # We expect the payload to match ToolCallRequest structure
            request = ToolCallRequest.from_dict(message.payload)
            
            # ... (rest of single request handling) ...
            logger.info(
                "Received tool call request: call_id=%s, tool=%s, session=%s",
                request.call_id,
                request.tool_name,
                request.session_id
            )
            
            # Get tool
            tool = self._get_tool(request.tool_name)
            
            if tool is None:
                # Tool not found
                result = ToolCallResult.create(
                    call_id=request.call_id,
                    session_id=request.session_id,
                    tool_name=request.tool_name,
                    result=ToolResult.error_result(
                        error=f"Tool not found: {request.tool_name}"
                    ),
                    runtime_used="none"
                )
                # Publish to agent topic from context
                self.broker.publish(self.context.agent_topic, result.to_dict())
                return
            
            # Parse execution context
            context = ExecutionContext(**request.context)
            
            # Execute via runtime manager
            start_time = time.time()
            try:
                tool_result = await self.runtime_manager.execute_tool(
                    tool,
                    request.parameters,
                    context
                )
            except Exception as e:
                # Execution failed
                logger.error(
                    "Tool execution failed: call_id=%s, error=%s",
                    request.call_id,
                    str(e),
                    exc_info=True
                )
                tool_result = ToolResult.error_result(
                    error=f"Execution failed: {str(e)}",
                    execution_time=time.time() - start_time
                )
            
            # Publish result
            # Use ToolResultObservation directly for agent topics
            from agent_framework.messages.types import ToolResultObservation
            
            observation = ToolResultObservation(
                session_id=request.session_id,
                sequence=0,
                call_id=request.call_id,
                content=tool_result.output if tool_result.success else f"Error: {tool_result.error}",
                status="success" if tool_result.success else "error"
            )
            
            # Publish to agent topic from context
            self.broker.publish(self.context.agent_topic, observation.to_dict())

            # Publish ToolResult event to client topic for CLI feedback
            tool_result_msg = {
                "type": "ToolResult",
                "tool_name": request.tool_name,
                "session_id": request.session_id,
                "result": tool_result.output if tool_result.success else f"Error: {tool_result.error}",
                "status": "success" if tool_result.success else "error"
            }

            logger.info(
                "Publishing ToolResult to client_topic %s: tool=%s, call_id=%s, success=%s, status=%s",
                self.context.client_topic,
                request.tool_name,
                request.call_id,
                tool_result.success,
                tool_result_msg.get("status")
            )

            # Log a preview of the result
            result_preview = (tool_result.output if tool_result.success else tool_result.error)[:100]
            logger.debug(f"ToolResult preview: {result_preview}...")

            # Detailed log to dedicated tool result logger
            tool_result_logger.info(
                "=== SINGLE TOOL RESULT ===\n"
                f"Tool: {request.tool_name}\n"
                f"Call ID: {request.call_id}\n"
                f"Success: {tool_result.success}\n"
                f"Result Length: {len(tool_result.output if tool_result.success else tool_result.error)}\n"
                f"Result: {tool_result.output if tool_result.success else tool_result.error}\n"
                "=========================="
            )

            # Skip publishing to client topic for internal todo tools
            # We don't want users to see internal todo operations
            if not request.tool_name.startswith("todo_"):
                self.broker.publish(self.context.client_topic, tool_result_msg)
                logger.info(
                    "Successfully published ToolResult to %s",
                    self.context.client_topic
                )
            else:
                logger.debug(
                    "Skipped publishing ToolResult for internal tool: %s",
                    request.tool_name
                )

            logger.info(
                "Published ToolResultObservation to agent_topic %s: call_id=%s, success=%s",
                self.context.agent_topic,
                request.call_id,
                tool_result.success
            )
            
        except Exception as e:
            logger.error(
                "Error handling tool call request: %s",
                str(e),
                exc_info=True
            )

    async def _handle_batch_request(self, message: Message) -> None:
        """Handle BatchToolCallRequest."""
        from agent_framework.runtime.messages import BatchToolCallRequest
        from agent_framework.messages.types import BatchToolResultObservation, ToolResultObservation
        
        try:
            request = BatchToolCallRequest.from_dict(message.payload)
            
            # For now, we assume all tools are independent and run them in parallel
            # Future: Build DAG for dependencies
            
            async def execute_single(tool_req: ToolCallRequest):
                tool = self._get_tool(tool_req.tool_name)
                start_time = time.time()
                
                if tool is None:
                    return ToolResultObservation(
                        session_id=tool_req.session_id,
                        sequence=0,
                        call_id=tool_req.call_id,
                        content=f"Error: Tool not found: {tool_req.tool_name}",
                        status="error"
                    )
                
                context = ExecutionContext(**tool_req.context)
                try:
                    res = await self.runtime_manager.execute_tool(tool, tool_req.parameters, context)
                    return ToolResultObservation(
                        session_id=tool_req.session_id,
                        sequence=0,
                        call_id=tool_req.call_id,
                        content=res.output if res.success else f"Error: {res.error}",
                        status="success" if res.success else "error"
                    )
                except Exception as e:
                    return ToolResultObservation(
                        session_id=tool_req.session_id,
                        sequence=0,
                        call_id=tool_req.call_id,
                        content=f"Error: Execution failed: {str(e)}",
                        status="error"
                    )

            # Execute all in parallel, tracking execution times
            start_time = time.time()
            results = await asyncio.gather(*[execute_single(req) for req in request.tool_calls])
            total_time = time.time() - start_time

            # Create batch observation
            batch_observation = BatchToolResultObservation(
                session_id=request.session_id,
                sequence=0, # Sequence handled by broker/agent
                batch_id=request.batch_id,
                results=list(results)
            )

            # Publish to agent topic
            self.broker.publish(self.context.agent_topic, batch_observation.to_dict())
            logger.info("Published BatchToolResultObservation to %s", self.context.agent_topic)

            # IMPORTANT: Also publish individual tool results to client topic for display
            # But skip internal todo tools that users shouldn't see
            # We need to map results back to their original requests to get tool names
            for i, result in enumerate(results):
                if isinstance(result, ToolResultObservation):
                    # Get the original tool request to access tool name
                    original_request = request.tool_calls[i]

                    # Skip publishing to client topic for internal todo tools
                    # We don't want users to see internal todo operations
                    if original_request.tool_name.startswith("todo_"):
                        logger.debug(
                            "Skipped publishing batch ToolResult for internal tool: %s (batch_id: %s)",
                            original_request.tool_name,
                            request.batch_id
                        )
                        # Still log to tool result logger for debugging
                        tool_result_logger.info(
                            "=== BATCH TOOL RESULT (INTERNAL) ===\n"
                            f"Tool: {original_request.tool_name}\n"
                            f"Call ID: {result.call_id}\n"
                            f"Batch ID: {request.batch_id}\n"
                            f"Status: {result.status}\n"
                            f"Result Length: {len(result.content)}\n"
                            f"Result: {result.content}\n"
                            "====================================="
                        )
                        continue

                    # Create ToolResult message for client (only for non-todo tools)
                    tool_result_msg = {
                        "type": "ToolResult",
                        "session_id": request.session_id,
                        "call_id": result.call_id,
                        "tool_name": original_request.tool_name,
                        "result": result.content,
                        "status": result.status,
                        "metadata": {
                            "batch_id": request.batch_id,
                            "batch_total_time": total_time,
                            "sequence_in_batch": i + 1,
                            "batch_size": len(request.tool_calls)
                        }
                    }

                    # Log before publishing to client
                    logger.info(
                        "Publishing batch ToolResult to client_topic %s: tool=%s, call_id=%s, batch_id=%s, status=%s",
                        self.context.client_topic,
                        original_request.tool_name,
                        result.call_id,
                        request.batch_id,
                        result.status
                    )

                    # Log detailed information for batch tool results
                    tool_result_logger.info(
                        "=== BATCH TOOL RESULT ===\n"
                        f"Tool: {original_request.tool_name}\n"
                        f"Call ID: {result.call_id}\n"
                        f"Batch ID: {request.batch_id}\n"
                        f"Status: {result.status}\n"
                        f"Sequence in Batch: {i + 1}/{len(request.tool_calls)}\n"
                        f"Batch Total Time: {total_time:.2f}s\n"
                        f"Result Length: {len(result.content)}\n"
                        f"Result: {result.content}\n"
                        "==========================="
                    )

                    # Publish to client topic
                    self.broker.publish(self.context.client_topic, tool_result_msg)

                    logger.info(
                        "Successfully published batch ToolResult to %s",
                        self.context.client_topic
                    )
            
        except Exception as e:
            logger.error("Error handling batch request: %s", str(e), exc_info=True)
            raise e
