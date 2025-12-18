import json
import logging
from typing import Any, Dict, Optional

from .agents.base import BaseAgent
from .llm.provider import LLMResponse, FinishReason
from .tools.tool_base import registry
from message_queue.broker import MessageBroker
from .messages.types import (
    BaseMessage, UserMessage, ToolCallMessage, ToolResultObservation, LLMRespondMessage,
    WaitForUserInput, AgentFinishedMessage
)
from .context import TopicContext

logger = logging.getLogger("agent_controller")

class AgentController:
    """
    Controller that orchestrates the agent's execution loop.
    
    - Listens to messages from the broker (User inputs).
    - Feeds messages to the Agent.
    - Listens to messages from the Agent (Tool calls, Responses).
    - Executes tools and feeds results back to Agent.
    - Publishes final responses back to the Broker.
    """
    
    def __init__(self, agent: BaseAgent, broker: MessageBroker, context: TopicContext):
        self.agent = agent
        self.broker = broker
        self.context = context

    def on_event(self, message: Any):
        """Callback for new messages from the broker (User input)."""
        try:
            payload = message.payload
            
            if not isinstance(payload, dict):
                logger.warning("Received non-dict payload")
                return

            msg_type = payload.get('type')
            
            # Map legacy/simple types to class names if needed, or rely on sender to be correct
            # For robustness, let's handle the mapping here or ensure senders are correct.
            # Let's assume senders will be updated to send class names, but we can have a fallback map.
            type_map = {
                "USER_INPUT": "UserMessage",
                "TOOL_RESULT_OBSERVATION": "ToolResultObservation",
                "BatchToolResultObservation": "BatchToolResultObservation",
                "AGENT_FINISHED": "AgentFinishedMessage"
            }
            
            if msg_type in type_map:
                payload['type'] = type_map[msg_type]
            
            # Deserialize
            from .messages.types import deserialize_message
            try:
                base_message = deserialize_message(payload)

                # Step the agent
                response = self.agent.step(base_message)
                self._handle_agent_response(response)
            except ValueError as e:
                logger.error(f"Failed to deserialize message: {e}")
                logger.error(f"Payload type: {payload.get('type')}")
                logger.error(f"Payload keys: {list(payload.keys())}")
                import json
                logger.error(f"Payload (first 500 chars): {json.dumps(payload)[:500]}")
                
        except Exception as e:
            logger.error(f"Error in on_event: {e}", exc_info=True)

    def _handle_agent_response(self, message: BaseMessage):
        """Handle the message returned by the agent."""
        if not message:
            return

        logger.info(f"Agent returned: {message.type}")
        
        if isinstance(message, ToolCallMessage):
            self._handle_tool_calls(message)
        elif isinstance(message, WaitForUserInput):
            self.broker.publish(self.context.client_topic, {
                "type": "WAIT_FOR_USER_INPUT",
                "session_id": message.session_id,
                "sequence": message.sequence
            })
        elif isinstance(message, AgentFinishedMessage):
             self.broker.publish(self.context.client_topic, {
                "type": "AGENT_FINISHED",
                "session_id": message.session_id,
                "sequence": message.sequence,
                "reason": message.reason
            })
        elif isinstance(message, LLMRespondMessage):
            self._handle_llm_response(message)

    def _handle_tool_calls(self, message: ToolCallMessage):
        """Execute tools via RuntimeExecutor (Batch)."""
        logger.info(f"Executing {len(message.tool_calls)} tool calls")
        
        # Publish AgentThought message if there's thinking content
        if message.thought and message.thought.strip():
            self.broker.publish(self.context.client_topic, {
                "type": "AgentThought",
                "session_id": message.session_id,
                "sequence": message.sequence,
                "content": message.thought
            })
        
        from .runtime.messages import ToolCallRequest, BatchToolCallRequest
        from .runtime.context import ExecutionContext
        import uuid
        
        # Create execution context
        exec_context = ExecutionContext(
            session_id=message.session_id,
            timeout=60.0 # Default timeout
        )
        
        tool_requests = []
        
        # Create requests for all tools
        for tool_call in message.tool_calls:
            try:
                # Prepare parameters
                params = tool_call.arguments
                if isinstance(params, str):
                    import json
                    try:
                        params = json.loads(params)
                    except:
                        params = {}
                
                # Extract details for feedback
                details = ""
                # Common keys for detailed feedback
                # Includes extracted keys for: bash, web_search, web_fetch, file tools
                details_keys = [
                    'command', 'cmd',               # bash
                    'url',                          # web_fetch
                    'query', 'search_term',         # web_search
                    'target_file', 'file_path',     # file ops
                    'path', 'filename', 'directory' # generic
                ]

                for key in details_keys:
                    if key in params:
                        val = params[key]
                        # Truncate if too long (optional, but good for CLI)
                        if isinstance(val, str) and len(val) > 50:
                            val = val[:47] + "..."
                        details = f" ({key}='{val}')"
                        break
                
                # Publish ToolCall event to client topic for CLI feedback
                self.broker.publish(self.context.client_topic, {
                    "type": "ToolCall",
                    "tool_name": tool_call.tool_name,
                    "session_id": message.session_id,
                    "content": f"Executing {tool_call.tool_name}{details}...",
                    "arguments": params  # Pass full arguments for renderer
                })

                # Create individual request
                # We don't publish it yet, just add to list
                req = ToolCallRequest.create(
                    call_id=tool_call.id,
                    session_id=message.session_id,
                    tool_name=tool_call.tool_name,
                    parameters=params,
                    context=exec_context,
                    reply_topic=self.context.agent_topic
                )
                tool_requests.append(req)
                
            except Exception as e:
                logger.error(f"Error preparing tool call {tool_call.tool_name}: {e}") 
        if tool_requests:
            # Create Batch Request
            batch_req = BatchToolCallRequest.create(
                batch_id=str(uuid.uuid4()),
                session_id=message.session_id,
                tool_calls=tool_requests,
                context=exec_context,
                reply_topic=self.context.agent_topic
            )
            
            # Publish Batch Request
            self.broker.publish(self.context.runtime_topic, batch_req.to_dict())

    def _handle_llm_response(self, message: LLMRespondMessage):
        """
        Handle a direct text response from the LLM (no tool calls).
        This usually means the agent is talking to the user.
        """
        logger.info(f"Handling LLM response: {message.content[:50]}...")
        
        # 1. Publish the content as an AssistantMessage for the UI to render
        self.broker.publish(self.context.client_topic, {
            "type": "AssistantMessage",
            "session_id": message.session_id,
            "content": message.content,
            "sequence": message.sequence
        })

        # 2. Signal that we are waiting for user input
        # This unblocks the CLI input loop
        self.broker.publish(self.context.client_topic, {
            "type": "WAIT_FOR_USER_INPUT",
            "session_id": message.session_id,
            "sequence": message.sequence
        })


