"""
Web Session Broker for ArchiFlow Web Backend.

Manages the message broker infrastructure for web sessions, bridging
WebSocket transport with the agent framework's pub/sub architecture.
"""

from typing import Optional, Callable, Awaitable, Dict, Any, TYPE_CHECKING
from pathlib import Path
import asyncio
import logging
import os

from message_queue.broker import MessageBroker
from message_queue.storage.memory import InMemoryBackend
from agent_framework.agent_controller import AgentController
from agent_framework.context import TopicContext
from agent_framework.runtime.executor import RuntimeExecutor
from agent_framework.runtime.manager import RuntimeManager
from agent_framework.runtime.local import LocalRuntime
from agent_framework.runtime.security import SecurityPolicy

if TYPE_CHECKING:
    from agent_framework.agents.base import BaseAgent
    from .web_agent_factory import WebAgentFactory

logger = logging.getLogger(__name__)


class WebSessionBrokerError(Exception):
    """Raised when broker operations fail."""
    pass


class WebSessionBroker:
    """
    Manages the message broker infrastructure for a web session.

    This bridges the WebSocket transport with the agent framework's
    pub/sub architecture, enabling consistent behavior with the CLI.

    Architecture:
        Frontend ←→ WebSocket ←→ WebSessionBroker ←→ MessageBroker ←→ AgentController

    Message Flow:
        1. Frontend sends message via WebSocket
        2. WebSessionBroker publishes to agent_topic
        3. AgentController receives, processes, publishes to client_topic
        4. WebSessionBroker receives from client_topic
        5. WebSessionBroker sends to frontend via WebSocket callback

    The broker enables:
        - Proper tool execution loop (multiple tool calls per message)
        - Auto-refinement of prompts via PromptPreprocessor
        - Decoupled architecture for testability
        - Consistent behavior with CLI

    Usage:
        broker = WebSessionBroker(
            session_id="session_123",
            user_id="user_456",
            agent=agent,
            workspace_path=Path("/workspace/user_456/session_123"),
            ws_callback=send_to_websocket,
        )
        await broker.start()
        await broker.send_message("Build a web app")
        # ... messages flow through broker and arrive at ws_callback
        await broker.stop()
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        agent: "BaseAgent",
        workspace_path: Path,
        ws_callback: Callable[[Dict[str, Any]], Awaitable[None]],
        auto_refine_enabled: bool = False,
    ):
        """
        Initialize the session broker.

        Args:
            session_id: Unique session identifier
            user_id: User identifier for workspace isolation
            agent: The agent instance to control
            workspace_path: Session workspace directory
            ws_callback: Async callback to send messages to WebSocket
            auto_refine_enabled: Whether auto-refinement is enabled
        """
        self.session_id = session_id
        self.user_id = user_id
        self.agent = agent
        self.workspace_path = workspace_path
        self.ws_callback = ws_callback
        self._auto_refine_enabled = auto_refine_enabled

        # Infrastructure (initialized in start())
        self.broker: Optional[MessageBroker] = None
        self.context: Optional[TopicContext] = None
        self.controller: Optional[AgentController] = None
        self.executor: Optional[RuntimeExecutor] = None
        self.runtime_manager: Optional[RuntimeManager] = None

        self._started = False
        self._message_sequence = 0

    @property
    def is_started(self) -> bool:
        """Check if the broker is started."""
        return self._started

    def _auto_refine_callback(self) -> bool:
        """Callback for AgentController to check if auto-refinement is enabled."""
        return self._auto_refine_enabled

    def set_auto_refine_enabled(self, enabled: bool) -> None:
        """Set whether auto-refinement is enabled."""
        self._auto_refine_enabled = enabled

    async def start(self) -> None:
        """
        Start the broker infrastructure.

        Sets up:
        1. MessageBroker with InMemoryBackend
        2. TopicContext with session-specific topics
        3. RuntimeManager with sandboxed LocalRuntime
        4. AgentController (subscribes to agent_topic)
        5. RuntimeExecutor (subscribes to runtime_topic)
        6. Client bridge (subscribes to client_topic)

        Raises:
            WebSessionBrokerError: If broker fails to start
        """
        if self._started:
            logger.warning(f"Session broker for {self.session_id} already started")
            return

        try:
            # 1. Create message broker
            self.broker = MessageBroker(storage_backend=InMemoryBackend())

            # 2. Create topic context
            self.context = TopicContext.default(self.session_id)

            # 3. Create runtime manager with security policy
            policy = SecurityPolicy(
                default_runtime="local",
                max_execution_time=60,  # Web sessions may need longer
                allow_network=True,  # For API calls
            )
            self.runtime_manager = RuntimeManager(security_policy=policy)

            # Create sandboxed local runtime
            local_runtime = LocalRuntime(enable_resource_monitoring=True)
            self.runtime_manager.register_runtime("local", local_runtime)

            # 4. Create agent controller
            self.controller = AgentController(
                agent=self.agent,
                broker=self.broker,
                context=self.context,
                working_dir=self.workspace_path,
                auto_refine_enabled_callback=self._auto_refine_callback,
            )

            # 5. Create runtime executor
            # Get tool registry from agent
            tool_registry = getattr(self.agent, 'tool_registry', None)
            if tool_registry is None:
                logger.warning(
                    f"Agent has no tool_registry, tools may not execute properly"
                )

            self.executor = RuntimeExecutor(
                broker=self.broker,
                runtime_manager=self.runtime_manager,
                tool_registry=tool_registry,
                context=self.context,
            )

            # Start broker
            self.broker.start()

            # Subscribe AgentController to agent_topic
            self.broker.subscribe(self.context.agent_topic, self.controller.on_event)

            # Start RuntimeExecutor (subscribes to runtime_topic)
            self.executor.start()

            # Subscribe to client_topic for WebSocket forwarding
            self.broker.subscribe(self.context.client_topic, self._on_client_topic)

            self._started = True

            logger.info(
                f"WebSessionBroker started for session {self.session_id} "
                f"(topics: agent={self.context.agent_topic}, "
                f"client={self.context.client_topic}, "
                f"runtime={self.context.runtime_topic})"
            )

        except Exception as e:
            logger.exception(f"Failed to start session broker for {self.session_id}")
            await self._cleanup()
            raise WebSessionBrokerError(f"Failed to start broker: {e}") from e

    async def _on_client_topic(self, message: Any) -> None:
        """
        Handle messages on client_topic.

        Transforms broker messages to WebSocket events and sends to frontend.

        Args:
            message: Message from broker
        """
        try:
            payload = message.payload if hasattr(message, 'payload') else message

            if not isinstance(payload, dict):
                logger.warning(f"Non-dict payload received on client_topic: {type(payload)}")
                return

            # Log the message received from client_topic
            msg_type = payload.get("type", "unknown")
            logger.debug(f"📨 Received message from client_topic: {msg_type}")
            logger.debug(f"  Payload: {payload}")

            # Transform to WebSocket event format
            event = self._transform_to_ws_event(payload)

            # Log the transformed event
            logger.debug(f"🌐 Transformed to WebSocket event: {event.get('type', 'unknown')}")
            logger.debug(f"  Event: {event}")

            # Send to frontend via callback
            if self.ws_callback:
                await self.ws_callback(event)
                logger.debug(f"✅ Sent to WebSocket callback for session {self.session_id}")

        except Exception as e:
            logger.error(f"Error forwarding to WebSocket: {e}", exc_info=True)

    def _transform_to_ws_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform broker message to WebSocket event format.

        Maps internal message types to frontend-friendly events.

        Args:
            payload: Broker message payload

        Returns:
            WebSocket event dictionary
        """
        msg_type = payload.get("type", "unknown")

        # Common fields
        base_event = {
            "session_id": self.session_id,
            "timestamp": payload.get("timestamp"),
        }

        if msg_type == "AssistantMessage":
            return {
                **base_event,
                "type": "agent_message",
                "content": payload.get("content", ""),
                "sequence": payload.get("sequence", 0),
            }

        elif msg_type == "ToolCall":
            return {
                **base_event,
                "type": "tool_call",
                "tool_name": payload.get("tool_name", ""),
                "content": payload.get("content", ""),
                "arguments": payload.get("arguments", {}),
            }

        elif msg_type == "ToolResult":
            return {
                **base_event,
                "type": "tool_result",
                "tool_name": payload.get("tool_name", ""),
                "result": payload.get("result", ""),
                "status": payload.get("status", "unknown"),
                "metadata": payload.get("metadata", {}),
            }

        elif msg_type == "AgentThought":
            return {
                **base_event,
                "type": "agent_thought",
                "content": payload.get("content", ""),
            }

        elif msg_type == "WAIT_FOR_USER_INPUT":
            return {
                **base_event,
                "type": "waiting_for_input",
                "sequence": payload.get("sequence", 0),
            }

        elif msg_type == "AGENT_FINISHED":
            return {
                **base_event,
                "type": "agent_finished",
                "reason": payload.get("reason", ""),
            }

        elif msg_type == "RefinementNotification":
            return {
                **base_event,
                "type": "refinement_applied",
                "content": payload.get("content", ""),
            }

        else:
            # Pass through unknown types
            return {
                **base_event,
                "type": msg_type.lower(),
                "payload": payload,
            }

    async def send_message(self, content: str) -> None:
        """
        Send a user message to the agent.

        Publishes UserMessage to agent_topic, which AgentController
        will pick up and process.

        Args:
            content: The user message content

        Raises:
            WebSessionBrokerError: If broker not started
        """
        if not self._started:
            raise WebSessionBrokerError("Session broker not started")

        self._message_sequence += 1

        # Publish UserMessage to agent_topic
        self.broker.publish(
            self.context.agent_topic,
            {
                "type": "UserMessage",
                "content": content,
                "session_id": self.session_id,
                "sequence": self._message_sequence,
            }
        )

        logger.debug(
            f"📤 Published UserMessage to {self.context.agent_topic}: "
            f"seq={self._message_sequence}, content_len={len(content)}"
        )
        logger.debug(f"  Content: {content[:100]}{'...' if len(content) > 100 else ''}")

    async def stop(self) -> None:
        """Stop the broker infrastructure and cleanup resources."""
        if not self._started:
            return

        await self._cleanup()

        logger.info(f"WebSessionBroker stopped for session {self.session_id}")

    async def _cleanup(self) -> None:
        """Cleanup all resources."""
        try:
            # Unsubscribe from client topic
            if self.broker and self.context:
                try:
                    self.broker.unsubscribe(
                        self.context.client_topic,
                        self._on_client_topic
                    )
                except Exception as e:
                    logger.warning(f"Error unsubscribing from client topic: {e}")

            # Stop executor
            if self.executor:
                try:
                    self.executor.stop()
                except Exception as e:
                    logger.warning(f"Error stopping executor: {e}")

            # Stop broker
            if self.broker:
                try:
                    self.broker.stop()
                except Exception as e:
                    logger.warning(f"Error stopping broker: {e}")

        finally:
            self._started = False
            self.broker = None
            self.context = None
            self.controller = None
            self.executor = None
            self.runtime_manager = None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get broker statistics.

        Returns:
            Dictionary with broker stats
        """
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "started": self._started,
            "message_sequence": self._message_sequence,
            "workspace": str(self.workspace_path),
            "auto_refine_enabled": self._auto_refine_enabled,
            "topics": {
                "agent": self.context.agent_topic if self.context else None,
                "client": self.context.client_topic if self.context else None,
                "runtime": self.context.runtime_topic if self.context else None,
            } if self.context else None,
        }
