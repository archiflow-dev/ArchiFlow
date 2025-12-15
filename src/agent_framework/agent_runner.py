"""
Generic Agent Runner - Entry point for running any agent type.

This module provides a high-level, reusable interface for running any agent
with the message broker, runtime, and executor infrastructure. It's a
generalized version of coding_agent_runner.py that works with any BaseAgent.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Type, Union
from dataclasses import dataclass, field

from message_queue.broker import MessageBroker
from message_queue.storage.memory import InMemoryBackend
from agent_framework.agent_controller import AgentController
from agent_framework.agents.base import BaseAgent
from agent_framework.llm.provider import LLMProvider
from agent_framework.llm.openai_provider import OpenAIProvider
from agent_framework.llm.usage_tracker import UsageTracker
from agent_framework.context import TopicContext
from agent_framework.runtime.manager import RuntimeManager
from agent_framework.runtime.local import LocalRuntime
from agent_framework.runtime.security import SecurityPolicy
from agent_framework.runtime.executor import RuntimeExecutor
from agent_framework.config.env_loader import load_env

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for generic agent execution.

    This class encapsulates all configuration needed to run any agent task.
    """

    # Agent Configuration
    agent: Optional[BaseAgent] = None
    """Pre-configured agent instance. If provided, agent_class and agent_kwargs are ignored."""

    agent_class: Optional[Type[BaseAgent]] = None
    """Agent class to instantiate (e.g., CodingAgent, SimpleAgent)."""

    agent_kwargs: Dict[str, Any] = field(default_factory=dict)
    """Keyword arguments to pass to the agent constructor."""

    # Initial Task/Message
    initial_message: Optional[str] = None
    """Initial message/task to send to the agent. If None, agent waits for input."""

    # Session Configuration
    session_id: Optional[str] = None
    """Session ID for the agent. Auto-generated if None."""

    # LLM Configuration (used if agent is not pre-configured)
    llm_provider: Optional[LLMProvider] = None
    """Pre-configured LLM provider. If None and agent needs it, creates OpenAIProvider."""

    model: str = "gpt-4o"
    """LLM model to use (e.g., 'gpt-4o', 'gpt-4-turbo')."""

    api_key: Optional[str] = None
    """API key for the LLM provider. If None, reads from environment."""

    # Runtime Configuration
    timeout: float = 1200.0
    """Maximum execution time in seconds (default: 20 minutes)."""

    max_tool_execution_time: float = 30.0
    """Maximum time for a single tool execution (default: 30 seconds)."""

    allow_network: bool = True
    """Whether to allow network access in tool execution."""

    enable_resource_monitoring: bool = True
    """Enable CPU/memory monitoring for tool execution."""

    # Logging & Debugging
    debug_log_path: Optional[str] = None
    """Path to save debug logs. None = no debug logging."""

    log_level: str = "INFO"
    """Logging level: DEBUG, INFO, WARNING, ERROR."""

    # Usage Tracking
    enable_usage_tracking: bool = True
    """Track token usage and costs."""

    usage_tracker: Optional[UsageTracker] = None
    """Pre-configured usage tracker. If None and enabled, creates new one."""

    # Callbacks
    on_tool_execution: Optional[Callable[[str, bool, str], None]] = None
    """Callback(tool_name, success, result) called after each tool execution."""

    on_agent_message: Optional[Callable[[str, Dict[str, Any]], None]] = None
    """Callback(message_type, payload) called for agent events."""

    on_completion: Optional[Callable[[bool, str], None]] = None
    """Callback(success, reason) called when agent finishes."""

    # Message Broker Configuration
    message_broker: Optional[MessageBroker] = None
    """Pre-configured message broker. If None, creates new in-memory broker."""

    # Runtime Manager Configuration
    runtime_manager: Optional[RuntimeManager] = None
    """Pre-configured runtime manager. If None, creates new one with LocalRuntime."""


@dataclass
class AgentResult:
    """Result of an agent execution."""

    success: bool
    """Whether the task completed successfully."""

    reason: str
    """Completion reason or error message."""

    session_id: str = ""
    """Session ID used for this execution."""

    usage_summary: Optional[Dict[str, Any]] = None
    """Token usage and cost summary (if tracking enabled)."""

    execution_time: float = 0.0
    """Total execution time in seconds."""

    error: Optional[Exception] = None
    """Exception if execution failed."""

    agent: Optional[BaseAgent] = None
    """The agent instance that was used."""


async def run_agent(config: AgentConfig) -> AgentResult:
    """
    Run an agent with the given configuration.

    This is the main entry point for executing any agent. It handles all
    setup, execution, and cleanup automatically.

    Args:
        config: Configuration for the agent execution

    Returns:
        AgentResult with execution details

    Example:
        ```python
        from agent_framework.agents.coding_agent import CodingAgent
        from agent_framework.agent_runner import run_agent, AgentConfig

        # Option 1: Pre-configured agent
        agent = CodingAgent(
            session_id="my_session",
            llm=my_llm,
            project_directory="/path/to/project"
        )
        config = AgentConfig(
            agent=agent,
            initial_message="Create a calculator module"
        )

        # Option 2: Agent class with kwargs
        config = AgentConfig(
            agent_class=CodingAgent,
            agent_kwargs={
                "session_id": "my_session",
                "project_directory": "/path/to/project"
            },
            model="gpt-4o",
            initial_message="Create a calculator module"
        )

        result = await run_agent(config)
        ```
    """
    start_time = time.time()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )

    logger.info("=" * 70)
    logger.info("Generic Agent Execution Starting")
    logger.info("=" * 70)

    # Load environment variables
    load_env()

    # Setup usage tracker
    usage_tracker = None
    if config.enable_usage_tracking:
        usage_tracker = config.usage_tracker or UsageTracker()

    # Setup LLM provider (if needed for agent creation)
    llm = config.llm_provider
    if llm is None and config.agent is None:
        # Only create LLM if we need to instantiate an agent
        api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Generate session ID for error reporting
            session_id = config.session_id or f"agent_{int(time.time())}"
            return AgentResult(
                success=False,
                reason="No API key provided and OPENAI_API_KEY not set in environment",
                session_id=session_id,
                error=ValueError("Missing API key")
            )

        llm = OpenAIProvider(
            model=config.model,
            api_key=api_key,
            usage_tracker=usage_tracker
        )
        logger.info(f"LLM Provider: {llm.__class__.__name__}")
        logger.info(f"Model: {llm.model}")

    # Get or create agent
    agent = config.agent
    if agent is None:
        if config.agent_class is None:
            # Generate session ID for error reporting
            session_id = config.session_id or f"agent_{int(time.time())}"
            return AgentResult(
                success=False,
                reason="Either 'agent' or 'agent_class' must be provided",
                session_id=session_id,
                error=ValueError("No agent or agent_class specified")
            )

        # Prepare agent kwargs
        agent_kwargs = config.agent_kwargs.copy()

        # Generate session ID if not provided
        if 'session_id' not in agent_kwargs:
            session_id = config.session_id or f"agent_{int(time.time())}"
            agent_kwargs['session_id'] = session_id
        else:
            # Use the session_id from agent_kwargs
            session_id = agent_kwargs['session_id']

        # Inject llm if not present
        if 'llm' not in agent_kwargs:
            if llm is None:
                return AgentResult(
                    success=False,
                    reason="LLM provider required but not configured",
                    session_id=session_id,
                    error=ValueError("Missing LLM provider")
                )
            agent_kwargs['llm'] = llm

        # Create agent instance
        try:
            agent = config.agent_class(**agent_kwargs)
            logger.info(f"Created agent: {config.agent_class.__name__}")
        except Exception as e:
            logger.error(f"Failed to create agent: {e}", exc_info=True)
            return AgentResult(
                success=False,
                reason=f"Failed to create agent: {str(e)}",
                session_id=session_id,
                error=e
            )
    else:
        # Agent is pre-configured, extract session_id
        if hasattr(agent, 'session_id'):
            session_id = agent.session_id
        elif config.session_id:
            session_id = config.session_id
        else:
            session_id = f"agent_{int(time.time())}"

    logger.info(f"Agent Type: {agent.__class__.__name__}")
    logger.info(f"Session ID: {session_id}")

    # Setup message broker
    logger.info("[1/6] Setting up Message Broker...")
    broker = config.message_broker
    if broker is None:
        broker = MessageBroker(storage_backend=InMemoryBackend())
    broker.start()

    # Setup runtime system
    logger.info("[2/6] Setting up Runtime System...")
    runtime_manager = config.runtime_manager
    if runtime_manager is None:
        policy = SecurityPolicy(
            default_runtime="local",
            max_execution_time=config.max_tool_execution_time,
            allow_network=config.allow_network
        )
        runtime_manager = RuntimeManager(security_policy=policy)
        local_runtime = LocalRuntime(enable_resource_monitoring=config.enable_resource_monitoring)
        runtime_manager.register_runtime("local", local_runtime)

    # Setup agent controller
    logger.info("[3/6] Setting up AgentController...")
    context = TopicContext.default(session_id)
    controller = AgentController(agent=agent, broker=broker, context=context)
    broker.subscribe(context.agent_topic, controller.on_event)

    # Setup runtime executor (if agent has tools)
    logger.info("[4/6] Setting up RuntimeExecutor...")
    tool_registry = None
    if hasattr(agent, 'tools'):
        tool_registry = agent.tools

        # Set execution context on all tools if agent has execution_context
        if hasattr(agent, 'execution_context'):
            for tool in tool_registry.list_tools():
                if hasattr(tool, 'execution_context'):
                    tool.execution_context = agent.execution_context

        logger.info(f"Available Tools: {len(tool_registry.list_tools())}")

    executor = RuntimeExecutor(
        broker=broker,
        runtime_manager=runtime_manager,
        tool_registry=tool_registry,
        context=context
    )
    executor.start()

    # Setup event handling
    logger.info("[5/6] Starting agent loop...")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    # Result tracking
    task_completed = False
    completion_reason = "Unknown"

    def client_subscriber(message):
        """Subscriber for client-facing messages."""
        nonlocal task_completed, completion_reason
        payload = message.payload

        if isinstance(payload, dict):
            msg_type = payload.get('type')

            # Call user callback
            if config.on_agent_message:
                try:
                    config.on_agent_message(msg_type, payload)
                except Exception as e:
                    logger.error(f"Error in on_agent_message callback: {e}")

            if msg_type == 'AGENT_FINISHED':
                completion_reason = payload.get('reason', 'Unknown')
                logger.info(f"Agent finished: {completion_reason}")
                task_completed = True
                loop.call_soon_threadsafe(stop_event.set)

                # Call completion callback
                if config.on_completion:
                    try:
                        config.on_completion(True, completion_reason)
                    except Exception as e:
                        logger.error(f"Error in on_completion callback: {e}")

            elif msg_type == 'WAIT_FOR_USER_INPUT':
                logger.info("Agent is waiting for user input")

            elif msg_type == 'TOOL_RESULT':
                tool_name = payload.get('tool_name', 'unknown')
                error = payload.get('error')
                success = not error
                result = payload.get('result', '') if success else error

                logger.info(f"Tool '{tool_name}' executed: {'success' if success else 'error'}")

                # Call tool execution callback
                if config.on_tool_execution:
                    try:
                        config.on_tool_execution(tool_name, success, result)
                    except Exception as e:
                        logger.error(f"Error in on_tool_execution callback: {e}")

    # Subscribe to client topic
    broker.subscribe(context.client_topic, client_subscriber)

    logger.info("=" * 70)
    logger.info("Agent Execution Started")
    logger.info("=" * 70)

    # Send initial message if provided
    if config.initial_message:
        logger.info(f"Initial message: {config.initial_message[:200]}...")
        broker.publish(context.agent_topic, {
            "content": config.initial_message,
            "type": "UserMessage",
            "session_id": session_id,
            "sequence": 0
        })
    else:
        logger.info("No initial message provided. Agent is waiting for input.")

    # Wait for completion or timeout
    execution_error = None
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=config.timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Task execution timeout ({config.timeout}s)")
        completion_reason = f"Timeout after {config.timeout}s"
        task_completed = False
        execution_error = TimeoutError(completion_reason)
    except Exception as e:
        logger.error(f"Unexpected error during execution: {e}", exc_info=True)
        completion_reason = f"Error: {str(e)}"
        task_completed = False
        execution_error = e

    # Cleanup
    logger.info("Shutting down...")
    broker.stop()
    await runtime_manager.cleanup_all()

    # Calculate execution time
    execution_time = time.time() - start_time

    # Get usage summary
    usage_summary = None
    if usage_tracker:
        usage_summary = usage_tracker.get_summary()

    # Create result
    result = AgentResult(
        success=task_completed,
        reason=completion_reason,
        session_id=session_id,
        usage_summary=usage_summary,
        execution_time=execution_time,
        error=execution_error,
        agent=agent
    )

    # Log summary
    logger.info("=" * 70)
    logger.info("Execution Complete")
    logger.info("=" * 70)
    logger.info(f"Success: {result.success}")
    logger.info(f"Reason: {result.reason}")
    logger.info(f"Execution Time: {result.execution_time:.2f}s")
    if usage_summary:
        logger.info(f"Total Tokens: {usage_summary.get('total_tokens', 0)}")
        logger.info(f"Total Cost: ${usage_summary.get('total_cost', 0):.4f}")
    logger.info("=" * 70)

    return result


# Convenience function for simple usage
async def run_agent_simple(
    agent_class: Type[BaseAgent],
    initial_message: str,
    session_id: Optional[str] = None,
    model: str = "gpt-4o",
    timeout: float = 1200.0,
    **agent_kwargs
) -> AgentResult:
    """
    Simplified interface for running an agent.

    Args:
        agent_class: The agent class to instantiate
        initial_message: Initial message/task to send to the agent
        session_id: Optional session ID
        model: LLM model to use
        timeout: Maximum execution time in seconds
        **agent_kwargs: Additional keyword arguments for agent constructor

    Returns:
        AgentResult

    Example:
        ```python
        from agent_framework.agents.coding_agent import CodingAgent

        result = await run_agent_simple(
            CodingAgent,
            initial_message="Create a calculator module",
            project_directory="/path/to/project",
            model="gpt-4o"
        )
        ```
    """
    config = AgentConfig(
        agent_class=agent_class,
        agent_kwargs=agent_kwargs,
        initial_message=initial_message,
        session_id=session_id,
        model=model,
        timeout=timeout
    )
    return await run_agent(config)


def run_agent_sync(config: AgentConfig) -> AgentResult:
    """
    Synchronous wrapper for run_agent.

    This is useful when you want to run an agent from non-async code.

    Args:
        config: Configuration for the agent execution

    Returns:
        AgentResult
    """
    return asyncio.run(run_agent(config))
