import logging
from typing import Dict, Any, Optional

from message_queue.broker import MessageBroker
from .agent_controller import AgentController
from .llm.provider import LLMFactory
from .agents.base import BaseAgent
# Assuming we have a way to create agents from config, or we just pass the class
from .agents.coding_agent import CodingAgent # Example, or use a factory

logger = logging.getLogger("agent_session")

class AgentSession:
    """
    Manages the lifecycle of an agent session.
    
    - Initializes the agent.
    - Sets up the controller.
    - Manages broker subscriptions.
    """
    
    def __init__(
        self,
        session_id: str,
        broker: MessageBroker,
        llm_config: Dict[str, Any],
        agent: BaseAgent,
        agent_config: Dict[str, Any]
    ):
        self.session_id = session_id
        self.broker = broker
        self.llm_config = llm_config
        self.agent_config = agent_config
        
        self.agent: BaseAgent = agent
        self.controller: AgentController = AgentController(agent, broker, topic)
        self.topic = f"agent.{session_id}"

    def start(self):
        """Start the agent session."""
        logger.info(f"Starting session {self.session_id}")
        self.broker.subscribe(self.topic, self.controller.on_event)
        logger.info(f"Session {self.session_id} started. Listening on {self.topic}")
        self.broker.start()

    def stop(self):
        """Stop the session."""
        logger.info(f"Stopping session {self.session_id}")
        self.broker.stop()
