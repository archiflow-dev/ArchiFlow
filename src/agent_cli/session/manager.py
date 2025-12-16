"""
Session manager for CLI sessions with broker integration.

Manages CLI sessions with full broker infrastructure including:
- MessageBroker setup
- TopicContext creation
- AgentController initialization
- RuntimeExecutor initialization
"""

import time
from dataclasses import dataclass, field

from agent_framework.agent_controller import AgentController
from agent_framework.runtime.local import LocalRuntime
from agent_framework.runtime.security import SecurityPolicy
from agent_framework.agents.base import BaseAgent
from agent_framework.context import TopicContext
from agent_framework.runtime.executor import RuntimeExecutor
from agent_framework.runtime.manager import RuntimeManager
from message_queue.broker import MessageBroker
from message_queue.storage.memory import InMemoryBackend


@dataclass
class CLISession:
    """
    Represents a CLI session with an agent.

    A session includes:
    - Unique session ID
    - Agent instance
    - Message broker
    - Topic context for pub/sub
    - Agent controller
    - Runtime executor
    """

    session_id: str
    agent: BaseAgent
    broker: MessageBroker
    context: TopicContext
    controller: AgentController
    executor: RuntimeExecutor
    runtime_manager: RuntimeManager
    created_at: float = field(default_factory=time.time)
    active: bool = True

    def close(self) -> None:
        """Close the session and cleanup resources."""
        self.active = False
        # Stop the broker
        if self.broker:
            self.broker.stop()


class SessionManager:
    """
    Manages CLI sessions.

    Handles session creation, retrieval, and cleanup with full broker infrastructure.
    """

    def __init__(self) -> None:
        """Initialize the session manager."""
        self.sessions: dict[str, CLISession] = {}
        self.active_session_id: str | None = None

    def create_session(
        self,
        agent: BaseAgent,
        session_id: str | None = None,
    ) -> CLISession:
        """
        Create a new CLI session with full broker infrastructure.

        This sets up:
        1. MessageBroker with InMemoryBackend
        2. TopicContext with session-specific topics:
           - agent_topic: session_{id}:agent (for messages TO agent)
           - client_topic: session_{id}:client (for messages FROM agent)
           - runtime_topic: session_{id}:runtime (for tool execution)
        3. AgentController (manages agent, subscribes to agent_topic)
        4. RuntimeExecutor (executes tools, subscribes to runtime_topic)

        Args:
            agent: The agent instance to use
            session_id: Optional session ID (auto-generated if not provided)

        Returns:
            CLISession instance with all infrastructure set up
        """
        # Generate session ID if not provided
        if session_id is None:
            # Use agent's session_id if available, otherwise generate
            if hasattr(agent, "session_id") and agent.session_id:
                session_id = agent.session_id
            else:
                session_id = f"cli_{int(time.time())}"

        # Create message broker
        broker = MessageBroker(storage_backend=InMemoryBackend())

        # Create topic context
        # Topics:
        # - agent_topic: session_{id}:agent (CLI publishes user messages here)
        # - client_topic: session_{id}:client (Agent publishes responses here)
        # - runtime_topic: session_{id}:runtime (Tool execution messages)
        context = TopicContext.default(session_id)
        policy = SecurityPolicy(
            default_runtime="local",
            max_execution_time=30,
            allow_network=True  # Allow network for OpenAI API calls
        )

        runtime_manager = RuntimeManager(security_policy=policy)
        local_runtime = LocalRuntime(enable_resource_monitoring=True)
        runtime_manager.register_runtime("local", local_runtime)

        # Create agent controller
        # AgentController manages the agent and subscribes to agent_topic
        controller = AgentController(
            agent=agent,
            broker=broker,
            context=context,
        )

        # Create runtime executor
        # RuntimeExecutor handles tool execution and subscribes to runtime_topic
        executor = RuntimeExecutor(
            broker=broker,
            runtime_manager=runtime_manager,
            tool_registry=agent.tool_registry,  # type: ignore[attr-defined]
            context=context,
        )

        # Start the broker
        broker.start()

        # Subscribe AgentController to agent_topic
        broker.subscribe(context.agent_topic, controller.on_event)

        # Start RuntimeExecutor (subscribes to runtime_topic)
        executor.start()

        # Create session object
        session = CLISession(
            session_id=session_id,
            agent=agent,
            broker=broker,
            context=context,
            controller=controller,
            executor=executor,
            runtime_manager=runtime_manager,
        )

        # Store session
        self.sessions[session_id] = session

        # Set as active session
        self.active_session_id = session_id

        return session

    def get_session(self, session_id: str) -> CLISession | None:
        """
        Get a session by ID.

        Args:
            session_id: The session ID

        Returns:
            CLISession or None if not found
        """
        return self.sessions.get(session_id)

    def get_active_session(self) -> CLISession | None:
        """
        Get the currently active session.

        Returns:
            Active CLISession or None if no active session
        """
        if self.active_session_id:
            return self.sessions.get(self.active_session_id)
        return None

    def list_sessions(self) -> list[CLISession]:
        """
        Get all sessions.

        Returns:
            List of all sessions
        """
        return list(self.sessions.values())

    def send_message(self, content: str, session_id: str | None = None) -> bool:
        """
        Send a message to the agent via broker.

        Args:
            content: The message content
            session_id: Optional session ID (uses active session if not provided)

        Returns:
            True if message was sent, False otherwise
        """
        # Get session
        if session_id:
            session = self.get_session(session_id)
        else:
            session = self.get_active_session()

        if not session or not session.active:
            return False

        # Publish UserMessage to agent_topic
        # Message should include: type, content, session_id, sequence
        session.broker.publish(
            session.context.agent_topic,
            {
                "type": "UserMessage",
                "content": content,
                "session_id": session.session_id,
                "sequence": 0,  # TODO: Track message sequence
            },
        )

        return True

    def abort_agent(self, session_id: str | None = None) -> bool:
        """
        Abort the currently running agent in a session.

        Args:
            session_id: Optional session ID (uses active session if not provided)

        Returns:
            True if abort message was sent, False otherwise
        """
        # Get session
        if session_id:
            session = self.get_session(session_id)
        else:
            session = self.get_active_session()

        if not session or not session.active:
            return False

        # Publish Abort message to agent_topic
        session.broker.publish(
            session.context.agent_topic,
            {
                "type": "Abort",
                "content": "Agent execution aborted by user",
                "session_id": session.session_id,
            },
        )

        # Also publish to runtime_topic to stop any running tool execution
        session.broker.publish(
            session.context.runtime_topic,
            {
                "type": "Abort",
                "content": "Tool execution aborted by user",
                "session_id": session.session_id,
            },
        )

        return True

    def close_session(self, session_id: str) -> bool:
        """
        Close a session and cleanup resources.

        Args:
            session_id: The session ID to close

        Returns:
            True if session was closed, False if not found
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # Close the session
        session.close()

        # Remove from sessions
        del self.sessions[session_id]

        # Clear active session if this was it
        if self.active_session_id == session_id:
            self.active_session_id = None

        return True

    def close_all_sessions(self) -> None:
        """Close all sessions."""
        for session_id in list(self.sessions.keys()):
            self.close_session(session_id)
