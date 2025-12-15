from dataclasses import dataclass

@dataclass
class TopicContext:
    """
    Context object to manage topic names for different components.
    
    Attributes:
        agent_topic: Topic for agent loop control (User Input, Agent Finished).
        runtime_topic: Topic for tool execution requests.
        client_topic: Topic for user-facing information (Wait For Input).
    """
    agent_topic: str
    runtime_topic: str
    client_topic: str

    @classmethod
    def default(cls, session_id: str) -> 'TopicContext':
        """Create a default context based on session ID."""
        return cls(
            agent_topic=f"agent.{session_id}",
            runtime_topic=f"runtime.{session_id}",
            client_topic=f"client.{session_id}"
        )
