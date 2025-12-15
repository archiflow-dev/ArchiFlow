"""
Entry point for running CodingAgent tasks.

This module provides a high-level, reusable interface for running coding tasks
with the CodingAgent. It handles all the boilerplate setup (message broker,
runtime, executor, etc.) and provides a clean API.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field

from message_queue.broker import MessageBroker
from message_queue.storage.memory import InMemoryBackend
from agent_framework.agent_controller import AgentController
from agent_framework.agents.coding_agent import CodingAgent
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
class CodingAgentConfig:
    """Configuration for CodingAgent execution.

    This class encapsulates all configuration needed to run a coding agent task.
    """

    # Core Configuration
    task: str
    """The coding task description to execute."""

    project_dir: Path
    """Directory where the agent will work (create/edit files)."""

    # LLM Configuration
    model: str = "gpt-4o"
    """LLM model to use (e.g., 'gpt-4o', 'gpt-4-turbo', 'claude-3-5-sonnet')."""

    api_key: Optional[str] = None
    """API key for the LLM provider. If None, reads from environment."""

    llm_provider: Optional[LLMProvider] = None
    """Pre-configured LLM provider. If provided, model and api_key are ignored."""

    # Session Configuration
    session_id: Optional[str] = None
    """Session ID for the agent. Auto-generated if None."""

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
    """Path to save debug logs (LLM interactions). None = no debug logging."""

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

    # Advanced
    custom_tools: Optional[Any] = None
    """Custom tool registry to use instead of default tools."""

    strict_mode: bool = False
    """If True, enforce all operations within project_directory."""

    auto_create_project_dir: bool = True
    """If True, create project_dir if it doesn't exist."""


@dataclass
class CodingAgentResult:
    """Result of a coding agent execution."""

    success: bool
    """Whether the task completed successfully."""

    reason: str
    """Completion reason or error message."""

    files_created: List[Path] = field(default_factory=list)
    """List of files created/modified during execution."""

    session_id: str = ""
    """Session ID used for this execution."""

    usage_summary: Optional[Dict[str, Any]] = None
    """Token usage and cost summary (if tracking enabled)."""

    execution_time: float = 0.0
    """Total execution time in seconds."""

    error: Optional[Exception] = None
    """Exception if execution failed."""


async def run_coding_agent(config: CodingAgentConfig) -> CodingAgentResult:
    """
    Run a coding agent task with the given configuration.

    This is the main entry point for executing coding tasks. It handles all
    setup, execution, and cleanup automatically.

    Args:
        config: Configuration for the coding agent execution

    Returns:
        CodingAgentResult with execution details

    Example:
        ```python
        from pathlib import Path
        from agent_framework.coding_agent_runner import run_coding_agent, CodingAgentConfig

        config = CodingAgentConfig(
            task="Create a Python calculator with add/subtract/multiply/divide",
            project_dir=Path("./my_project"),
            model="gpt-4o",
            timeout=600.0
        )

        result = await run_coding_agent(config)

        if result.success:
            print(f"Task completed! Files: {result.files_created}")
            print(f"Tokens used: {result.usage_summary}")
        else:
            print(f"Task failed: {result.reason}")
        ```
    """
    import time
    start_time = time.time()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )

    logger.info("="*70)
    logger.info("CodingAgent Execution Starting")
    logger.info("="*70)

    # Load environment variables
    load_env()

    # Validate and setup project directory
    if config.auto_create_project_dir:
        config.project_dir.mkdir(parents=True, exist_ok=True)
    elif not config.project_dir.exists():
        return CodingAgentResult(
            success=False,
            reason=f"Project directory does not exist: {config.project_dir}",
            error=FileNotFoundError(f"Project directory not found: {config.project_dir}")
        )

    logger.info(f"Project Directory: {config.project_dir}")
    logger.info(f"Task: {config.task[:200]}...")

    # Generate session ID if not provided
    session_id = config.session_id or f"coding_agent_{int(time.time())}"

    # Setup usage tracker
    usage_tracker = None
    if config.enable_usage_tracking:
        usage_tracker = config.usage_tracker or UsageTracker()

    # Setup LLM provider
    llm = config.llm_provider
    if llm is None:
        api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return CodingAgentResult(
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

    # Setup message broker
    logger.info("[1/6] Setting up Message Broker...")
    broker = MessageBroker(storage_backend=InMemoryBackend())
    broker.start()

    # Setup runtime system
    logger.info("[2/6] Setting up Runtime System...")
    policy = SecurityPolicy(
        default_runtime="local",
        max_execution_time=config.max_tool_execution_time,
        allow_network=config.allow_network
    )

    runtime_manager = RuntimeManager(security_policy=policy)
    local_runtime = LocalRuntime(enable_resource_monitoring=config.enable_resource_monitoring)
    runtime_manager.register_runtime("local", local_runtime)

    # Create coding agent
    logger.info("[3/6] Creating CodingAgent...")
    agent = CodingAgent(
        session_id=session_id,
        llm=llm,
        project_directory=str(config.project_dir),
        tools=config.custom_tools,
        strict_mode=config.strict_mode,
        debug_log_path=config.debug_log_path
    )

    # Set execution context on all tools
    for tool in agent.tools.list_tools():
        tool.execution_context = agent.execution_context

    logger.info(f"Session ID: {session_id}")
    logger.info(f"Available Tools: {len(agent.tools.list_tools())}")

    # Setup agent controller
    logger.info("[4/6] Setting up AgentController...")
    context = TopicContext.default(session_id)
    controller = AgentController(agent=agent, broker=broker, context=context)
    broker.subscribe(context.agent_topic, controller.on_event)

    # Setup runtime executor
    logger.info("[5/6] Setting up RuntimeExecutor...")
    executor = RuntimeExecutor(
        broker=broker,
        runtime_manager=runtime_manager,
        tool_registry=agent.tools,
        context=context
    )
    executor.start()

    # Setup event handling
    logger.info("[6/6] Starting agent loop...")
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

    logger.info("="*70)
    logger.info("Agent Execution Started")
    logger.info("="*70)

    # Send initial task message
    broker.publish(context.agent_topic, {
        "content": config.task,
        "type": "UserMessage",
        "session_id": session_id,
        "sequence": 0
    })

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

    # Collect created files
    created_files = []
    try:
        all_files = list(config.project_dir.rglob("*"))
        created_files = [f for f in all_files if f.is_file()]
    except Exception as e:
        logger.warning(f"Could not enumerate created files: {e}")

    # Get usage summary
    usage_summary = None
    if usage_tracker:
        usage_summary = usage_tracker.get_summary()

    # Create result
    result = CodingAgentResult(
        success=task_completed,
        reason=completion_reason,
        files_created=created_files,
        session_id=session_id,
        usage_summary=usage_summary,
        execution_time=execution_time,
        error=execution_error
    )

    # Log summary
    logger.info("="*70)
    logger.info("Execution Complete")
    logger.info("="*70)
    logger.info(f"Success: {result.success}")
    logger.info(f"Reason: {result.reason}")
    logger.info(f"Files Created: {len(result.files_created)}")
    logger.info(f"Execution Time: {result.execution_time:.2f}s")
    if usage_summary:
        logger.info(f"Total Tokens: {usage_summary.get('total_tokens', 0)}")
        logger.info(f"Total Cost: ${usage_summary.get('total_cost', 0):.4f}")
    logger.info("="*70)

    return result


# Convenience functions for common use cases

async def run_coding_task(
    task: str,
    project_dir: Path,
    model: str = "gpt-4o",
    timeout: float = 1200.0,
    **kwargs
) -> CodingAgentResult:
    """
    Simplified interface for running a coding task.

    Args:
        task: The coding task description
        project_dir: Directory where files will be created
        model: LLM model to use
        timeout: Maximum execution time in seconds
        **kwargs: Additional CodingAgentConfig parameters

    Returns:
        CodingAgentResult

    Example:
        ```python
        result = await run_coding_task(
            task="Create a REST API with FastAPI",
            project_dir=Path("./my_api"),
            model="gpt-4o",
            debug_log_path="./debug.log"
        )
        ```
    """
    config = CodingAgentConfig(
        task=task,
        project_dir=project_dir,
        model=model,
        timeout=timeout,
        **kwargs
    )
    return await run_coding_agent(config)


def run_coding_task_sync(
    task: str,
    project_dir: Path,
    model: str = "gpt-4o",
    timeout: float = 1200.0,
    **kwargs
) -> CodingAgentResult:
    """
    Synchronous wrapper for run_coding_task.

    This is useful when you want to run a coding task from non-async code.

    Args:
        task: The coding task description
        project_dir: Directory where files will be created
        model: LLM model to use
        timeout: Maximum execution time in seconds
        **kwargs: Additional CodingAgentConfig parameters

    Returns:
        CodingAgentResult

    Example:
        ```python
        result = run_coding_task_sync(
            task="Create a calculator module",
            project_dir=Path("./calculator")
        )
        ```
    """
    return asyncio.run(run_coding_task(task, project_dir, model, timeout, **kwargs))
